"""Compute intent_stage and ai_readiness_score for active pages (Phase 2, Day 2).

Both columns exist in content_nodes since Phase 1 but were never populated.

intent_stage (master PRD funnel mapping from content type):
    article     -> awareness       (top of funnel, educational)
    case_study  -> consideration   (proof / evaluation)
    report      -> decision        (commercial intent)
    market_page -> decision
    service_page-> decision
    (others)    -> awareness

ai_readiness_score (master PRD §22, COMPUTABLE SUBSET only — 0.0-1.0):
    Factors we can measure from Phase 2 data, each 0-1, weighted:
      - clear market definition   : has a market entity            (0.25)
      - clear geography           : has country or region entity   (0.15)
      - metadata completeness     : title + h1 + meta all present  (0.20)
      - entity richness           : #entities, saturating at 5     (0.20)
      - internal relationships    : has >=1 relationship edge      (0.20)
    Deferred factors (need body-content crawl, documented not skipped):
      TOC, FAQ, methodology section, structured data, author
      attribution, original-data signal — join in the Agent 8/9 body pass.
    Bands (master PRD §22.2): High >= 0.70, Medium >= 0.45, else Low.

Usage:
    python scripts/17_compute_intent_ai_readiness.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

INTENT_BY_CONTENT_TYPE = {
    "article": "awareness",
    "case_study": "consideration",
    "report": "decision",
    "market_page": "decision",
    "industry_page": "decision",
    "country_page": "decision",
    "service_page": "decision",
}

WEIGHTS = {
    "market": 0.25, "geography": 0.15, "metadata": 0.20,
    "richness": 0.20, "relationships": 0.20,
}


def band(score: float) -> str:
    return "High" if score >= 0.70 else "Medium" if score >= 0.45 else "Low"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    nodes = conn.execute(
        "SELECT node_id, content_type, title, h1, meta_description "
        "FROM content_nodes WHERE status='active'"
    ).fetchall()

    # entity counts + type presence per node
    ent_types: dict[str, set[str]] = {}
    ent_count: dict[str, int] = {}
    for row in conn.execute(
        """SELECT ne.node_id, ce.entity_type FROM node_entities ne
           JOIN content_entities ce ON ce.entity_id = ne.entity_id
           WHERE ne.status != 'rejected'"""
    ):
        ent_types.setdefault(row["node_id"], set()).add(row["entity_type"])
        ent_count[row["node_id"]] = ent_count.get(row["node_id"], 0) + 1

    # which nodes have at least one relationship edge
    linked = {
        r[0] for r in conn.execute(
            "SELECT source_node_id FROM relationship_edges "
            "UNION SELECT target_node_id FROM relationship_edges"
        )
    }

    now = datetime.now(timezone.utc).isoformat()
    bands = {"High": 0, "Medium": 0, "Low": 0}
    intents: dict[str, int] = {}
    updates = []
    for n in nodes:
        types = ent_types.get(n["node_id"], set())
        f_market = 1.0 if "market" in types else 0.0
        f_geo = 1.0 if ("country" in types or "region" in types) else 0.0
        f_meta = sum(bool(n[c]) for c in ("title", "h1", "meta_description")) / 3.0
        f_rich = min(ent_count.get(n["node_id"], 0), 5) / 5.0
        f_rel = 1.0 if n["node_id"] in linked else 0.0
        score = round(
            WEIGHTS["market"] * f_market + WEIGHTS["geography"] * f_geo
            + WEIGHTS["metadata"] * f_meta + WEIGHTS["richness"] * f_rich
            + WEIGHTS["relationships"] * f_rel, 3
        )
        intent = INTENT_BY_CONTENT_TYPE.get(n["content_type"], "awareness")
        bands[band(score)] += 1
        intents[intent] = intents.get(intent, 0) + 1
        updates.append((intent, score, now, n["node_id"]))

    if not args.dry_run:
        conn.executemany(
            "UPDATE content_nodes SET intent_stage=?, ai_readiness_score=?, "
            "updated_at=? WHERE node_id=?",
            updates,
        )
        conn.commit()
    conn.close()

    print(f"Pages processed: {len(nodes)}")
    print(f"Intent stage: {intents}")
    print(f"AI-readiness bands: {bands}")
    print("Dry run — nothing written." if args.dry_run else "Committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
