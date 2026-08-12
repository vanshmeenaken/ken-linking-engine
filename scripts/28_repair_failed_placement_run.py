"""Restore verified placement fields from a known-good database backup."""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"


def repair(target_db: Path, source_db: Path, dry_run: bool = False) -> int:
    if not target_db.exists():
        raise FileNotFoundError(f"Target database not found: {target_db}")
    if not source_db.exists():
        raise FileNotFoundError(f"Source backup not found: {source_db}")

    source = sqlite3.connect(f"file:{source_db.resolve()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    rows = source.execute(
        """SELECT source_node_id, target_node_id, relationship_type,
                  placement_type, placement_section, suggested_sentence
           FROM link_recommendations
           WHERE placement_type='contextual_body'
             AND COALESCE(suggested_sentence, '') != ''"""
    ).fetchall()
    source.close()

    target = sqlite3.connect(target_db)
    matches = []
    try:
        for row in rows:
            recommendation = target.execute(
                """SELECT recommendation_id
                   FROM link_recommendations
                   WHERE source_node_id=? AND target_node_id=?
                     AND relationship_type=?""",
                (row["source_node_id"], row["target_node_id"],
                 row["relationship_type"]),
            ).fetchone()
            if recommendation:
                matches.append((recommendation[0], row))
        if dry_run:
            return len(matches)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = target_db.with_name(
            f"{target_db.stem}_backup_before_placement_repair_{stamp}.db"
        )
        target.close()
        shutil.copy2(target_db, backup)
        target = sqlite3.connect(target_db)
        now = datetime.now(timezone.utc).isoformat()
        target.execute("BEGIN IMMEDIATE")
        for recommendation_id, row in matches:
            target.execute(
                """UPDATE link_recommendations
                   SET placement_type=?, placement_section=?,
                       suggested_sentence=?, placement_status='confirmed',
                       updated_at=?
                   WHERE recommendation_id=?""",
                (row["placement_type"], row["placement_section"],
                 row["suggested_sentence"], now, recommendation_id),
            )
        target.commit()
        print(f"Backup: {backup}")
        return len(matches)
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = repair(Path(args.db), Path(args.source_db), args.dry_run)
    print(f"Verified placements matched: {count}")
    print("Database update: skipped (dry run)" if args.dry_run
          else "Database update: committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
