"""Add explainable market/technology relevance fields.

Idempotent and additive. A timestamped database backup is created before the
first schema change.
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
    "relationship_edges": {
        "technology_match_score": "REAL DEFAULT 0.0",
        "relationship_class": "TEXT",
    },
    "link_recommendations": {
        "relationship_class": "TEXT",
        "market_match_score": "REAL DEFAULT 0.0",
        "technology_match_score": "REAL DEFAULT 0.0",
    },
}


def migrate(db_path: Path) -> tuple[Path | None, list[str]]:
    conn = sqlite3.connect(db_path)
    missing = []
    try:
        for table, columns in COLUMNS.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    missing.append((table, name, definition))
        if not missing:
            return None, []
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(f"{db_path.stem}_backup_market_technology_{stamp}.db")
        shutil.copy2(db_path, backup)
        for table, name, definition in missing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        conn.commit()
        return backup, [f"{table}.{name}" for table, name, _ in missing]
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    backup, added = migrate(Path(args.db))
    if added:
        print(f"Backup: {backup}")
        print("Added: " + ", ".join(added))
    else:
        print("Schema already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
