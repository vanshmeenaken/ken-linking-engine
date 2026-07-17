"""Enrich link recommendations with real contextual placement and varied anchors.

Two PRD-mandated improvements applied in one pass over the existing
recommendations:

  1. Contextual placement (PRD 18.6 placement priority #1: relevant body
     paragraph). Reads each source page's body, finds the sentence where the
     target genuinely belongs, and stores it as suggested_sentence with
     placement_type='contextual_body'. Links with no genuine contextual home
     go to placement_type='related_reports_block' (an end-of-page block, like
     Search Engine Journal's "Suggested Articles"), never forced into an
     unrelated sentence.

  2. Anchor variation (PRD 18.4: no single exact-match anchor should dominate).
     When several pages link to the same target, their anchors are rotated
     from that target's anchor bank (Agent 7) so they are not all identical.

Read-only crawl of the source pages (the ones that have recommendations).
Idempotent: re-running recomputes placement and anchors from scratch.

Usage:
    python scripts/22_place_contextual_links.py --dry-run
    python scripts/22_place_contextual_links.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.contextual_placement import (best_placement, fetch_paragraphs,
                                          target_keywords)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "ken_links.db"

PLACEMENT_SECTION = {  # a readable section label per relationship type
    "same_market": "Market Overview",
    "adjacent_market": "Related Markets",
    "country_region": "Regional Coverage",
    "global_local": "Global Context",
    "report_article_support": "Supporting Analysis",
    "case_study_support": "Case Study Evidence",
}


def anchor_options(bank: sqlite3.Row) -> list[str]:
    """Ordered, de-duplicated anchor choices for a target, primary first."""
    if bank is None:
        return []
    out, seen = [], set()
    def add(vals):
        for v in vals:
            if v and v.lower() not in seen:
                seen.add(v.lower()); out.append(v)
    add([bank["primary_anchor"]])
    for col in ("secondary_anchors", "long_tail_anchors",
                "market_specific_anchors", "country_specific_anchors"):
        add(json.loads(bank[col]) if bank[col] else [])
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    recs = conn.execute(
        """SELECT r.recommendation_id, r.source_node_id, r.target_node_id,
                  r.relationship_type, r.link_score,
                  s.url AS source_url,
                  t.market AS t_market, t.country AS t_country,
                  t.region AS t_region, t.title AS t_title
           FROM link_recommendations r
           JOIN content_nodes s ON s.node_id = r.source_node_id
           JOIN content_nodes t ON t.node_id = r.target_node_id
           ORDER BY r.source_node_id, r.link_score DESC"""
    ).fetchall()

    # ── crawl each distinct source page once ─────────────────────────────────
    source_urls = {r["source_node_id"]: r["source_url"] for r in recs}
    paragraphs: dict[str, list[str]] = {}
    print(f"Crawling {len(source_urls)} source pages for body text...")
    for i, (nid, url) in enumerate(source_urls.items(), 1):
        try:
            paragraphs[nid] = fetch_paragraphs(url)
        except Exception as exc:
            paragraphs[nid] = []
            print(f"  [{i}] skip {url.split('/')[-1]}: {exc}")
        time.sleep(0.3)  # be polite to the server
    print("  done.\n")

    # ── decide placement per recommendation ──────────────────────────────────
    updates = []
    contextual = related = 0
    for r in recs:
        kws = target_keywords(r["t_market"], r["t_country"], r["t_region"], r["t_title"])
        placed = best_placement(paragraphs.get(r["source_node_id"], []), kws)
        if placed:
            ptype, sentence = "contextual_body", placed["sentence"]
            contextual += 1
        else:
            ptype, sentence = "related_reports_block", None
            related += 1
        section = ("Related Reports" if ptype == "related_reports_block"
                   else PLACEMENT_SECTION.get(r["relationship_type"], "Market Overview"))
        updates.append({"id": r["recommendation_id"], "target": r["target_node_id"],
                        "score": r["link_score"], "placement_type": ptype,
                        "placement_section": section, "suggested_sentence": sentence})

    # ── rotate anchors: vary anchors across inbound links to the same target ──
    by_target: dict[str, list[dict]] = {}
    for u in updates:
        by_target.setdefault(u["target"], []).append(u)
    anchor_assigned = 0
    for tid, group in by_target.items():
        bank = conn.execute(
            "SELECT * FROM anchor_banks WHERE target_node_id = ?", (tid,)).fetchone()
        options = anchor_options(bank)
        if not options:
            continue
        # strongest inbound link gets the primary anchor, next gets a variation
        group.sort(key=lambda u: -u["score"])
        for idx, u in enumerate(group):
            u["anchor_text"] = options[idx % len(options)]
            anchor_assigned += 1

    print(f"Contextual placements (in body): {contextual}")
    print(f"Routed to Related Reports block : {related}")
    print(f"Anchors rotated from bank       : {anchor_assigned}")

    if args.dry_run:
        print("\nDRY RUN - nothing written. Samples:")
        for u in updates[:6]:
            if u["placement_type"] == "contextual_body":
                print(f'  [body] anchor "{u.get("anchor_text","?")}"')
                print(f'         in: "{u["suggested_sentence"][:110]}..."')
            else:
                print(f'  [related-block] anchor "{u.get("anchor_text","?")}"')
        conn.close()
        return 0

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        conn.execute("BEGIN IMMEDIATE")
        for u in updates:
            sets = ["placement_type=?", "placement_section=?",
                    "suggested_sentence=?", "updated_at=?"]
            params = [u["placement_type"], u["placement_section"],
                      u["suggested_sentence"], now]
            if "anchor_text" in u:
                sets.append("anchor_text=?"); params.append(u["anchor_text"])
            params.append(u["id"])
            conn.execute(f"UPDATE link_recommendations SET {', '.join(sets)} "
                         "WHERE recommendation_id=?", params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    conn.close()
    print("\nDatabase update: committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
