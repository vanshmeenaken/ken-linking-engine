"""Add the section_purpose_map table for Agent 9 (master PRD 13.9).

One row per crawled section of a page: its real heading, classified purpose,
paragraph/link counts, and the section-specific link guidance Agent 9
produces. Additive and idempotent; backs up the database before changing
schema (project safety rule: backup before migrations).
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

SECTION_TABLE = """
CREATE TABLE IF NOT EXISTS section_purpose_map (
    section_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES content_nodes(node_id),
    url TEXT NOT NULL,
    heading TEXT,
    section_order INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    paragraph_count INTEGER DEFAULT 0,
    internal_link_count INTEGER DEFAULT 0,
    linkable INTEGER DEFAULT 0,
    link_guidance TEXT,
    flag_purposeless INTEGER DEFAULT 0,
    flag_missing_links INTEGER DEFAULT 0,
    crawled_at TEXT,
    created_at TEXT,
    updated_at TEXT
)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_section_purpose_node "
    "ON section_purpose_map(node_id)",
    "CREATE INDEX IF NOT EXISTS ix_section_purpose_purpose "
    "ON section_purpose_map(purpose)",
]


def migrate(db_path: Path) -> tuple[Path | None, list[str]]:
    conn = sqlite3.connect(db_path)
    changes: list[str] = []
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='section_purpose_map'"
        ).fetchone() is not None
        if table_exists:
            for statement in INDEXES:
                conn.execute(statement)
            conn.commit()
            return None, []

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(
            f"{db_path.stem}_backup_section_purpose_{stamp}.db")
        shutil.copy2(db_path, backup)

        conn.execute(SECTION_TABLE)
        changes.append("section_purpose_map")
        for statement in INDEXES:
            conn.execute(statement)
        conn.commit()
        return backup, changes
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    backup, changes = migrate(Path(args.db))
    if changes:
        print(f"Backup: {backup}")
        print("Added: " + ", ".join(changes))
    else:
        print("Schema already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
