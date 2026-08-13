"""Add chosen_sentence and suggestion_style to manual_link_plans.

The workbench now offers several sentence framings per paragraph and lets the
user edit or write their own. chosen_sentence stores the exact wording they
settled on (the thing the web team will paste), and suggestion_style records
whether it came from a suggested framing or was written from scratch, so it
stays clear which sentences a person authored themselves.

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

COLUMNS = {
    "chosen_sentence": "TEXT",
    "suggestion_style": "TEXT",
}


def migrate(db_path: Path) -> tuple[Path | None, list[str]]:
    conn = sqlite3.connect(db_path)
    try:
        existing = {r[1] for r in conn.execute(
            "PRAGMA table_info(manual_link_plans)")}
        missing = [(n, d) for n, d in COLUMNS.items() if n not in existing]
        if not missing:
            return None, []
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(
            f"{db_path.stem}_backup_chosen_sentence_{stamp}.db")
        shutil.copy2(db_path, backup)
        for name, decl in missing:
            conn.execute(
                f"ALTER TABLE manual_link_plans ADD COLUMN {name} {decl}")
        conn.commit()
        return backup, [n for n, _ in missing]
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    backup, changes = migrate(Path(args.db))
    if changes:
        print(f"Backup: {backup}")
        print("Added: " + ", ".join(f"manual_link_plans.{c}" for c in changes))
    else:
        print("Schema already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
