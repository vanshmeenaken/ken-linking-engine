"""One-time fix: relocate industry_market entity facts out of relationship_edges.

Background
----------
Agent 3 stored "this market belongs to this industry" as `industry_market`
rows in `relationship_edges`, anchoring each on a single page
(source_node_id == target_node_id, a self-loop). That is entity-hierarchy
metadata, not a page-to-page link, and it polluted:
  - relationship_edges (384 of 494 rows were these self-loops)
  - any "page-to-page connectivity" metric computed over that table

The correct home for "a market's parent industry" already exists and was
empty: content_entities.parent_entity_id.

This script (idempotent, backs up first):
  1. Derives each market entity's parent industry from the existing edges.
     Clean 1->1 markets take that industry; the few markets that co-occur
     with >1 industry take their single most-frequent industry.
  2. Writes it to content_entities.parent_entity_id.
  3. Deletes the industry_market self-loop edges.

Nothing is lost: the market/industry entities and their per-page mappings
remain in content_entities / node_entities; only the miscounted duplicate
in the links table is removed, and the hierarchy moves to its designed field.

Agent 3 itself is fixed separately so future runs never recreate these edges.

Usage:
    python scripts/18_fix_industry_market_edges.py --dry-run
    python scripts/18_fix_industry_market_edges.py
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "ken_links.db"


def derive_parents(conn: sqlite3.Connection) -> dict[str, str]:
    """market_entity_id -> chosen industry_entity_id, from industry_market edges."""
    pairs: dict[str, Counter] = defaultdict(Counter)
    for market_id, industry_id in conn.execute(
        """SELECT source_entity_id, target_entity_id
           FROM relationship_edges
           WHERE relationship_type = 'industry_market'
             AND source_entity_id IS NOT NULL
             AND target_entity_id IS NOT NULL"""
    ):
        pairs[market_id][industry_id] += 1
    # most_common(1) breaks any ambiguity deterministically by frequency
    return {m: counts.most_common(1)[0][0] for m, counts in pairs.items()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change; write nothing")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(DB_PATH)

    edge_count = conn.execute(
        "SELECT COUNT(*) FROM relationship_edges "
        "WHERE relationship_type = 'industry_market'"
    ).fetchone()[0]
    selfloops = conn.execute(
        "SELECT COUNT(*) FROM relationship_edges "
        "WHERE relationship_type = 'industry_market' "
        "AND source_node_id = target_node_id"
    ).fetchone()[0]
    parents = derive_parents(conn)

    print(f"industry_market edges found : {edge_count}")
    print(f"  of which self-loops       : {selfloops}")
    print(f"market entities to re-parent: {len(parents)}")

    # sanity: every industry_market edge must be a self-loop; if not, stop and
    # surface it rather than deleting a genuine page-to-page edge by mistake
    if edge_count != selfloops:
        print(f"ABORT: {edge_count - selfloops} industry_market edge(s) are NOT "
              "self-loops. Inspect before deleting.", file=sys.stderr)
        return 1

    if args.dry_run:
        sample = list(parents.items())[:3]
        for m, i in sample:
            mn = conn.execute("SELECT entity_name FROM content_entities WHERE entity_id=?", (m,)).fetchone()
            inn = conn.execute("SELECT entity_name FROM content_entities WHERE entity_id=?", (i,)).fetchone()
            print(f"  would set parent: {mn[0]!r} -> {inn[0]!r}")
        print("DRY RUN - no changes written.")
        conn.close()
        return 0

    backup = DB_PATH.with_name(
        f"ken_links_backup_industrymarket_{datetime.now():%Y%m%d_%H%M%S}.db"
    )
    shutil.copy2(DB_PATH, backup)
    print(f"backup written: {backup.name}")

    try:
        conn.execute("BEGIN IMMEDIATE")
        reparented = 0
        for market_id, industry_id in parents.items():
            conn.execute(
                "UPDATE content_entities SET parent_entity_id = ?, "
                "updated_at = ? WHERE entity_id = ? AND entity_type = 'market'",
                (industry_id, datetime.now().isoformat(), market_id),
            )
            reparented += conn.total_changes and 1
        deleted = conn.execute(
            "DELETE FROM relationship_edges WHERE relationship_type = 'industry_market'"
        ).rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    # verify
    remaining = conn.execute(
        "SELECT COUNT(*) FROM relationship_edges WHERE relationship_type='industry_market'"
    ).fetchone()[0]
    parents_set = conn.execute(
        "SELECT COUNT(*) FROM content_entities "
        "WHERE entity_type='market' AND parent_entity_id IS NOT NULL"
    ).fetchone()[0]
    total_edges = conn.execute("SELECT COUNT(*) FROM relationship_edges").fetchone()[0]
    selfloops_left = conn.execute(
        "SELECT COUNT(*) FROM relationship_edges WHERE source_node_id=target_node_id"
    ).fetchone()[0]
    conn.close()

    print(f"parent_entity_id set on      : {parents_set} market entities")
    print(f"industry_market edges deleted: {deleted}")
    print(f"industry_market edges left    : {remaining}")
    print(f"self-loop edges left anywhere : {selfloops_left}")
    print(f"relationship_edges now total  : {total_edges} (all page-to-page)")
    if remaining or selfloops_left:
        print("WARNING: residual self-loops remain — inspect.", file=sys.stderr)
        return 1
    print("OK — links table is now 100% genuine page-to-page edges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
