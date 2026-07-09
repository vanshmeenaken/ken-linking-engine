"""Entity correction toolkit (Phase 2, Day 4 Module 4.2).

Manual-correction workflow over the entities Agent 2 extracted. Every command
preserves the original extracted values — corrections change status and
normalized_value, never the extraction evidence — and every change is logged
to entity_extraction_logs.

Commands:
    audit                         Show duplicate groups and status/confidence overview
    merge-duplicates [--apply]    Merge singular/plural duplicate entities
                                  (dry-run preview unless --apply)
    list-low-confidence           Export mappings below --threshold (default 0.70)
                                  to CSV + JSON for manual review
    approve  --id <node_entity_id>              Mark a mapping verified-correct
    reject   --id <node_entity_id> [--notes]    Mark a mapping wrong (kept, not used)
    correct  --id <node_entity_id> --value V    Store the fixed value, keep original

Workflow doc: docs/09-AGENTS/02-ENTITY-CORRECTION-WORKFLOW.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.taxonomy import normalize_market_name

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
REPORT_DIR = ROOT / "reports"

REVIEW_THRESHOLD = 0.70
VALID_STATUSES = ("extracted", "approved", "corrected", "rejected")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _log(conn, node_id, operation, notes):
    conn.execute(
        """INSERT INTO entity_extraction_logs
           (run_id, node_id, operation, status, entities_found,
            low_confidence_count, error, notes, created_at)
           VALUES (?,?,?,?,0,0,NULL,?,?)""",
        (f"correction-{uuid.uuid4().hex[:8]}", node_id, operation, "success",
         notes, _now()),
    )


# ── duplicate detection / merge ──────────────────────────────────────────────

def find_duplicate_groups(conn) -> list[list[sqlite3.Row]]:
    """Groups of entities whose recomputed dedup key collides.
    Uses normalize_market_name for markets; plain lowercase for other types."""
    groups: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in conn.execute(
        "SELECT entity_id, entity_name, entity_type, normalized_name "
        "FROM content_entities"
    ):
        if row["entity_type"] == "market":
            key = normalize_market_name(row["normalized_name"])
        else:
            key = row["normalized_name"].lower().strip()
        groups[(key, row["entity_type"])].append(row)
    return [rows for rows in groups.values() if len(rows) > 1]


def cmd_merge_duplicates(db_path: Path, apply: bool) -> int:
    conn = _connect(db_path, readonly=not apply)
    try:
        groups = find_duplicate_groups(conn)
        if not groups:
            print("No duplicate entities found.")
            return 0
        print(f"{len(groups)} duplicate group(s):")
        merged = 0
        if apply:
            conn.execute("BEGIN IMMEDIATE")
        for rows in groups:
            # Keeper = the variant mapped to the most pages
            counts = {
                r["entity_id"]: conn.execute(
                    "SELECT COUNT(*) FROM node_entities WHERE entity_id=?",
                    (r["entity_id"],),
                ).fetchone()[0]
                for r in rows
            }
            rows = sorted(rows, key=lambda r: -counts[r["entity_id"]])
            keeper, losers = rows[0], rows[1:]
            new_key = (normalize_market_name(keeper["normalized_name"])
                       if keeper["entity_type"] == "market"
                       else keeper["normalized_name"].lower().strip())
            names = " | ".join(f"{r['entity_name']} ({counts[r['entity_id']]} pages)"
                               for r in rows)
            print(f"  [{keeper['entity_type']}] {names}  ->  keep '{keeper['entity_name']}'")
            if not apply:
                continue
            for loser in losers:
                # Repoint page mappings; drop any that would now duplicate
                # an existing (node_id, entity_id, entity_role) on the keeper
                conn.execute(
                    """DELETE FROM node_entities WHERE entity_id=? AND EXISTS (
                           SELECT 1 FROM node_entities k
                           WHERE k.entity_id=? AND k.node_id=node_entities.node_id
                             AND k.entity_role=node_entities.entity_role)""",
                    (loser["entity_id"], keeper["entity_id"]),
                )
                conn.execute(
                    "UPDATE node_entities SET entity_id=?, updated_at=? WHERE entity_id=?",
                    (keeper["entity_id"], _now(), loser["entity_id"]),
                )
                conn.execute(
                    "DELETE FROM content_entities WHERE entity_id=?",
                    (loser["entity_id"],),
                )
                _log(conn, None, "merge_duplicate",
                     f"merged '{loser['entity_name']}' into '{keeper['entity_name']}' "
                     f"({keeper['entity_id']})")
                merged += 1
            conn.execute(
                "UPDATE content_entities SET normalized_name=?, updated_at=? "
                "WHERE entity_id=?",
                (new_key, _now(), keeper["entity_id"]),
            )
        if apply:
            conn.commit()
            print(f"\nMerged {merged} duplicate entities. Changes committed.")
        else:
            print("\nDry run — re-run with --apply to merge.")
        return 0
    except Exception:
        if apply:
            conn.rollback()
        raise
    finally:
        conn.close()


# ── low-confidence review export ─────────────────────────────────────────────

def cmd_list_low_confidence(db_path: Path, threshold: float) -> int:
    conn = _connect(db_path, readonly=True)
    try:
        rows = conn.execute(
            """SELECT ne.node_entity_id, n.url, ce.entity_type, ce.entity_name,
                      ne.entity_role, ne.source_field, ne.extracted_value,
                      ne.normalized_value, ne.confidence_score,
                      ne.extraction_method, ne.status
               FROM node_entities ne
               JOIN content_nodes n ON n.node_id = ne.node_id
               JOIN content_entities ce ON ce.entity_id = ne.entity_id
               WHERE ne.confidence_score < ? AND ne.status = 'extracted'
               ORDER BY ne.confidence_score ASC, n.url""",
            (threshold,),
        ).fetchall()
        REPORT_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = REPORT_DIR / f"low_confidence_entities_{stamp}.csv"
        json_path = REPORT_DIR / f"low_confidence_entities_{stamp}.json"
        records = [dict(r) for r in rows]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "node_entity_id", "url", "entity_type", "entity_name",
                "entity_role", "source_field", "extracted_value",
                "normalized_value", "confidence_score", "extraction_method",
                "status",
            ])
            for r in records:
                writer.writerow(r.values())
        json_path.write_text(
            json.dumps({
                "generated_at": _now(), "threshold": threshold,
                "count": len(records), "mappings": records,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"{len(records)} mapping(s) below confidence {threshold}")
        print(f"CSV:  {csv_path}")
        print(f"JSON: {json_path}")
        return 0
    finally:
        conn.close()


# ── status commands ──────────────────────────────────────────────────────────

def _get_mapping(conn, node_entity_id: str):
    row = conn.execute(
        """SELECT ne.*, ce.entity_name, ce.entity_type
           FROM node_entities ne
           JOIN content_entities ce ON ce.entity_id = ne.entity_id
           WHERE ne.node_entity_id = ?""",
        (node_entity_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"ERROR: no node_entities row with id '{node_entity_id}'")
    return row


def _find_or_create_entity(conn, entity_type: str, display_value: str) -> str:
    """Entity id for a human-corrected value: reuse the existing entity with
    the same dedup key, or create a new one (confidence 1.0 — human-set)."""
    key = (normalize_market_name(display_value) if entity_type == "market"
           else display_value.lower().strip())
    row = conn.execute(
        "SELECT entity_id FROM content_entities "
        "WHERE normalized_name=? AND entity_type=?",
        (key, entity_type),
    ).fetchone()
    if row:
        return row["entity_id"]
    entity_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO content_entities
           (entity_id, entity_name, entity_type, normalized_name, aliases,
            industry, country, region, confidence_score, created_at, updated_at)
           VALUES (?,?,?,?,'','','','',1.0,?,?)""",
        (entity_id, display_value, entity_type, key, _now(), _now()),
    )
    return entity_id


