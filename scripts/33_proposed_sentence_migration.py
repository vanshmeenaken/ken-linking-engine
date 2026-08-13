"""Add proposed_sentence to link_recommendations.

When no existing sentence on a source page genuinely fits an anchor, the
system now COMPOSES a ready-to-insert sentence containing the anchor (claim
free - it never invents market numbers, per PRD 12.3) and records exactly
where to insert it. suggested_sentence keeps its meaning (the existing line
the placement anchors to); proposed_sentence is the new sentence to add.

Backs up the database first. Additive and idempotent.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"


def migrate(db_path: Path) -> Path | None:
    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(link_recommendations)")}
        if "proposed_sentence" in cols:
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(
            f"{db_path.stem}_backup_proposed_sentence_{stamp}.db")
        shutil.copy2(db_path, backup)
        conn.execute(
            "ALTER TABLE link_recommendations ADD COLUMN proposed_sentence TEXT")
        conn.commit()
        return backup
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    backup = migrate(Path(args.db))
    if backup:
        print(f"Backup: {backup}")
        print("Added: link_recommendations.proposed_sentence")
    else:
        print("Schema already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
