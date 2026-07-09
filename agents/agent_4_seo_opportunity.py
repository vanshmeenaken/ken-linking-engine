"""Agent 4 — SEO Opportunity (master PRD §13.4, Phase 2 foundation).

Deterministic detector that turns the Phase 1/2 intelligence into a queue of
actionable SEO opportunities, and writes a per-page search_opportunity_score
(a content_nodes column that existed since Phase 1 but was never populated —
it becomes the pre-GSC placeholder that real position-4-20 data will refine
once Search Console credentials arrive).

Opportunity types (master PRD §13.4 / Phase 2 plan), all computable now:
    orphan_page               0 incoming internal links
    underlinked_page          1-2 incoming links
    high_priority_underlinked underlinked AND high authority/decision intent
    missing_market_entity     active page with no market entity
    missing_geo_entity        active page with no country/region entity
    missing_relationships     active page with no relationship edges
    entity_low_confidence     page has a sub-0.5 confidence entity mapping
    stale_metadata            missing title / h1 / meta description

Not emitted (documented, not silently dropped):
  - global_local_gap: on this dataset only 2 markets have both a global and
    a local page (already interlinked by Agent 3's global_local edges); the
    other ~370 markets are single-geography, so a "no counterpart" flag fires
    for nearly every page and is content-creation (not linking) work this
    system can't action. Re-add with a sharper definition when the catalog
    has real global/local market pairs.
  - position_4_to_20, high_impression_low_ctr: need GSC ranking/impression
    data — activate when Search Console credentials exist.

Usage:
    python agents/agent_4_seo_opportunity.py --dry-run
    python agents/agent_4_seo_opportunity.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
REPORT_DIR = ROOT / "reports"

# Each opportunity type's weight toward search_opportunity_score (0-1).
# Higher = a bigger, more valuable SEO gap on that page.
OPPORTUNITY_WEIGHTS = {
    "orphan_page": 1.0,
    "high_priority_underlinked": 0.9,
    "underlinked_page": 0.6,
    "missing_relationships": 0.6,
    "missing_market_entity": 0.4,
    "missing_geo_entity": 0.3,
    "entity_low_confidence": 0.2,
    "stale_metadata": 0.3,
}

DEFERRED_TYPES = [
    "position_4_to_20 — needs GSC ranking data",
    "high_impression_low_ctr — needs GSC impressions/CTR data",
]


@dataclass
class Opportunity:
    node_id: str
    opportunity_type: str
    priority: str          # high | medium | low
    reason: str
    evidence: dict
    seo_score: float       # 0-1, this opportunity's own weight
    business_score: float  # 0-1, from business_priority if available else 0


class SEOOpportunityAgent:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = Path(db_path)
        self.run_id = str(uuid.uuid4())

    def _connect_ro(self):
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def detect(self) -> list[Opportunity]:
        conn = self._connect_ro()
        try:
            nodes = conn.execute(
                "SELECT node_id, url, content_type, title, h1, meta_description, "
                "internal_links_in, orphan_status, page_authority_score, "
                "intent_stage, global_or_local, business_priority "
                "FROM content_nodes WHERE status='active'"
            ).fetchall()

            ent_types: dict[str, set[str]] = {}
            low_conf: set[str] = set()
            for r in conn.execute(
                """SELECT ne.node_id, ce.entity_type, ne.confidence_score
                   FROM node_entities ne JOIN content_entities ce
                   ON ce.entity_id = ne.entity_id WHERE ne.status != 'rejected'"""
            ):
                ent_types.setdefault(r["node_id"], set()).add(r["entity_type"])
                if r["confidence_score"] is not None and r["confidence_score"] < 0.5:
                    low_conf.add(r["node_id"])

            linked = {
                r[0] for r in conn.execute(
                    "SELECT source_node_id FROM relationship_edges "
                    "UNION SELECT target_node_id FROM relationship_edges"
                )
            }
        finally:
            conn.close()

        opps: list[Opportunity] = []
        for n in nodes:
            nid = n["node_id"]
            types = ent_types.get(nid, set())
            biz = self._business_score(n["business_priority"])

            if n["orphan_status"] == "orphan":
                opps.append(self._mk(nid, "orphan_page", "high",
                    "Page has zero incoming internal links",
                    {"internal_links_in": n["internal_links_in"]}, biz))
            elif n["orphan_status"] == "under_linked":
                # A commercial-intent (decision) page being underlinked is
                # inherently high priority — that's where internal links move
                # the needle. (An authority-threshold gate was tried and
                # killed the signal: underlinked decision pages top out at
                # authority 33, so no fixed high cutoff fires. Intent is the
                # right proxy for "high value" until Agent 5 business
                # priority exists.)
                if n["intent_stage"] == "decision":
                    opps.append(self._mk(nid, "high_priority_underlinked", "high",
                        "Commercial-intent page with only 1-2 incoming links",
                        {"internal_links_in": n["internal_links_in"],
                         "authority": n["page_authority_score"]}, biz))
                else:
                    opps.append(self._mk(nid, "underlinked_page", "medium",
                        "Page has only 1-2 incoming internal links",
                        {"internal_links_in": n["internal_links_in"]}, biz))

            if "market" not in types:
                opps.append(self._mk(nid, "missing_market_entity", "medium",
                    "No market entity extracted for this page",
                    {"entity_types": sorted(types)}, biz))
            if not ({"country", "region"} & types):
                opps.append(self._mk(nid, "missing_geo_entity", "low",
                    "No country or region entity extracted", {}, biz))
            if nid not in linked:
                opps.append(self._mk(nid, "missing_relationships", "medium",
                    "Page has no relationship edges to any other page", {}, biz))
            if nid in low_conf:
                opps.append(self._mk(nid, "entity_low_confidence", "low",
                    "Page has at least one low-confidence entity mapping (<0.5)",
                    {}, biz))
            if not all((n["title"], n["h1"], n["meta_description"])):
                missing = [c for c in ("title", "h1", "meta_description") if not n[c]]
                opps.append(self._mk(nid, "stale_metadata", "low",
                    f"Missing metadata: {', '.join(missing)}", {"missing": missing}, biz))
        return opps

    @staticmethod
    def _business_score(band: str | None) -> float:
        return {"High": 1.0, "Medium": 0.6, "Low": 0.3}.get(band or "", 0.0)

    def _mk(self, node_id, otype, priority, reason, evidence, biz) -> Opportunity:
        return Opportunity(
            node_id=node_id, opportunity_type=otype, priority=priority,
            reason=reason, evidence=evidence,
            seo_score=OPPORTUNITY_WEIGHTS[otype], business_score=biz,
        )

    def run(self, dry_run=False):
        opps = self.detect()
        # Per-page search_opportunity_score = the strongest opportunity weight
        # on that page (0-1), so a page's score reflects its biggest gap.
        page_score: dict[str, float] = {}
        for o in opps:
            page_score[o.node_id] = max(page_score.get(o.node_id, 0.0), o.seo_score)
        summary = self._summary(opps, page_score, dry_run)
        if not dry_run:
            self._write(opps, page_score)
        return opps, summary

    def _write(self, opps, page_score):
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            # Refresh this agent's opportunity rows: clear old open ones first
            # (idempotent re-run) but preserve any a human moved off 'open'.
            conn.execute("DELETE FROM seo_opportunities WHERE status='open'")
            for o in opps:
                conn.execute(
                    """INSERT INTO seo_opportunities
                       (opportunity_id, node_id, opportunity_type, priority,
                        reason, evidence, seo_score, business_score, status,
                        created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,'open',?,?)
                       ON CONFLICT (node_id, opportunity_type) DO UPDATE SET
                           priority=excluded.priority, reason=excluded.reason,
                           evidence=excluded.evidence, seo_score=excluded.seo_score,
                           business_score=excluded.business_score,
                           updated_at=excluded.updated_at""",
                    (str(uuid.uuid4()), o.node_id, o.opportunity_type, o.priority,
                     o.reason, json.dumps(o.evidence), o.seo_score, o.business_score,
                     now, now),
                )
            for node_id, score in page_score.items():
                conn.execute(
                    "UPDATE content_nodes SET search_opportunity_score=?, updated_at=? "
                    "WHERE node_id=?",
                    (round(score, 3), now, node_id),
                )
            conn.execute(
                """INSERT INTO entity_extraction_logs
                   (run_id, node_id, operation, status, entities_found,
                    low_confidence_count, error, notes, created_at)
                   VALUES (?,NULL,'seo_opportunity','success',?,0,NULL,?,?)""",
                (self.run_id, len(opps),
                 f"Agent 4: {len(opps)} opportunities across {len(page_score)} pages", now),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _summary(self, opps, page_score, dry_run):
        by_type: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for o in opps:
            by_type[o.opportunity_type] = by_type.get(o.opportunity_type, 0) + 1
            by_priority[o.priority] = by_priority.get(o.priority, 0) + 1
        return {
            "run_id": self.run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "total_opportunities": len(opps),
            "pages_with_opportunity": len(page_score),
            "by_type": by_type,
            "by_priority": by_priority,
            "deferred_types": DEFERRED_TYPES,
        }


def write_report(opps, summary, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "summary": summary,
        "opportunities": [
            {"node_id": o.node_id, "type": o.opportunity_type, "priority": o.priority,
             "reason": o.reason, "seo_score": o.seo_score, "business_score": o.business_score}
            for o in opps
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report")
    args = parser.parse_args(argv)

    agent = SEOOpportunityAgent(args.db)
    report = Path(args.report) if args.report else (
        REPORT_DIR / f"seo_opportunity_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    opps, summary = agent.run(args.dry_run)
    write_report(opps, summary, report)

    print(f"Total opportunities: {summary['total_opportunities']}")
    print(f"Pages with an opportunity: {summary['pages_with_opportunity']}")
    print(f"By type: {summary['by_type']}")
    print(f"By priority: {summary['by_priority']}")
    print(f"Report: {report}")
    print("Database update: skipped (dry run)" if dry_run_flag(summary)
          else "Database update: committed")
    return 0


def dry_run_flag(summary):
    return summary["dry_run"]


if __name__ == "__main__":
    raise SystemExit(main())
