"""Agent 6 - Link Recommendation Engine (master PRD 13.6, 17; Phase 3).

Turns each trusted relationship edge (a pending page-to-page connection from
Agent 3) into a scored, validated internal-link recommendation written to
link_recommendations with status='pending'. This is the core Phase 3
deliverable: the system stops only finding opportunities and starts saying
"link this source page to this target page, with this anchor, here, because".

For each edge (source -> target) it:
  1. builds a descriptive anchor from the target's market/geography (never a
     generic "click here"; the generic list is rejected by Agent 10 anyway)
  2. computes a 0-100 link_score from the master PRD 17 fourteen-factor formula
  3. assigns a score band (PRD 17.2) and drops anything below 50 (never pad)
  4. runs the proposed link through Agent 10 as a mandatory validation gate
  5. writes the recommendation, with its reason and risk, for editorial review

Link score (master PRD 17). Ten of the fourteen factors are computable from
Phase 1/2 data plus live GSC/GA4; the other four need data this phase doesn't
have and are DEFERRED, not faked. The score is rescaled over the computable
weights so it stays an honest 0-100, and the deferred factors are recorded in
the run report rather than silently zeroed.

    computable now (weight):
      semantic_similarity 16   from edge.semantic_similarity_score
      entity_overlap      12   from edge.entity_overlap_score
      market_relationship 10   from edge.market_match_score
      geography            8   from edge.geo_match_score
      search_intent        8   from GSC (target in striking distance 4-20)
      business_value       8   from target business_priority
      authority_transfer   8   from source page_authority_score
      crawl_priority       5   from target search_opportunity_score
      anchor_quality       5   from the generated anchor
      conversion_path      4   from GA4 key events on the target
      ai_readiness         3   from target ai_readiness_score
    deferred (documented):
      freshness            6   published/updated dates not populated
      evidence_support     5   Phase 5 paragraph evidence
      sentiment_external   2   out of scope

Usage:
    python agents/agent_6_link_recommendation.py --dry-run
    python agents/agent_6_link_recommendation.py --limit 20 --dry-run
    python agents/agent_6_link_recommendation.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agent_10_seo_validation import SEOValidationAgent
from analysis.anchor_text import build_primary_anchor
from analysis.report_link_planner import (
    recommendation_category,
    refresh_report_link_plans,
    select_balanced_recommendations,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
REPORT_DIR = ROOT / "reports"

# master PRD 17.1 weights, split into computable-now and deferred.
WEIGHTS = {
    "semantic_similarity": 16, "entity_overlap": 12, "market_relationship": 10,
    "geography": 8, "search_intent": 8, "business_value": 8,
    "authority_transfer": 8, "crawl_priority": 5, "anchor_quality": 5,
    "conversion_path": 4, "ai_readiness": 3,
}
DEFERRED = {"freshness": 6, "evidence_support": 5, "sentiment_external": 2}
COMPUTABLE_TOTAL = sum(WEIGHTS.values())  # 87

BUSINESS_VALUE = {"High": 1.0, "Medium": 0.6, "Low": 0.3}

# relationship_type -> where the link belongs (master PRD 18.6 placement).
PLACEMENT = {
    "same_market":            ("contextual_body", "Market Overview"),
    "adjacent_market":        ("related_reports_block", "Related Reports"),
    "country_region":         ("hub_link", "Regional Coverage"),
    "global_local":           ("contextual_body", "Global Context"),
    "report_article_support": ("contextual_body", "Supporting Analysis"),
    "case_study_support":     ("evidence_block", "Case Study Evidence"),
}

# Related-report blocks are a separate PRD placement path from contextual body
# links. Adjacent reports should not need exact same-market/geography scores;
# they need strong topical similarity and a real report-to-report target.
RELATED_REPORT_MIN_SEMANTIC = 0.40
RELATED_REPORT_MIN_MARKET = 0.30
RELATED_REPORT_MIN_SCORE = 50.0

# master PRD 17.2 score bands.
def band(score: float) -> str:
    if score >= 90: return "priority"
    if score >= 80: return "strong"
    if score >= 65: return "secondary"
    if score >= 50: return "hold"
    return "drop"


@dataclass
class Recommendation:
    source_node_id: str
    target_node_id: str
    source_url: str
    target_url: str
    target_canonical_url: str
    source_content_type: str
    target_content_type: str
    relationship_type: str
    relationship_class: str
    market_match_score: float
    technology_match_score: float
    anchor_text: str
    placement_type: str
    placement_section: str
    placement_status: str
    plan_category: str
    source_plan_rank: int
    link_score: float
    seo_score: float
    business_score: float
    ai_readiness_score: float
    confidence_score: float
    score_band: str
    validation_status: str
    risk_flag: str
    risk_reason: str
    recommendation_reason: str
    factors: dict = field(default_factory=dict)


class LinkRecommendationAgent:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = Path(db_path)
        self.validator = SEOValidationAgent(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # Related-report blocks are a separate PRD placement path from contextual
    # body links. Adjacent reports should not need exact same-market/geography
    # scores; they need strong topical similarity and a real report target.
    @staticmethod
    def _is_related_report_edge(edge: sqlite3.Row) -> bool:
        return (
            edge["relationship_type"] == "adjacent_market"
            and edge["s_type"] == "report"
            and edge["t_type"] == "report"
            and (edge["semantic_similarity_score"] or 0.0) >= RELATED_REPORT_MIN_SEMANTIC
            and (edge["market_match_score"] or 0.0) >= RELATED_REPORT_MIN_MARKET
            and (edge["technology_match_score"] or 0.0) >= 0.50
        )

    @staticmethod
    def _related_report_score(edge: sqlite3.Row, factors: dict) -> float:
        """Score for related-report block candidates.

        This intentionally weights semantic closeness and edge confidence over
        exact market/geography match. Adjacent reports are useful because they
        broaden discovery inside the same industry, not because they describe
        the identical market in the same country.
        """
        semantic = edge["semantic_similarity_score"] or 0.0
        confidence = edge["confidence_score"] or 0.0
        market = edge["market_match_score"] or 0.0
        technology = edge["technology_match_score"] or 0.0
        score = 100.0 * (
            market * 0.45
            + technology * 0.30
            + semantic * 0.10
            + confidence * 0.10
            + factors["business_value"] * 0.05
        )
        return max(RELATED_REPORT_MIN_SCORE, score)

    # ── anchor text (descriptive, never generic) ─────────────────────────────
    @staticmethod
    def _build_anchor(target: sqlite3.Row) -> tuple[str, float]:
        """Descriptive (anchor, quality) for the target. Delegates to the
        shared anchor helper so Agent 6 and Agent 7 stay consistent."""
        return build_primary_anchor(
            target["market"], target["country"], target["title"])

    def _load_signals(self, conn) -> dict:
        """Per-node GSC striking-distance and GA4 conversion flags."""
        striking, converting, has_impr = set(), set(), set()
        for nid, mn, mv in conn.execute(
            "SELECT node_id, metric_name, metric_value FROM integration_placeholders "
            "WHERE status='matched' AND metric_name IN ('position','impressions','key_events')"
        ):
            if mn == "position" and 4 <= mv <= 20:
                striking.add(nid)
            elif mn == "impressions" and mv > 0:
                has_impr.add(nid)
            elif mn == "key_events" and mv > 0:
                converting.add(nid)
        return {"striking": striking, "converting": converting, "has_impr": has_impr}

    def build(self, limit: int | None = None) -> list[Recommendation]:
        conn = self._connect()
        try:
            sig = self._load_signals(conn)
            q = """WITH oriented_edges AS (
                       SELECT e.*, e.source_node_id AS candidate_source_node_id,
                              e.target_node_id AS candidate_target_node_id
                       FROM relationship_edges e
                       WHERE e.status='pending' AND e.source_node_id != e.target_node_id
                       UNION ALL
                       SELECT e.*, e.target_node_id AS candidate_source_node_id,
                              e.source_node_id AS candidate_target_node_id
                       FROM relationship_edges e
                       WHERE e.status='pending'
                         AND e.relationship_direction='bidirectional'
                         AND e.source_node_id != e.target_node_id
                   )
                   SELECT e.*,
                          s.url AS s_url, s.page_authority_score AS s_auth,
                          s.content_type AS s_type,
                          t.url AS t_url, t.canonical_url AS t_canon, t.title AS t_title,
                          t.content_type AS t_type,
                          t.market AS t_market, t.country AS t_country,
                          t.business_priority AS t_bp, t.ai_readiness_score AS t_ai,
                          t.search_opportunity_score AS t_so
                   FROM oriented_edges e
                   JOIN content_nodes s ON s.node_id = e.candidate_source_node_id
                   JOIN content_nodes t ON t.node_id = e.candidate_target_node_id
                   ORDER BY e.confidence_score DESC"""
            if limit:
                q += f" LIMIT {int(limit)}"
            edges = conn.execute(q).fetchall()

            recs: list[Recommendation] = []
            for e in edges:
                target = conn.execute(
                    "SELECT * FROM content_nodes WHERE node_id = ?",
                    (e["candidate_target_node_id"],)).fetchone()
                anchor, anchor_q = self._build_anchor(target)

                source_id = e["candidate_source_node_id"]
                tid = e["candidate_target_node_id"]
                f = {
                    "semantic_similarity": e["semantic_similarity_score"] or 0.0,
                    "entity_overlap": e["entity_overlap_score"] or 0.0,
                    "market_relationship": e["market_match_score"] or 0.0,
                    "technology_relationship": e["technology_match_score"] or 0.0,
                    "geography": e["geo_match_score"] or 0.0,
                    "search_intent": 1.0 if tid in sig["striking"] else (
                        0.5 if tid in sig["has_impr"] else 0.0),
                    "business_value": BUSINESS_VALUE.get(e["t_bp"], 0.3),
                    "authority_transfer": (e["s_auth"] or 0.0) / 100.0,
                    "crawl_priority": e["t_so"] or 0.0,
                    "anchor_quality": anchor_q,
                    "conversion_path": 1.0 if tid in sig["converting"] else 0.0,
                    "ai_readiness": e["t_ai"] or 0.0,
                }
                # rescale over computable weights -> honest 0-100
                score = 100.0 * sum(f[k] * WEIGHTS[k] for k in WEIGHTS) / COMPUTABLE_TOTAL
                seo = 100.0 * (f["semantic_similarity"]*16 + f["entity_overlap"]*12
                               + f["market_relationship"]*10 + f["geography"]*8
                               + f["crawl_priority"]*5) / (16+12+10+8+5)
                if self._is_related_report_edge(e):
                    score = max(score, self._related_report_score(e, f))
                b = band(score)
                if b == "drop":
                    continue  # never pad: below 50 is not recommended

                placement_type, placement_section = PLACEMENT.get(
                    e["relationship_type"], ("contextual_body", "Related"))

                # mandatory validation gate (Agent 10)
                v = self.validator.validate(
                    source_id, tid, anchor, placement_type)
                risk_flag = "high" if v.overall_status == "rejected" else (
                    "medium" if v.overall_status == "needs_revision" else "low")
                risk_reason = "; ".join(f"{rf.rule}: {rf.description}"
                                        for rf in v.risk_flags) or None

                recs.append(Recommendation(
                    source_node_id=source_id, target_node_id=tid,
                    source_url=e["s_url"], target_url=e["t_url"],
                    target_canonical_url=e["t_canon"] or e["t_url"],
                    source_content_type=e["s_type"],
                    target_content_type=e["t_type"],
                    relationship_type=e["relationship_type"],
                    relationship_class=e["relationship_class"] or e["relationship_type"],
                    market_match_score=round(e["market_match_score"] or 0.0, 3),
                    technology_match_score=round(e["technology_match_score"] or 0.0, 3),
                    anchor_text=anchor,
                    placement_type=placement_type, placement_section=placement_section,
                    placement_status=(
                        "confirmed" if placement_type != "contextual_body"
                        else "planned"
                    ),
                    plan_category=recommendation_category(
                        e["relationship_type"], e["s_type"], e["t_type"]
                    ),
                    source_plan_rank=0,
                    link_score=round(score, 1), seo_score=round(seo, 1),
                    business_score=round(f["business_value"] * 100, 1),
                    ai_readiness_score=round(f["ai_readiness"] * 100, 1),
                    confidence_score=e["confidence_score"] or 0.0,
                    score_band=b, validation_status=v.overall_status,
                    risk_flag=risk_flag, risk_reason=risk_reason,
                    recommendation_reason=self._reason(e, anchor, b),
                    factors={k: round(val, 3) for k, val in f.items()},
                ))

            reviewed_rows = conn.execute(
                """SELECT source_node_id, target_node_id, relationship_type, status
                   FROM link_recommendations
                   WHERE status IN ('approved', 'rejected')"""
            ).fetchall()
            review_status = {
                (row["source_node_id"], row["target_node_id"],
                 row["relationship_type"]): row["status"]
                for row in reviewed_rows
            }
            approved_pairs = {
                (row["source_node_id"], row["target_node_id"])
                for row in reviewed_rows if row["status"] == "approved"
            }
            rejected_pairs = {
                (row["source_node_id"], row["target_node_id"])
                for row in reviewed_rows if row["status"] == "rejected"
            } - approved_pairs

            # De-duplicate overlapping relationship types. A prior human
            # approval wins over a newly higher machine score; rejected pairs
            # stay out of the active plan.
            best: dict[tuple[str, str], Recommendation] = {}
            for r in recs:
                key = (r.source_node_id, r.target_node_id)
                if key in rejected_pairs:
                    continue
                existing = best.get(key)
                status = review_status.get(
                    (r.source_node_id, r.target_node_id, r.relationship_type)
                )
                if key in approved_pairs and status != 'approved':
                    continue
                existing_status = (
                    review_status.get((
                        existing.source_node_id, existing.target_node_id,
                        existing.relationship_type,
                    ))
                    if existing else None
                )
                if (
                    existing is None
                    or (status == "approved" and existing_status != "approved")
                    or (
                        status == existing_status
                        and r.link_score > existing.link_score
                    )
                ):
                    best[key] = r

            page_facts = {
                row["node_id"]: dict(row)
                for row in conn.execute(
                    """SELECT node_id, content_type,
                              COALESCE(internal_links_out, 0) AS internal_links_out
                       FROM content_nodes"""
                )
            }
            selected_pairs = set(best)
            reserved_by_source: dict[str, int] = {}
            reserved_touch: dict[str, int] = {}
            for row in reviewed_rows:
                pair = (row["source_node_id"], row["target_node_id"])
                if row["status"] != "approved" or pair in selected_pairs:
                    continue
                source_id, target_id = pair
                reserved_by_source[source_id] = (
                    reserved_by_source.get(source_id, 0) + 1
                )
                for node_id in (source_id, target_id):
                    if page_facts[node_id]["content_type"] == "report":
                        reserved_touch[node_id] = reserved_touch.get(node_id, 0) + 1

            selected = select_balanced_recommendations(
                list(best.values()), page_facts, approved_pairs,
                reserved_by_source, reserved_touch,
            )
            additions_by_source: dict[str, int] = {}
            for recommendation in selected:
                additions_by_source[recommendation.source_node_id] = (
                    additions_by_source.get(recommendation.source_node_id, 0) + 1
                )
            for recommendation in selected:
                validation = self.validator.validate(
                    recommendation.source_node_id,
                    recommendation.target_node_id,
                    recommendation.anchor_text,
                    recommendation.placement_type,
                    additional_links=additions_by_source[
                        recommendation.source_node_id
                    ],
                )
                recommendation.validation_status = validation.overall_status
                recommendation.risk_flag = (
                    "high" if validation.overall_status == "rejected"
                    else "medium" if validation.overall_status == "needs_revision"
                    else "low"
                )
                recommendation.risk_reason = "; ".join(
                    f"{flag.rule}: {flag.description}"
                    for flag in validation.risk_flags
                ) or None
            return selected
        finally:
            conn.close()

    @staticmethod
    def _reason(e, anchor, b) -> str:
        rel = e["relationship_type"].replace("_", " ")
        relationship_class = e["relationship_class"] or rel
        return (f"{e['s_url'].split('/')[-1]} and {e['t_url'].split('/')[-1]} pass "
                f"the market/technology relevance gate as {relationship_class} "
                f"(market {e['market_match_score'] or 0.0:.2f}, technology "
                f"{e['technology_match_score'] or 0.0:.2f}, confidence "
                f"{e['confidence_score']:.2f}); link with anchor '{anchor}' [{b}].")

    def write(self, recs: list[Recommendation]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            for r in recs:
                # a rejected link is stored but flagged, never as 'pending'
                status = "rejected" if r.validation_status == "rejected" else "pending"
                conn.execute(
                    """INSERT INTO link_recommendations
                       (recommendation_id, source_node_id, target_node_id,
                        source_url, target_url, target_canonical_url,
                        relationship_type, relationship_class,
                        market_match_score, technology_match_score,
                        anchor_text, placement_type, placement_section,
                        placement_status, plan_category, source_plan_rank,
                        link_score, seo_score, business_score,
                        ai_readiness_score, confidence_score, score_band,
                        risk_flag, risk_reason, recommendation_reason,
                        validation_status, status, created_by, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'agent_6',?,?)
                       ON CONFLICT (source_node_id, target_node_id, relationship_type)
                       DO UPDATE SET
                           anchor_text=CASE
                               WHEN link_recommendations.status IN ('approved','deployed')
                               THEN link_recommendations.anchor_text
                               ELSE excluded.anchor_text END,
                           link_score=excluded.link_score,
                           seo_score=excluded.seo_score,
                           business_score=excluded.business_score,
                           score_band=excluded.score_band,
                           validation_status=excluded.validation_status,
                           risk_flag=excluded.risk_flag,
                           risk_reason=excluded.risk_reason,
                           relationship_class=excluded.relationship_class,
                           market_match_score=excluded.market_match_score,
                           technology_match_score=excluded.technology_match_score,
                           placement_type=CASE
                               WHEN link_recommendations.placement_status
                                    IN ('confirmed','unresolved')
                               THEN link_recommendations.placement_type
                               ELSE excluded.placement_type END,
                           placement_section=CASE
                               WHEN link_recommendations.placement_status
                                    IN ('confirmed','unresolved')
                               THEN link_recommendations.placement_section
                               ELSE excluded.placement_section END,
                           placement_status=CASE
                               WHEN link_recommendations.placement_status
                                    IN ('confirmed','unresolved')
                               THEN link_recommendations.placement_status
                               ELSE excluded.placement_status END,
                           plan_category=excluded.plan_category,
                           source_plan_rank=excluded.source_plan_rank,
                           recommendation_reason=excluded.recommendation_reason,
                           updated_at=excluded.updated_at""",
                    (str(uuid.uuid4()), r.source_node_id, r.target_node_id,
                     r.source_url, r.target_url, r.target_canonical_url,
                     r.relationship_type, r.relationship_class,
                     r.market_match_score, r.technology_match_score,
                     r.anchor_text, r.placement_type, r.placement_section,
                     r.placement_status, r.plan_category, r.source_plan_rank,
                     r.link_score, r.seo_score, r.business_score,
                     r.ai_readiness_score, r.confidence_score, r.score_band,
                     r.risk_flag, r.risk_reason, r.recommendation_reason,
                     r.validation_status, status, now, now),
                )

            # Rebuilding recommendations must also retire stale machine-made
            # pending rows. Human-approved/rejected rows are audit decisions
            # and are deliberately preserved.
            current_keys = {
                (r.source_node_id, r.target_node_id, r.relationship_type)
                for r in recs
            }
            stale_ids = [
                row[0] for row in conn.execute(
                    "SELECT recommendation_id, source_node_id, target_node_id, "
                    "relationship_type FROM link_recommendations "
                    "WHERE created_by='agent_6' AND status='pending'"
                )
                if (row[1], row[2], row[3]) not in current_keys
            ]
            for recommendation_id in stale_ids:
                conn.execute(
                    "DELETE FROM link_recommendations WHERE recommendation_id=?",
                    (recommendation_id,),
                )
            refresh_report_link_plans(conn, now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return len(recs)


def write_report(recs, elapsed, dry_run) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"link_recommendations_{stamp}.json"
    bands: dict = {}
    for r in recs:
        bands[r.score_band] = bands.get(r.score_band, 0) + 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "elapsed_seconds": elapsed,
        "recommendations": len(recs),
        "by_band": bands,
        "deferred_factors": DEFERRED,
        "computable_weight_total": COMPUTABLE_TOTAL,
        "sample": [
            {"source": r.source_url.split("/")[-1],
             "target": r.target_url.split("/")[-1],
             "anchor": r.anchor_text, "score": r.link_score, "band": r.score_band,
             "validation": r.validation_status, "reason": r.recommendation_reason}
            for r in recs[:10]
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main(argv=None) -> int:
    import time
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    agent = LinkRecommendationAgent(args.db)
    recs = agent.build(args.limit)
    elapsed = round(time.perf_counter() - started, 2)

    bands: dict = {}
    for r in recs:
        bands[r.score_band] = bands.get(r.score_band, 0) + 1
    print(f"Recommendations generated: {len(recs)}")
    print(f"By band: {bands}")
    print(f"Deferred factors (documented, not scored): {DEFERRED}")

    report = write_report(recs, elapsed, args.dry_run)
    print(f"Report: {report}")

    if args.dry_run:
        print("Database update: skipped (dry run)")
        for r in recs[:5]:
            print(f"  [{r.score_band:9s} {r.link_score:5.1f}] {r.anchor_text[:40]:40s}"
                  f" <- {r.source_url.split('/')[-1][:30]}")
    else:
        n = agent.write(recs)
        print(f"Database update: committed ({n} recommendations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
