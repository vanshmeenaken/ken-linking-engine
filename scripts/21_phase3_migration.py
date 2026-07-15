"""Phase 3 schema migration: create the recommendation-engine tables.

Additive only, no Phase 1/2 table or column is altered. Idempotent, every
statement is CREATE ... IF NOT EXISTS, safe to re-run. A timestamped backup
copy of the database file is written before any change.

Tables (master PRD 14.4 / 14.5):
  link_recommendations  every generated internal-link recommendation, scored
                        and status-tracked from pending through deployed
  anchor_banks          per-target anchor-text options and usage tracking,
                        so no single exact-match anchor over-dominates

Both key on node_id (the real join key, as relationship_edges does) and also
carry the URL fields the PRD lists, so the editorial/CMS layers have URLs
without a join.

Usage:
    python scripts/21_phase3_migration.py                 # migrate ken_links.db
    python scripts/21_phase3_migration.py --verify-only   # check, change nothing
    python scripts/21_phase3_migration.py --db path.db    # migrate another file
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

PHASE3_TABLES = {
    "link_recommendations": """
        CREATE TABLE IF NOT EXISTS link_recommendations (
            recommendation_id    TEXT PRIMARY KEY,
            source_node_id       TEXT NOT NULL REFERENCES content_nodes(node_id),
            target_node_id       TEXT NOT NULL REFERENCES content_nodes(node_id),
            source_url           TEXT,
            target_url           TEXT,
            target_canonical_url TEXT,
            relationship_type    TEXT,
            anchor_text          TEXT,
            anchor_variant       TEXT,
            placement_type       TEXT,
            placement_section    TEXT,
            suggested_sentence   TEXT,
            link_score           REAL DEFAULT 0.0,
            seo_score            REAL DEFAULT 0.0,
            business_score       REAL DEFAULT 0.0,
            ai_readiness_score   REAL DEFAULT 0.0,
            confidence_score     REAL DEFAULT 0.0,
            score_band           TEXT,
            risk_flag            TEXT,
            risk_reason          TEXT,
            recommendation_reason TEXT,
            validation_status    TEXT,
            status               TEXT DEFAULT 'pending',
            created_by           TEXT DEFAULT 'agent_6',
            approved_by          TEXT,
            deployed_by          TEXT,
            deployed_at          TEXT,
            rollback_available   INTEGER DEFAULT 0,
            created_at           TEXT,
            updated_at           TEXT,
            UNIQUE (source_node_id, target_node_id, relationship_type)
        )""",
    "anchor_banks": """
        CREATE TABLE IF NOT EXISTS anchor_banks (
            anchor_id                TEXT PRIMARY KEY,
            target_node_id           TEXT NOT NULL UNIQUE REFERENCES content_nodes(node_id),
            target_url               TEXT,
            primary_anchor           TEXT,
            secondary_anchors        TEXT,
            long_tail_anchors        TEXT,
            country_specific_anchors TEXT,
            market_specific_anchors  TEXT,
            commercial_anchors       TEXT,
            restricted_anchors       TEXT,
            anchor_usage_count       INTEGER DEFAULT 0,
            last_used_date           TEXT,
            overuse_flag             INTEGER DEFAULT 0,
            created_at               TEXT,
            updated_at               TEXT
        )""",
}

PHASE3_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_link_recs_source ON link_recommendations(source_node_id)",
    "CREATE INDEX IF NOT EXISTS ix_link_recs_target ON link_recommendations(target_node_id)",
    "CREATE INDEX IF NOT EXISTS ix_link_recs_status ON link_recommendations(status)",
    "CREATE INDEX IF NOT EXISTS ix_link_recs_band ON link_recommendations(score_band)",
    "CREATE INDEX IF NOT EXISTS ix_link_recs_score ON link_recommendations(link_score)",
    "CREATE INDEX IF NOT EXISTS ix_anchor_banks_target ON anchor_banks(target_node_id)",
]

CONTEXT_TABLES = ["content_nodes", "relationship_edges", "seo_opportunities"]


def backup_database(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}_backup_phase3_{stamp}.db")
    shutil.copy2(db_path, backup_path)
    if not backup_path.exists() or backup_path.stat().st_size != db_path.stat().st_size:
        raise RuntimeError(f"Backup verification failed: {backup_path}")
    return backup_path


def existing_tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def verify(conn: sqlite3.Connection) -> bool:
    present = existing_tables(conn)
    ok = True
    print(f"{'table':<24} {'exists':<7} rows")
    for name in CONTEXT_TABLES + list(PHASE3_TABLES):
        if name in present:
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(f"{name:<24} yes     {count}")
        else:
            print(f"{name:<24} MISSING -")
            if name in PHASE3_TABLES:
                ok = False
    idx = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
        "AND name LIKE 'ix_link_recs%' OR name LIKE 'ix_anchor%'"
    ).fetchone()[0]
    print(f"\nphase 3 indexes present: {idx}")
    return ok


def migrate(db_path: Path, verify_only: bool) -> int:
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 1

    if verify_only:
        conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        try:
            return 0 if verify(conn) else 2
        finally:
            conn.close()

    backup_path = backup_database(db_path)
    print(f"Backup written: {backup_path.name}")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN")
        for name, ddl in PHASE3_TABLES.items():
            conn.execute(ddl)
        for idx in PHASE3_INDEXES:
            conn.execute(idx)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print("Migration committed.\n")
    ok = verify(conn)
    conn.close()
    return 0 if ok else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    return migrate(Path(args.db), args.verify_only)


if __name__ == "__main__":
    raise SystemExit(main())