def cmd_set_status(db_path: Path, node_entity_id: str, status: str,
                   value: str = "", notes: str = "") -> int:
    conn = _connect(db_path)
    try:
        mapping = _get_mapping(conn, node_entity_id)
        conn.execute("BEGIN IMMEDIATE")
        if status == "corrected":
            if not value:
                raise SystemExit("ERROR: correct requires --value")
            # Remap to the corrected entity, not just relabel: the APIs join
            # through content_entities, so leaving the old entity_id in place
            # would keep showing the wrong entity name (review finding).
            new_entity_id = _find_or_create_entity(
                conn, mapping["entity_type"], value
            )
            collision = conn.execute(
                """SELECT node_entity_id FROM node_entities
                   WHERE node_id=? AND entity_id=? AND entity_role=?
                     AND node_entity_id != ?""",
                (mapping["node_id"], new_entity_id, mapping["entity_role"],
                 node_entity_id),
            ).fetchone()
            if collision:
                # The page already maps to the corrected entity in this role —
                # keep that row (marked corrected), drop the wrong one.
                conn.execute(
                    "UPDATE node_entities SET status='corrected', "
                    "normalized_value=?, updated_at=? WHERE node_entity_id=?",
                    (value, _now(), collision["node_entity_id"]),
                )
                conn.execute(
                    "DELETE FROM node_entities WHERE node_entity_id=?",
                    (node_entity_id,),
                )
            else:
                conn.execute(
                    "UPDATE node_entities SET status=?, entity_id=?, "
                    "normalized_value=?, updated_at=? WHERE node_entity_id=?",
                    (status, new_entity_id, value, _now(), node_entity_id),
                )
        else:
            conn.execute(
                "UPDATE node_entities SET status=?, updated_at=? "
                "WHERE node_entity_id=?",
                (status, _now(), node_entity_id),
            )
        detail = (f"{status}: [{mapping['entity_type']}] '{mapping['entity_name']}' "
                  f"role={mapping['entity_role']}")
        if value:
            detail += f" corrected_to='{value}'"
        if notes:
            detail += f" notes={notes}"
        _log(conn, mapping["node_id"], f"correction_{status}", detail)
        conn.commit()
        print(f"OK — mapping {node_entity_id[:8]}… set to '{status}'."
              + (f" Corrected value: '{value}'." if value else "")
              + " Original extracted value preserved.")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── audit overview ───────────────────────────────────────────────────────────

