"""Agent 3 — Relationship Mapping (Phase 2, Day 6 / Jul 9 of the final PRD).

Reads the entities Agent 2 extracted (node_entities + content_entities) and
page metadata (content_nodes) to create typed, scored, directed edges in
relationship_edges. Deterministic rule engine — no LLM calls, no semantic
similarity yet (that lands Day 7/Jul 10 alongside full edge scoring; this
agent leaves semantic_similarity_score NULL and fills entity_overlap_score,
geo_match_score, market_match_score, confidence_score).

Edge types built (master PRD §15, the ones computable from Phase 2 data —
see relationship coverage matrix in source_of_truth/PHASE_2_FINAL_PRD.md):
  - same_market         two pages sharing a market entity
  - country_region      a country page <-> pages in its region
  - global_local        same market, one global-scoped page + one local page
  - industry_market      a market entity -> its parent industry entity
  - report_article_support / case_study_support
                         article/case-study sharing a MARKET entity with a
                         report (industry+country alone is not enough — see
                         precision-first note below)

same_industry is deliberately NOT built as raw page pairs: with industries up
to ~100 pages wide, all-pairs would be thousands of low-value edges. Industry
co-membership is available via node_entities directly (no edge needed to
answer "what else is in Healthcare"); an edge is only created when something
more specific also matches (market, or industry+country for support edges).

Precision-first (project quality bar): every edge either shares a market, or
shares industry+geography with an explicit content-type reason — never a bare
same-industry guess. When unsure, no edge, matching "never pad" from the
interlink quality bar.

Usage:
    python agents/agent_3_relationship_mapping.py --dry-run
    python agents/agent_3_relationship_mapping.py --limit 25 --dry-run
    python agents/agent_3_relationship_mapping.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis import llm_subject_judge
from analysis.tfidf_similarity import build_corpus, cosine
from analysis.subject_similarity import subject_similarity

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
REPORT_DIR = ROOT / "reports"
LOG_DIR = ROOT / "logs"

# Confidence model — deterministic, explainable (master PRD §8/§36)
CONFIDENCE = {
    "same_market": 0.90,          # both pages independently mapped to the same market entity
    "country_region": 0.65,       # region-hub <-> local page, same industry only
                                    # (broader signal than same_market — no subject-
                                    # level match, industry co-membership only)
    "global_local": 0.80,         # same market, global/local scope differs
    "industry_market": 0.85,      # market -> parent industry, both from trusted extraction
    "report_article_support": 0.75,  # article shares market with a report
    "case_study_support": 0.75,      # case study shares market with a report
    "adjacent_market": 0.60,         # same industry, different market, high text similarity
}

MAX_SAME_MARKET_PAGES_PER_ENTITY = 12  # precision guard: skip hub-like markets

# adjacent_market / country_region tuning. Both now gated on
# subject_similarity() (Shrey's 4-layer method, Layers 2+3 — see
# analysis/subject_similarity.py) instead of plain embedding cosine.
# Threshold re-validated against live data after the swap: replaying it over
# the 168 existing adjacent_market pairs and 551 existing country_region
# pairs, 0.25 keeps the same "genuine cross-geography subject match" band
# the original dry-run found (0.30-0.40 for strong matches like infusion
# pumps <-> insulin infusion pumps) while now correctly zeroing out pairs
# that only shared generic words/years (e.g. the reported Bone Growth
# Stimulator <-> Microscope country_region edge, both just "...Outlook to
# 2030" — old score 0.15, new score 0.002). At this bar country_region drops
# from 551 candidate pairs to ~7 genuine ones; that's the fix, not a bug —
# most of those 551 never shared a real subject, only a region + industry.
ADJACENT_SIMILARITY_THRESHOLD = 0.25
COUNTRY_REGION_SIMILARITY_THRESHOLD = 0.25
MAX_ADJACENT_PER_PAGE = 5


@dataclass
class Edge:
    source_node_id: str
    target_node_id: str
    relationship_type: str
    relationship_direction: str  # 'bidirectional' | 'source_to_target'
    confidence_score: float
    entity_overlap_score: float
    geo_match_score: float
    market_match_score: float
    reason: str
    source_entity_id: str = ""
    target_entity_id: str = ""
    semantic_similarity_score: float | None = None
    seo_value_score: float | None = None
    business_value_score: float | None = None


@dataclass
class RunResult:
    edges: list[Edge] = field(default_factory=list)
    candidates_considered: int = 0
    skipped_hub_markets: list[str] = field(default_factory=list)


class RelationshipMappingAgent:
    """Deterministic relationship-edge builder over the Phase 2 entity graph."""

    def __init__(self, db_path=DEFAULT_DB, logger=None):
        self.db_path = Path(db_path)
        self.logger = logger or logging.getLogger("relationship_mapping_agent")
        self.run_id = str(uuid.uuid4())

    # ── load ────────────────────────────────────────────────────────────────

    def _connect_ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def load_nodes(self, limit: int | None = None) -> dict[str, sqlite3.Row]:
        conn = self._connect_ro()
        try:
            sql = (
                "SELECT node_id, url, content_type, country, region, market, "
                "global_or_local FROM content_nodes WHERE status='active' "
                "ORDER BY rowid"
            )
            params: tuple = ()
            if limit is not None:
                sql += " LIMIT ?"
                params = (limit,)
            rows = conn.execute(sql, params).fetchall()
            return {row["node_id"]: row for row in rows}
        finally:
            conn.close()

    def load_node_entities(self, node_ids: set[str]) -> dict[str, list[sqlite3.Row]]:
        """entity mappings (non-rejected) per node, scoped to the loaded node set."""
        conn = self._connect_ro()
        try:
            placeholders = ",".join("?" * len(node_ids))
            rows = conn.execute(
                f"""SELECT ne.node_id, ne.entity_id, ne.entity_role,
                           ce.entity_type, ce.entity_name, ce.normalized_name,
                           ce.parent_entity_id
                    FROM node_entities ne
                    JOIN content_entities ce ON ce.entity_id = ne.entity_id
                    WHERE ne.status != 'rejected' AND ne.node_id IN ({placeholders})""",
                tuple(node_ids),
            ).fetchall()
            by_node: dict[str, list[sqlite3.Row]] = {}
            for row in rows:
                by_node.setdefault(row["node_id"], []).append(row)
            return by_node
        finally:
            conn.close()

    # ── rule engine ─────────────────────────────────────────────────────────

    def build_edges(self, limit: int | None = None) -> RunResult:
        nodes = self.load_nodes(limit)
        node_entities = self.load_node_entities(set(nodes))
        result = RunResult()

        # Index: market entity_id -> [node_ids mapped to it]
        market_pages: dict[str, list[str]] = {}
        # Index: node_id -> its market entity ids (usually 0 or 1, could be more)
        node_markets: dict[str, list[str]] = {}
        for node_id, ents in node_entities.items():
            for e in ents:
                if e["entity_type"] == "market":
                    market_pages.setdefault(e["entity_id"], []).append(node_id)
                    node_markets.setdefault(node_id, []).append(e["entity_id"])

        # Authoritative per-page scope, derived from Agent 2's *entity-level*
        # extraction (node_entities) — not the raw content_nodes.country /
        # global_or_local columns, which are Phase 1 originals and can be
        # stale (the exact case Agent 2 already fixed for one UAE page:
        # content_nodes.country stayed 'global' while node_entities correctly
        # holds country='uae'). Using the corrected facts here prevents that
        # kind of page from being mistaken for a region-wide hub page.
        scope = self._derive_scope(node_entities)
        node_industries: dict[str, set[str]] = {
            node_id: {e["normalized_name"] for e in ents if e["entity_type"] == "industry"}
            for node_id, ents in node_entities.items()
        }

        titles = self._load_titles(nodes)
        subject_corpus = build_corpus(list(titles.values()))

        result.edges.extend(self._same_market_edges(market_pages, nodes, result))
        result.edges.extend(
            self._country_region_edges(scope, node_industries, titles, subject_corpus)
        )
        result.edges.extend(self._global_local_edges(scope, node_markets))
        result.edges.extend(self._industry_market_edges(node_entities))
        result.edges.extend(self._support_edges(nodes, node_markets))
        result.edges.extend(
            self._adjacent_market_edges(node_markets, node_industries, titles, subject_corpus)
        )

        # Final scoring pass: populate semantic_similarity_score and
        # seo_value_score on every edge (business_value_score is left for
        # Agent 5, Day 3 — documented, not silently zeroed).
        self._score_edges(result.edges)
        return result

    # ── embeddings / node signals (loaded lazily, cached per run) ────────────

    def _load_embeddings(self) -> dict[str, dict[str, float]]:
        """node_id -> sparse TF-IDF vector, from semantic_embeddings."""
        if getattr(self, "_embeddings", None) is not None:
            return self._embeddings
        conn = self._connect_ro()
        try:
            self._embeddings = {
                row["node_id"]: json.loads(row["embedding_vector"])
                for row in conn.execute(
                    "SELECT node_id, embedding_vector FROM semantic_embeddings"
                )
            }
        except sqlite3.OperationalError:
            self._embeddings = {}
        finally:
            conn.close()
        return self._embeddings

    @staticmethod
    def _llm_confirms(title_a: str, title_b: str) -> bool:
        """Layer 4 final check on a candidate that already passed Layers
        2+3. Optional/credential-gated (analysis/llm_subject_judge.py) — a
        missing key or any API failure returns None, which this treats as
        "no opinion, trust the deterministic score" (True), never as a
        rejection. Only an explicit False from the LLM drops the edge."""
        return llm_subject_judge.judge(title_a, title_b) is not False

    def _load_titles(self, nodes: dict[str, sqlite3.Row]) -> dict[str, str]:
        """node_id -> subject text for subject_similarity(): title, falling
        back to h1 when title is missing or corrupted. Found live: 4 pages
        have a literal 'nan Market...' title (a scrape/parse artifact) while
        h1 holds the real title — same corruption Agent 2 already works
        around for entity extraction. Left unfixed here, those 4 pages would
        wrongly cluster with each other on the shared word 'nan'."""
        if getattr(self, "_titles", None) is not None:
            return self._titles
        conn = self._connect_ro()
        try:
            rows = conn.execute(
                "SELECT node_id, title, h1 FROM content_nodes WHERE node_id IN "
                f"({','.join('?' * len(nodes))})",
                tuple(nodes),
            ).fetchall()
        finally:
            conn.close()
        self._titles = {}
        for row in rows:
            title = row["title"] or ""
            text = row["h1"] if (not title or title.strip().lower().startswith("nan")) else title
            self._titles[row["node_id"]] = text or ""
        return self._titles

    def _load_seo_signals(self) -> dict[str, dict]:
        """node_id -> {authority (0-1), needs_links (0-1)} for seo_value_score."""
        if getattr(self, "_seo_signals", None) is not None:
            return self._seo_signals
        conn = self._connect_ro()
        try:
            rows = conn.execute(
                "SELECT node_id, page_authority_score, orphan_status "
                "FROM content_nodes WHERE status='active'"
            ).fetchall()
        finally:
            conn.close()
        max_auth = max((r["page_authority_score"] or 0.0 for r in rows), default=0.0) or 1.0
        needs = {"orphan": 1.0, "under_linked": 0.7, "normal": 0.3, "well_linked": 0.1}
        self._seo_signals = {
            r["node_id"]: {
                "authority": (r["page_authority_score"] or 0.0) / max_auth,
                "needs_links": needs.get(r["orphan_status"], 0.5),
            }
            for r in rows
        }
        return self._seo_signals

    def _adjacent_market_edges(self, node_markets, node_industries, titles, corpus) -> list[Edge]:
        """Same industry, DIFFERENT market, high SUBJECT similarity — the
        master PRD 'adjacent market' relationship (§15.1). Uses
        subject_similarity() (Shrey's 4-layer method, Layers 2+3), not plain
        embedding cosine: plain cosine let generic shared words ("market",
        "3pl", a shared forecast year) drive matches between unrelated
        subjects. The same-industry guard removes cross-industry geography
        noise; the different-market requirement makes it 'adjacent' not
        'same'; subject_similarity's tech-intersection gate additionally
        blocks compound-topic false positives ("AI in Medicine" matching
        "AI in Robotics")."""
        edges = []
        seen = set()
        market_holders = [n for n in node_markets if titles.get(n)]
        for a in market_holders:
            a_markets = set(node_markets.get(a, []))
            a_industries = node_industries.get(a, set())
            if not a_industries:
                continue
            scored = []
            for b in market_holders:
                if b == a:
                    continue
                # same industry, different market
                if not (a_industries & node_industries.get(b, set())):
                    continue
                if a_markets & set(node_markets.get(b, [])):
                    continue  # same market -> that's same_market, not adjacent
                sim = subject_similarity(corpus, titles[a], titles[b])
                if sim >= ADJACENT_SIMILARITY_THRESHOLD and self._llm_confirms(titles[a], titles[b]):
                    scored.append((sim, b))
            scored.sort(reverse=True)
            for sim, b in scored[:MAX_ADJACENT_PER_PAGE]:
                lo, hi = sorted((a, b))
                if (lo, hi, "adjacent_market") in seen:
                    continue
                seen.add((lo, hi, "adjacent_market"))
                edges.append(Edge(
                    source_node_id=lo, target_node_id=hi,
                    relationship_type="adjacent_market",
                    relationship_direction="bidirectional",
                    confidence_score=round(min(0.85, CONFIDENCE["adjacent_market"] + sim * 0.5), 2),
                    entity_overlap_score=0.5, geo_match_score=0.0,
                    market_match_score=0.0,
                    semantic_similarity_score=round(sim, 3),
                    reason=f"Same industry, different market, subject similarity {sim:.2f}",
                ))
        return edges

    def _score_edges(self, edges: list[Edge]) -> None:
        """Populate semantic_similarity_score (from embeddings) and
        seo_value_score (from the target page's authority + link need) on
        every edge. business_value_score is intentionally left None until
        Agent 5 (Day 3) computes business priority."""
        embeddings = self._load_embeddings()
        seo = self._load_seo_signals()
        for e in edges:
            if e.semantic_similarity_score is None:
                va, vb = embeddings.get(e.source_node_id), embeddings.get(e.target_node_id)
                e.semantic_similarity_score = (
                    round(cosine(va, vb), 3) if va and vb else 0.0
                )
            # SEO value of pointing at the target: high when the target has
            # real authority to gain AND currently needs incoming links.
            t = seo.get(e.target_node_id)
            if t:
                e.seo_value_score = round(
                    0.5 * t["authority"] + 0.5 * t["needs_links"], 3
                )
            else:
                e.seo_value_score = 0.0

    @staticmethod
    def _derive_scope(node_entities: dict[str, list[sqlite3.Row]]) -> dict[str, dict]:
        """Per-node scope facts from entity extraction: is_local (has a real
        country entity) and region (from the region entity, if any)."""
        scope = {}
        for node_id, ents in node_entities.items():
            has_country = any(e["entity_type"] == "country" for e in ents)
            region = next(
                (e["entity_name"] for e in ents if e["entity_type"] == "region"), ""
            )
            scope[node_id] = {"is_local": has_country, "region": region}
        return scope

    def _same_market_edges(self, market_pages, nodes, result: RunResult) -> list[Edge]:
        edges = []
        for entity_id, page_ids in market_pages.items():
            unique_pages = sorted(set(page_ids))
            result.candidates_considered += len(unique_pages) * (len(unique_pages) - 1) // 2
            if len(unique_pages) < 2:
                continue
            if len(unique_pages) > MAX_SAME_MARKET_PAGES_PER_ENTITY:
                # Precision guard: a "market" this wide is almost certainly a
                # normalization miss (too generic), not a real tight cluster.
                # Skip rather than generate a hub of low-value edges.
                result.skipped_hub_markets.append(entity_id)
                continue
            for i in range(len(unique_pages)):
                for j in range(i + 1, len(unique_pages)):
                    a, b = sorted((unique_pages[i], unique_pages[j]))
                    edges.append(Edge(
                        source_node_id=a, target_node_id=b,
                        relationship_type="same_market",
                        relationship_direction="bidirectional",
                        confidence_score=CONFIDENCE["same_market"],
                        entity_overlap_score=1.0, geo_match_score=0.0,
                        market_match_score=1.0,
                        source_entity_id=entity_id, target_entity_id=entity_id,
                        reason=f"Both pages map to the same market entity ({entity_id[:8]})",
                    ))
        return edges

    def _country_region_edges(self, scope: dict[str, dict],
                              node_industries: dict[str, set[str]],
                              titles: dict[str, str], corpus) -> list[Edge]:
        """Region-hub page(s) linked to local-country page(s) in that region,
        gated by a shared industry AND subject similarity.

        Geography + industry alone is not enough here — a real live example
        Shrey flagged: "North America Bone Growth Stimulator Market" linked
        to "USA Microscope Market", both just "Healthcare"/"Medical Devices"
        in the same region. Auditing all 551 pre-fix country_region edges
        found under 2% (6/551) scored >= 0.30 on real subject overlap; the
        rest shared only region + broad industry, exactly this failure mode.
        Requiring subject_similarity() (Shrey's 4-layer method, Layers 2+3)
        on top of the industry guard keeps the project's precision-first bar
        (same reasoning that removed the industry+country fallback from
        case_study_support): the master PRD's own definition of this edge
        type (§15.2, geography hierarchy) is still honored, but scoped to
        pages a reader in the region would actually find related.

        Scope (is_local / region) comes from Agent 2's entity extraction, not
        raw content_nodes columns — see build_edges() for why.
        """
        edges = []
        by_region_local: dict[str, list[str]] = {}
        region_hub_nodes: dict[str, list[str]] = {}
        for node_id, s in scope.items():
            if not s["region"]:
                continue
            if s["is_local"]:
                by_region_local.setdefault(s["region"], []).append(node_id)
            else:
                # No specific country entity, but a region entity exists —
                # a genuine region/scope-level page (e.g. a "Global" or
                # "GCC"-tagged report), not a mislabeled local page.
                region_hub_nodes.setdefault(s["region"], []).append(node_id)
        for region, hubs in region_hub_nodes.items():
            locals_in_region = by_region_local.get(region, [])
            if not locals_in_region:
                continue
            for hub in hubs:
                hub_industries = node_industries.get(hub, set())
                if not hub_industries or not titles.get(hub):
                    continue
                scored = []
                for local_id in locals_in_region:
                    if not (node_industries.get(local_id, set()) & hub_industries):
                        continue
                    if not titles.get(local_id):
                        continue
                    sim = subject_similarity(corpus, titles[hub], titles[local_id])
                    if (sim >= COUNTRY_REGION_SIMILARITY_THRESHOLD
                            and self._llm_confirms(titles[hub], titles[local_id])):
                        scored.append((sim, local_id))
                scored.sort(reverse=True)
                for sim, local_id in scored[:MAX_SAME_MARKET_PAGES_PER_ENTITY]:
                    a, b = sorted((hub, local_id))
                    edges.append(Edge(
                        source_node_id=a, target_node_id=b,
                        relationship_type="country_region",
                        relationship_direction="bidirectional",
                        confidence_score=round(
                            min(0.85, CONFIDENCE["country_region"] + sim * 0.3), 2
                        ),
                        entity_overlap_score=0.5, geo_match_score=1.0,
                        market_match_score=0.0,
                        semantic_similarity_score=round(sim, 3),
                        reason=f"Region-scope page and a local page both in {region}, "
                               f"same industry, subject similarity {sim:.2f}",
                    ))
        return edges

    def _global_local_edges(self, scope: dict[str, dict], node_markets) -> list[Edge]:
        """Same market, one page global/region-scoped, one local (country) scoped."""
        edges = []
        seen = set()
        for market_id, holder_nodes in self._invert(node_markets).items():
            globals_ = [n for n in holder_nodes if not scope.get(n, {}).get("is_local")]
            locals_ = [n for n in holder_nodes if scope.get(n, {}).get("is_local")]
            for g in globals_[:MAX_SAME_MARKET_PAGES_PER_ENTITY]:
                for l in locals_[:MAX_SAME_MARKET_PAGES_PER_ENTITY]:
                    a, b = sorted((g, l))
                    key = (a, b, "global_local")
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append(Edge(
                        source_node_id=a, target_node_id=b,
                        relationship_type="global_local",
                        relationship_direction="bidirectional",
                        confidence_score=CONFIDENCE["global_local"],
                        entity_overlap_score=1.0, geo_match_score=0.5,
                        market_match_score=1.0,
                        source_entity_id=market_id, target_entity_id=market_id,
                        reason="Same market; one page is global-scope, the other local-scope",
                    ))
        return edges

    @staticmethod
    def _invert(node_markets: dict[str, list[str]]) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for node_id, market_ids in node_markets.items():
            for m in market_ids:
                out.setdefault(m, []).append(node_id)
        return out

    def _industry_market_edges(self, node_entities) -> list[Edge]:
        """Entity-to-entity edge: a market entity belongs to its industry
        entity, when a page independently carries both (co-occurrence
        evidence — never invented)."""
        edges = []
        seen = set()
        for node_id, ents in node_entities.items():
            markets = [e for e in ents if e["entity_type"] == "market"]
            industries = [e for e in ents if e["entity_type"] == "industry"]
            for m in markets:
                for ind in industries:
                    key = (m["entity_id"], ind["entity_id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append(Edge(
                        source_node_id=node_id, target_node_id=node_id,
                        relationship_type="industry_market",
                        relationship_direction="source_to_target",
                        confidence_score=CONFIDENCE["industry_market"],
                        entity_overlap_score=1.0, geo_match_score=0.0,
                        market_match_score=1.0,
                        source_entity_id=m["entity_id"], target_entity_id=ind["entity_id"],
                        reason=f"'{m['entity_name']}' co-occurs with industry "
                               f"'{ind['entity_name']}' on this page",
                    ))
        return edges

    def _support_edges(self, nodes, node_markets) -> list[Edge]:
        """article/case_study -> report, ONLY when they share a market entity.

        Precision-first by design (project quality bar: same-industry alone
        is never enough, never pad, leave it out when unsure). An earlier
        version also matched on industry+country alone as a fallback; dry-run
        inspection showed that pairs completely unrelated pages (a Sports
        Equipment case study linked to an Online Grocery Market report,
        joined only by "Consumer Products & Retail" + "India") — removed.
        """
        edges = []
        reports = [n for n, r in nodes.items() if r["content_type"] == "report"]
        supporters = [
            (n, r["content_type"]) for n, r in nodes.items()
            if r["content_type"] in ("article", "case_study")
        ]
        report_markets = {r: set(node_markets.get(r, [])) for r in reports}
        seen = set()
        for supporter_id, ctype in supporters:
            rel_type = ("report_article_support" if ctype == "article"
                       else "case_study_support")
            supporter_markets = set(node_markets.get(supporter_id, []))
            if not supporter_markets:
                continue
            matched = []
            for report_id in reports:
                if report_id == supporter_id:
                    continue
                shared_market = supporter_markets & report_markets.get(report_id, set())
                if shared_market:
                    matched.append((report_id, next(iter(shared_market))))
            for report_id, market_id in matched[:3]:
                key = (supporter_id, report_id, rel_type)
                if key in seen:
                    continue
                seen.add(key)
                edges.append(Edge(
                    source_node_id=supporter_id, target_node_id=report_id,
                    relationship_type=rel_type,
                    relationship_direction="source_to_target",
                    confidence_score=CONFIDENCE[rel_type],
                    entity_overlap_score=1.0, geo_match_score=0.0,
                    market_match_score=1.0,
                    source_entity_id=market_id, target_entity_id=market_id,
                    reason=f"{ctype.replace('_', ' ').title()} shares its market with this report",
                ))
        return edges

    # ── run ─────────────────────────────────────────────────────────────────

    def run(self, limit=None, dry_run=False):
        started = time.perf_counter()
        self._stale_removed = 0
        result = self.build_edges(limit)
        elapsed = round(time.perf_counter() - started, 2)
        summary = self._summary(result, elapsed, dry_run)
        if not dry_run:
            self._write_database(result.edges)
        summary["stale_edges_removed"] = self._stale_removed
        return result, summary

    def _write_database(self, edges: list[Edge]) -> None:
        if not edges:
            return
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            written = 0
            for e in edges:
                conn.execute(
                    """INSERT INTO relationship_edges
                       (edge_id, source_node_id, target_node_id, source_entity_id,
                        target_entity_id, relationship_type, relationship_direction,
                        confidence_score, semantic_similarity_score, entity_overlap_score,
                        geo_match_score, market_match_score, business_value_score,
                        seo_value_score, created_by, status, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'agent_3','pending',?,?)
                       ON CONFLICT (source_node_id, target_node_id, relationship_type)
                       DO UPDATE SET
                           confidence_score = excluded.confidence_score,
                           semantic_similarity_score = excluded.semantic_similarity_score,
                           entity_overlap_score = excluded.entity_overlap_score,
                           geo_match_score = excluded.geo_match_score,
                           market_match_score = excluded.market_match_score,
                           seo_value_score = excluded.seo_value_score,
                           updated_at = excluded.updated_at""",
                    (str(uuid.uuid4()), e.source_node_id, e.target_node_id,
                     e.source_entity_id or None, e.target_entity_id or None,
                     e.relationship_type, e.relationship_direction,
                     e.confidence_score, e.semantic_similarity_score,
                     e.entity_overlap_score, e.geo_match_score, e.market_match_score,
                     e.business_value_score, e.seo_value_score, now, now),
                )
                written += 1

            # Remove stale edges: ones this agent created on a previous run
            # that its current logic no longer produces (e.g. an edge built
            # when a page had a different, since-corrected industry). Without
            # this, re-running after source-data changes leaves orphaned edges
            # in the table (verified: an industry-cleanup re-run left 94 stale
            # edges). Only 'pending' agent_3 edges are eligible — anything a
            # human has reviewed (approved/rejected/corrected) is preserved.
            current_keys = {
                (e.source_node_id, e.target_node_id, e.relationship_type)
                for e in edges
            }
            stale = [
                row[0] for row in conn.execute(
                    "SELECT edge_id, source_node_id, target_node_id, relationship_type "
                    "FROM relationship_edges "
                    "WHERE created_by='agent_3' AND status='pending'"
                )
                if (row[1], row[2], row[3]) not in current_keys
            ]
            for edge_id in stale:
                conn.execute(
                    "DELETE FROM relationship_edges WHERE edge_id=?", (edge_id,)
                )

            conn.execute(
                """INSERT INTO entity_extraction_logs
                   (run_id, node_id, operation, status, entities_found,
                    low_confidence_count, error, notes, created_at)
                   VALUES (?,NULL,'relationship_mapping','success',?,0,NULL,?,?)""",
                (self.run_id, written,
                 f"Agent 3 deterministic edges: {written} written/updated, "
                 f"{len(stale)} stale removed", now),
            )
            conn.commit()
            self._stale_removed = len(stale)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _summary(self, result: RunResult, elapsed, dry_run) -> dict:
        by_type: dict[str, int] = {}
        for e in result.edges:
            by_type[e.relationship_type] = by_type.get(e.relationship_type, 0) + 1
        return {
            "run_id": self.run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "elapsed_seconds": elapsed,
            "candidate_pairs_considered": result.candidates_considered,
            "edges_created": len(result.edges),
            "edges_by_type": by_type,
            "hub_markets_skipped": len(result.skipped_hub_markets),
            "methodology": {
                "same_market": "both pages independently mapped to the same market entity",
                "country_region": "region-scope page linked to local pages in that region",
                "global_local": "same market, one page global-scope, one local-scope",
                "industry_market": "entity-to-entity: market observed co-occurring with an industry",
                "report_article_support / case_study_support": "article/case-study "
                    "shares a market entity with a report (industry+country alone "
                    "is deliberately not enough — precision-first per project quality bar)",
                "same_industry": "deliberately not built as page-pair edges — "
                    "available via node_entities directly; would be thousands "
                    "of low-value pairs for wide industries",
                "precision_guard": f"markets with more than "
                    f"{MAX_SAME_MARKET_PAGES_PER_ENTITY} pages are skipped as "
                    "likely normalization misses, not real tight clusters",
            },
        }


def write_report(result: RunResult, summary: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    edges_out = [
        {
            "source_node_id": e.source_node_id, "target_node_id": e.target_node_id,
            "relationship_type": e.relationship_type,
            "relationship_direction": e.relationship_direction,
            "confidence_score": e.confidence_score,
            "semantic_similarity_score": e.semantic_similarity_score,
            "entity_overlap_score": e.entity_overlap_score,
            "geo_match_score": e.geo_match_score,
            "market_match_score": e.market_match_score,
            "seo_value_score": e.seo_value_score,
            "business_value_score": e.business_value_score,
            "reason": e.reason,
        }
        for e in result.edges
    ]
    output.write_text(
        json.dumps({"summary": summary, "edges": edges_out}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("relationship_mapping_agent")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_DIR / "relationship_mapping_agent.log", encoding="utf-8")
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

    agent = RelationshipMappingAgent(args.db, configure_logging())
    report = Path(args.report) if args.report else (
        REPORT_DIR / f"relationship_mapping_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    try:
        result, summary = agent.run(args.limit, args.dry_run)
        write_report(result, summary, report)
    except Exception as exc:
        logging.getLogger("relationship_mapping_agent").exception("Agent failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Completed in {summary['elapsed_seconds']}s")
    print(f"Candidate pairs considered: {summary['candidate_pairs_considered']}")
    print(f"Edges created: {summary['edges_created']}")
    print(f"By type: {summary['edges_by_type']}")
    print(f"Hub markets skipped (precision guard): {summary['hub_markets_skipped']}")
    print(f"Stale edges removed: {summary.get('stale_edges_removed', 0)}")
    print(f"Report: {report}")
    print("Database update: skipped (dry run)" if summary["dry_run"]
          else "Database update: committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
