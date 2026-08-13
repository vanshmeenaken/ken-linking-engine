"""Rotate safe anchor variants across recommendations without crawling pages.

Anchor choice is intent-aware (master PRD 13.7 "align anchor with target page
intent"): the variant matching the sentence the link sits in is preferred -
a growth sentence gets the "Growth and Opportunities" variant, a market-size
sentence gets "Size" - while diversity (no repeated anchor per target) and
protection (approved/deployed anchors untouched) still hold.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.anchor_text import pick_anchor_for_context

DEFAULT_DB = ROOT / "ken_links.db"


def options(bank: sqlite3.Row | None) -> list[str]:
    if bank is None:
        return []
    values, seen = [], set()
    for value in [bank["primary_anchor"]]:
        if value and value.lower() not in seen:
            seen.add(value.lower()); values.append(value)
    for column in ("secondary_anchors", "long_tail_anchors",
                   "market_specific_anchors", "country_specific_anchors"):
        for value in json.loads(bank[column] or "[]"):
            if value and value.lower() not in seen:
                seen.add(value.lower()); values.append(value)
    return values


def rotate(db_path: Path, dry_run: bool = False) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT recommendation_id, target_node_id, link_score,
                  suggested_sentence, placement_section
           FROM link_recommendations
           WHERE status='pending'
           ORDER BY target_node_id, link_score DESC"""
    ).fetchall()
    used_by_target = defaultdict(set)
    for row in conn.execute(
        """SELECT target_node_id, anchor_text FROM link_recommendations
           WHERE status IN ('approved', 'deployed')
             AND COALESCE(anchor_text, '') != ''"""
    ):
        used_by_target[row["target_node_id"]].add(row["anchor_text"].lower())
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["target_node_id"]].append(row)
    updates = []
    for target_id, recommendations in grouped.items():
        bank = conn.execute(
            "SELECT * FROM anchor_banks WHERE target_node_id=?", (target_id,),
        ).fetchone()
        choices = options(bank)
        unused = [
            choice for choice in choices
            if choice.lower() not in used_by_target[target_id]
        ]
        if unused:
            choices = unused
        if not choices:
            continue
        # intent-aware pick per recommendation: the variant matching the
        # sentence/section the link sits in goes first; a set tracks what
        # this target's pending group already used so diversity holds
        assigned: set[str] = set()
        for index, recommendation in enumerate(recommendations):
            ordered = pick_anchor_for_context(
                choices, recommendation["suggested_sentence"],
                recommendation["placement_section"])
            choice = next(
                (c for c in ordered if c.lower() not in assigned),
                ordered[index % len(ordered)])
            assigned.add(choice.lower())
            updates.append((choice, recommendation["recommendation_id"]))
    if not dry_run:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.executemany(
            "UPDATE link_recommendations SET anchor_text=?,updated_at=? "
            "WHERE recommendation_id=?",
            [(anchor, now, recommendation_id) for anchor, recommendation_id in updates],
        )
        conn.commit()
    conn.close()
    return len(updates)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = rotate(Path(args.db), args.dry_run)
    print(f"Anchors rotated: {count}")
    print("Database update: skipped (dry run)" if args.dry_run else "Database update: committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