def cmd_audit(db_path: Path) -> int:
    conn = _connect(db_path, readonly=True)
    try:
        print("=== entity status distribution (node_entities) ===")
        for r in conn.execute(
            "SELECT status, COUNT(*) n FROM node_entities GROUP BY status"
        ):
            print(f"  {r['status']}: {r['n']}")
        print("\n=== confidence bands ===")
        for r in conn.execute(
            """SELECT CASE WHEN confidence_score>=0.9 THEN 'high (0.9+)'
                           WHEN confidence_score>=0.7 THEN 'good (0.7-0.9)'
                           WHEN confidence_score>=0.5 THEN 'review (0.5-0.7)'
                           ELSE 'low (<0.5)' END band, COUNT(*) n
               FROM node_entities GROUP BY band ORDER BY n DESC"""
        ):
            print(f"  {r['band']}: {r['n']}")
        groups = find_duplicate_groups(conn)
        print(f"\n=== duplicate groups: {len(groups)} ===")
        for rows in groups:
            print("  " + " | ".join(r["entity_name"] for r in rows))
        return 0
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("audit")
    p_merge = sub.add_parser("merge-duplicates")
    p_merge.add_argument("--apply", action="store_true")
    p_low = sub.add_parser("list-low-confidence")
    p_low.add_argument("--threshold", type=float, default=REVIEW_THRESHOLD)
    for name in ("approve", "reject", "correct"):
        p = sub.add_parser(name)
        p.add_argument("--id", required=True, dest="node_entity_id")
        p.add_argument("--notes", default="")
        if name == "correct":
            p.add_argument("--value", required=True)

    args = parser.parse_args(argv)
    db_path = Path(args.db)
    if args.command == "audit":
        return cmd_audit(db_path)
    if args.command == "merge-duplicates":
        return cmd_merge_duplicates(db_path, args.apply)
    if args.command == "list-low-confidence":
        return cmd_list_low_confidence(db_path, args.threshold)
    status = {"approve": "approved", "reject": "rejected", "correct": "corrected"}[args.command]
    return cmd_set_status(db_path, args.node_entity_id, status,
                          getattr(args, "value", ""), args.notes)


if __name__ == "__main__":
    raise SystemExit(main())
