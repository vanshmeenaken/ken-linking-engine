"""Agent 2 — Entity Extraction (Phase 2, Day 3).

Extracts normalized entities (industry, country, region, market, time_period)
from the stored metadata of every active content node: URL slug, title, H1,
meta description, and the trusted industry/country fields written by Agent 1.

Deliberately metadata-only — no live crawling, no LLM calls (Phase 2
execution discipline rule 4: deterministic before LLM). Body-content entity
types (company, product, technology, regulation, claim, evidence) are out of
scope and documented as deferred.

Writes, in one transaction:
  - content_entities   (deduplicated by normalized_name + entity_type)
  - node_entities      (page-to-entity mapping with provenance + confidence)
  - content_nodes      (market, region backfill where confidently extracted)
  - entity_extraction_logs (one row per node + run summary row)

Usage:
    python agents/agent_2_entity_extraction.py --dry-run          # report only
    python agents/agent_2_entity_extraction.py --limit 25         # small batch
    python agents/agent_2_entity_extraction.py                    # full live run

Confidence model (Module 3.2):
    0.95  trusted DB field (industry, country — verified by Agent 1 crawl)
    0.90  region derived from trusted country via taxonomy map
    0.90  scope value reclassified as region (e.g. 'gcc' -> Middle East)
    0.85  explicit time period in title (regex year range)
    0.65  market extracted from title pattern (base)
   +0.15  H1 independently agrees with title market
   +0.10  URL slug independently agrees          (market cap: 0.90)
    <0.50 flagged low-confidence for manual review
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.taxonomy import (
    COUNTRY_ALIASES,
    SCOPE_VALUES,
    classify_geo,
    extract_market_from_title,
    normalize_industry,
    normalize_market_name,
    region_for_country,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
REPORT_DIR = ROOT / "reports"
LOG_DIR = ROOT / "logs"

LOW_CONFIDENCE_THRESHOLD = 0.50

CONFIDENCE = {
    "db_field": 0.95,
    "region_from_country": 0.90,
    "region_from_scope": 0.90,
    "country_from_title": 0.65,
    "time_period_title": 0.85,
    "market_title_base": 0.65,
    "market_h1_agreement": 0.15,
    "market_slug_agreement": 0.10,
    "market_cap": 0.90,
}

_YEAR_RANGE = re.compile(r"\b(\d{4})\s*(?:[-–—�]|to)\s*(\d{4})\b", re.I)

# Full geography lexicon: every known country name, alias and scope value.
# Market-name stripping must use ALL of these, not just the page's own
# country field — Phase 1 country data is sometimes wrong (dry-run finding:
# a UAE report stored country='global', leaving 'United Arab Emirates'
# inside the market name).
from config.taxonomy import COUNTRY_TO_REGION  # noqa: E402

_GEO_LEXICON: list[str] = sorted(
    set(COUNTRY_TO_REGION) | set(COUNTRY_ALIASES) | set(SCOPE_VALUES),
    key=len, reverse=True,  # longest first so 'united arab emirates' wins over 'uae'
)


def _display_name(value: str) -> str:
    """Title-case a canonical lowercase name for display ('india' -> 'India'),
    preserving known acronyms."""
    acronyms = {"uae": "UAE", "usa": "USA", "uk": "UK", "gcc": "GCC"}
    if value.lower() in acronyms:
        return acronyms[value.lower()]
    return " ".join(
        word if word.isupper() else word.capitalize() for word in value.split()
    )


def _country_from_title(title: str) -> str:
    """Detect a leading geography in a title and return the canonical country
    ('' if the lead is a scope/region or no geography is found).
    'United Arab Emirates Low GWP Refrigerants Market ...' -> 'uae'."""
    lowered = (title or "").lower().strip()
    for surface in _GEO_LEXICON:
        if lowered.startswith(surface + " "):
            geo_type, canonical = classify_geo(surface)
            return canonical if geo_type == "country" else ""
    return ""


@dataclass
class ExtractedEntity:
    """One entity found on one page, with provenance for node_entities."""

    entity_type: str          # industry | country | region | market | time_period
    entity_name: str          # display form ('Healthcare', 'India', 'Pectin Market')
    normalized_name: str      # dedup key (lowercase)
    entity_role: str          # node_entities.entity_role
    source_field: str         # db_industry | db_country | title | h1 | url_slug
    extracted_value: str      # raw value as found
    confidence: float
    extraction_method: str    # exact_field | pattern | alias | derived
    region: str = ""          # context columns for content_entities
    country: str = ""
    industry: str = ""

    @property
    def low_confidence(self) -> bool:
        return self.confidence < LOW_CONFIDENCE_THRESHOLD


@dataclass
class NodeExtraction:
    """Everything Agent 2 learned about one content node."""

    node_id: str
    url: str
    content_type: str
    entities: list[ExtractedEntity] = field(default_factory=list)
    market_backfill: str = ""   # value for content_nodes.market ('' = leave)
    region_backfill: str = ""   # value for content_nodes.region
    error: str = ""

    @property
    def low_confidence_count(self) -> int:
        return sum(1 for e in self.entities if e.low_confidence)


class EntityExtractionAgent:
    """Deterministic entity extraction over stored content_nodes metadata."""

    def __init__(self, db_path=DEFAULT_DB, logger=None):
        self.db_path = Path(db_path)
        self.logger = logger or logging.getLogger("entity_extraction_agent")
        self.run_id = str(uuid.uuid4())

    # ── load ────────────────────────────────────────────────────────────────

    def load_nodes(self, limit: int | None = None) -> list[dict]:
        """Active content nodes with the metadata fields extraction reads."""
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            sql = (
                "SELECT node_id, url, title, h1, meta_description, content_type, "
                "COALESCE(industry,'') industry, COALESCE(country,'') country "
                "FROM content_nodes WHERE status = 'active' ORDER BY rowid"
            )
            params: tuple = ()
            if limit is not None:
                sql += " LIMIT ?"
                params = (limit,)
            return [dict(row) for row in conn.execute(sql, params)]
        finally:
            conn.close()

    # ── extraction ──────────────────────────────────────────────────────────

    def extract_node(self, node: dict) -> NodeExtraction:
        """Run all extraction rules against one node. Never raises."""
        result = NodeExtraction(
            node_id=node["node_id"], url=node["url"],
            content_type=node.get("content_type", ""),
        )
        try:
            self._extract_industry(node, result)
            self._extract_geography(node, result)
            self._extract_market(node, result)
            self._extract_time_period(node, result)
        except Exception as exc:  # defensive: one bad node must not stop the run
            result.error = f"{type(exc).__name__}: {exc}"
            self.logger.error("%s: %s", node["url"], result.error)
        return result

    def _extract_industry(self, node: dict, result: NodeExtraction) -> None:
        raw = node.get("industry", "")
        canonical = normalize_industry(raw)
        if canonical:
            result.entities.append(ExtractedEntity(
                entity_type="industry", entity_name=canonical,
                normalized_name=canonical.lower(), entity_role="primary_industry",
                source_field="db_industry", extracted_value=raw,
                confidence=CONFIDENCE["db_field"], extraction_method="exact_field",
                industry=canonical,
            ))

    def _extract_geography(self, node: dict, result: NodeExtraction) -> None:
        raw = node.get("country", "")
        geo_type, canonical = classify_geo(raw)
        if geo_type == "country":
            region = region_for_country(canonical)
            result.entities.append(ExtractedEntity(
                entity_type="country", entity_name=_display_name(canonical),
                normalized_name=canonical, entity_role="country",
                source_field="db_country", extracted_value=raw,
                confidence=CONFIDENCE["db_field"],
                extraction_method="exact_field" if raw.lower() == canonical else "alias",
                region=region, country=canonical,
            ))
            if region:
                result.entities.append(ExtractedEntity(
                    entity_type="region", entity_name=region,
                    normalized_name=region.lower(), entity_role="region",
                    source_field="db_country", extracted_value=raw,
                    confidence=CONFIDENCE["region_from_country"],
                    extraction_method="derived", region=region,
                ))
                result.region_backfill = region
        elif geo_type == "region":
            # Day 1 audit finding #3: scope value stored in the country column.
            # The DB field may also simply be wrong (dry-run finding: UAE
            # report stored country='global') — check the title lead for a
            # real country before settling for the scope region.
            title_country = _country_from_title(node.get("title", ""))
            if title_country:
                region = region_for_country(title_country)
                result.entities.append(ExtractedEntity(
                    entity_type="country", entity_name=_display_name(title_country),
                    normalized_name=title_country, entity_role="country",
                    source_field="title", extracted_value=node.get("title", ""),
                    confidence=CONFIDENCE["country_from_title"],
                    extraction_method="pattern",
                    region=region, country=title_country,
                ))
                if region:
                    result.entities.append(ExtractedEntity(
                        entity_type="region", entity_name=region,
                        normalized_name=region.lower(), entity_role="region",
                        source_field="title", extracted_value=node.get("title", ""),
                        confidence=CONFIDENCE["country_from_title"],
                        extraction_method="derived", region=region,
                    ))
                    result.region_backfill = region
            else:
                result.entities.append(ExtractedEntity(
                    entity_type="region", entity_name=canonical,
                    normalized_name=canonical.lower(), entity_role="region",
                    source_field="db_country", extracted_value=raw,
                    confidence=CONFIDENCE["region_from_scope"],
                    extraction_method="alias", region=canonical,
                ))
                result.region_backfill = canonical

    def _extract_market(self, node: dict, result: NodeExtraction) -> None:
        geo_words = _GEO_LEXICON  # strip any known geography, not just the page's own
        title_market = extract_market_from_title(node.get("title", ""), geo_words)
        h1_market = extract_market_from_title(node.get("h1", ""), geo_words)

        if title_market:
            confidence = CONFIDENCE["market_title_base"]
            sources = ["title"]
            if h1_market and normalize_market_name(h1_market) == normalize_market_name(title_market):
                confidence += CONFIDENCE["market_h1_agreement"]
                sources.append("h1")
        elif h1_market:
            # Title extraction failed (empty/corrupted, e.g. a "nan"-poisoned
            # title) but H1 independently produced a usable market name —
            # use it as the primary source rather than dropping the page's
            # market entirely.
            title_market = h1_market
            confidence = CONFIDENCE["market_title_base"]
            sources = ["h1"]
        else:
            return
        # Independent URL-slug agreement: every content word of the market
        # name (minus 'market') appears in the slug
        slug = urlsplit(node["url"]).path.lower()
        market_words = [
            w for w in normalize_market_name(title_market).split() if w != "market"
        ]
        if market_words and all(w in slug for w in market_words):
            confidence += CONFIDENCE["market_slug_agreement"]
            sources.append("url_slug")
        confidence = min(confidence, CONFIDENCE["market_cap"])

        industry = next(
            (e.entity_name for e in result.entities if e.entity_type == "industry"), ""
        )
        country = next(
            (e.normalized_name for e in result.entities if e.entity_type == "country"), ""
        )
        region = next(
            (e.entity_name for e in result.entities if e.entity_type == "region"), ""
        )
        result.entities.append(ExtractedEntity(
            entity_type="market", entity_name=title_market,
            normalized_name=normalize_market_name(title_market),
            entity_role="primary_market", source_field="+".join(sources),
            extracted_value=node.get("title", ""), confidence=round(confidence, 2),
            extraction_method="pattern",
            industry=industry, country=country, region=region,
        ))
        result.market_backfill = title_market

    def _extract_time_period(self, node: dict, result: NodeExtraction) -> None:
        match = _YEAR_RANGE.search(node.get("title", "") or "")
        if match:
            period = f"{match.group(1)}-{match.group(2)}"
            result.entities.append(ExtractedEntity(
                entity_type="time_period", entity_name=period,
                normalized_name=period, entity_role="time_period",
                source_field="title", extracted_value=match.group(0),
                confidence=CONFIDENCE["time_period_title"],
                extraction_method="pattern",
            ))

    # ── run ─────────────────────────────────────────────────────────────────

    def run(self, limit=None, dry_run=False):
        """Extract for all active nodes; write DB unless dry_run.
        Returns (results, summary)."""
        nodes = self.load_nodes(limit)
        if not nodes:
            raise RuntimeError("No active content_nodes found")
        print(f"Agent 2 — Entity Extraction | run {self.run_id[:8]}")
        print(f"Processing {len(nodes)} active nodes (dry_run={dry_run})...")
        started = time.perf_counter()
        results = [self.extract_node(node) for node in nodes]
        elapsed = round(time.perf_counter() - started, 2)
        summary = self._summary(results, elapsed, dry_run)
        if not dry_run:
            self._write_database(results)
        return results, summary

    # ── write ───────────────────────────────────────────────────────────────

    def _write_database(self, results: list[NodeExtraction]) -> None:
        """Single-transaction write of entities, mappings, backfills and logs."""
        successful = [r for r in results if not r.error]
        if not successful:
            raise RuntimeError("No successful extractions; database not updated")
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")

            # Existing entities (dedup across runs — idempotent re-runs)
            entity_ids: dict[tuple[str, str], str] = {
                (row[0], row[1]): row[2]
                for row in conn.execute(
                    "SELECT normalized_name, entity_type, entity_id FROM content_entities"
                )
            }

            for result in successful:
                for ent in result.entities:
                    key = (ent.normalized_name, ent.entity_type)
                    entity_id = entity_ids.get(key)
                    if entity_id is None:
                        entity_id = str(uuid.uuid4())
                        entity_ids[key] = entity_id
                        conn.execute(
                            """INSERT INTO content_entities
                               (entity_id, entity_name, entity_type, normalized_name,
                                aliases, industry, country, region, confidence_score,
                                created_at, updated_at)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                            (entity_id, ent.entity_name, ent.entity_type,
                             ent.normalized_name, "", ent.industry, ent.country,
                             ent.region, ent.confidence, now, now),
                        )
                    else:
                        # Keep the highest confidence ever observed
                        conn.execute(
                            """UPDATE content_entities
                               SET confidence_score = MAX(confidence_score, ?),
                                   updated_at = ?
                               WHERE entity_id = ?""",
                            (ent.confidence, now, entity_id),
                        )
                    conn.execute(
                        """INSERT INTO node_entities
                           (node_entity_id, node_id, entity_id, entity_role,
                            source_field, extracted_value, normalized_value,
                            confidence_score, extraction_method, status,
                            created_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT (node_id, entity_id, entity_role)
                           DO UPDATE SET
                               source_field = excluded.source_field,
                               extracted_value = excluded.extracted_value,
                               normalized_value = excluded.normalized_value,
                               confidence_score = excluded.confidence_score,
                               extraction_method = excluded.extraction_method,
                               updated_at = excluded.updated_at""",
                        (str(uuid.uuid4()), result.node_id, entity_id,
                         ent.entity_role, ent.source_field, ent.extracted_value,
                         ent.normalized_name, ent.confidence,
                         ent.extraction_method, "extracted", now, now),
                    )

                if result.market_backfill or result.region_backfill:
                    # Backfill means fill-if-empty: a re-run must never
                    # overwrite a value a human may have corrected by hand
                    # (review finding). Extraction improvements reach these
                    # columns only via the correction workflow.
                    conn.execute(
                        """UPDATE content_nodes SET
                           market = CASE WHEN ? != '' AND (market IS NULL OR market = '')
                                         THEN ? ELSE market END,
                           region = CASE WHEN ? != '' AND (region IS NULL OR region = '')
                                         THEN ? ELSE region END,
                           updated_at = ?
                           WHERE node_id = ?""",
                        (result.market_backfill, result.market_backfill,
                         result.region_backfill, result.region_backfill,
                         now, result.node_id),
                    )

            for result in results:
                conn.execute(
                    """INSERT INTO entity_extraction_logs
                       (run_id, node_id, operation, status, entities_found,
                        low_confidence_count, error, notes, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (self.run_id, result.node_id, "entity_extraction",
                     "failed" if result.error else "success",
                     len(result.entities), result.low_confidence_count,
                     result.error or None,
                     "Agent 2 metadata-only deterministic extraction", now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── report ──────────────────────────────────────────────────────────────

    def _summary(self, results, elapsed, dry_run):
        successful = [r for r in results if not r.error]
        by_type: dict[str, int] = {}
        unique_entities: set[tuple[str, str]] = set()
        low_confidence = 0
        for result in successful:
            for ent in result.entities:
                by_type[ent.entity_type] = by_type.get(ent.entity_type, 0) + 1
                unique_entities.add((ent.normalized_name, ent.entity_type))
                if ent.low_confidence:
                    low_confidence += 1
        total = len(results)
        with_any = sum(1 for r in successful if r.entities)
        with_geo = sum(
            1 for r in successful
            if any(e.entity_type in ("country", "region") for e in r.entities)
        )
        with_ind_or_market = sum(
            1 for r in successful
            if any(e.entity_type in ("industry", "market") for e in r.entities)
        )
        with_market = sum(
            1 for r in successful
            if any(e.entity_type == "market" for e in r.entities)
        )
        pct = lambda n: round(100.0 * n / total, 1) if total else 0.0
        return {
            "run_id": self.run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "nodes_processed": total,
            "nodes_failed": len(results) - len(successful),
            "elapsed_seconds": elapsed,
            "entity_mappings_by_type": by_type,
            "unique_entities": len(unique_entities),
            "low_confidence_mappings": low_confidence,
            "coverage": {
                "pages_with_any_entity_pct": pct(with_any),
                "pages_with_geography_pct": pct(with_geo),
                "pages_with_industry_or_market_pct": pct(with_ind_or_market),
                "pages_with_market_pct": pct(with_market),
            },
            "targets": {
                "pages_with_any_entity_pct": 95.0,
                "pages_with_geography_pct": 90.0,
                "pages_with_industry_or_market_pct": 80.0,
            },
            "methodology": {
                "sources": "stored metadata only: db industry/country, title, h1, url slug",
                "normalization": "config/taxonomy.py deterministic rules",
                "confidence": CONFIDENCE,
                "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
                "deferred": "company/product/technology/regulation/claim/evidence "
                            "entity types require body content (later phase)",
            },
        }


def write_report(results, summary, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    pages = [
        {
            "node_id": r.node_id, "url": r.url, "content_type": r.content_type,
            "error": r.error,
            "market_backfill": r.market_backfill,
            "region_backfill": r.region_backfill,
            "entities": [
                {
                    "type": e.entity_type, "name": e.entity_name,
                    "normalized": e.normalized_name, "role": e.entity_role,
                    "source": e.source_field, "confidence": e.confidence,
                    "method": e.extraction_method,
                    "low_confidence": e.low_confidence,
                }
                for e in r.entities
            ],
        }
        for r in results
    ]
    output.write_text(
        json.dumps({"summary": summary, "pages": pages}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("entity_extraction_agent")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_DIR / "entity_extraction_agent.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--report")
    args = parser.parse_args(argv)

    agent = EntityExtractionAgent(args.db, configure_logging())
    report = Path(args.report) if args.report else (
        REPORT_DIR / f"entity_extraction_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    try:
        results, summary = agent.run(args.limit, args.dry_run)
        write_report(results, summary, report)
    except Exception as exc:
        logging.getLogger("entity_extraction_agent").exception("Agent failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nCompleted in {summary['elapsed_seconds']}s")
    print(f"Nodes: {summary['nodes_processed']} ({summary['nodes_failed']} failed)")
    print(f"Unique entities: {summary['unique_entities']}")
    print(f"Mappings by type: {summary['entity_mappings_by_type']}")
    print(f"Low-confidence mappings: {summary['low_confidence_mappings']}")
    for name, value in summary["coverage"].items():
        target = summary["targets"].get(name)
        marker = ""
        if target is not None:
            marker = "  [OK]" if value >= target else f"  [BELOW {target}%]"
        print(f"{name}: {value}%{marker}")
    print(f"Report: {report}")
    print("Database update: skipped (dry run)" if summary["dry_run"]
          else "Database update: committed")
    return 0 if summary["nodes_failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
