"""Add the paragraph_evidence_map table for Agent 8 (master PRD 13.8).

One row per meaningful paragraph of a crawled page: which section it lives
in, whether it makes a market claim, whether that claim is supported by an
internal link, and the best evidence page (report or case study) found for
it. Additive and idempotent; backs up the database before changing schema
(project safety rule: backup before migrations).
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS paragraph_evidence_map (
    evidence_row_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES content_nodes(node_id),
    url TEXT NOT NULL,
    section_heading TEXT,
    section_purpose TEXT,
    paragraph_index INTEGER NOT NULL,
    paragraph_text TEXT NOT NULL,
    paragraph_hash TEXT NOT NULL,
    classification TEXT NOT NULL,
    has_numeric_claim INTEGER DEFAULT 0,
    support_status TEXT,
    evidence_target_node_id TEXT REFERENCES content_nodes(node_id),
    evidence_target_url TEXT,
    evidence_type TEXT,
    evidence_score REAL,
    crawled_at TEXT,
    created_at TEXT,
    updated_at TEXT
)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_paragraph_evidence_node "
    "ON paragraph_evidence_map(node_id)",
    "CREATE INDEX IF NOT EXISTS ix_paragraph_evidence_support "
    "ON paragraph_evidence_map(support_status)",
    "CREATE INDEX IF NOT EXISTS ix_paragraph_evidence_hash "
    "ON paragraph_evidence_map(paragraph_hash)",
]


def migrate(db_path: Path) -> tuple[Path | None, list[str]]:
    conn = sqlite3.connect(db_path)
    changes: list[str] = []
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='paragraph_evidence_map'"
        ).fetchone() is not None
        if table_exists:
            for statement in INDEXES:
                conn.execute(statement)
            conn.commit()
            return None, []

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(
            f"{db_path.stem}_backup_paragraph_evidence_{stamp}.db")
        shutil.copy2(db_path, backup)

        conn.execute(EVIDENCE_TABLE)
        changes.append("paragraph_evidence_map")
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
