"""Phase 2 schema migration: create the 5 intelligence-layer tables.

Additive only — no Phase 1 table or column is altered. Idempotent — every
statement is CREATE ... IF NOT EXISTS, safe to re-run. A timestamped backup
copy of the database file is written before any change.

Usage:
    python scripts/09_phase2_migration.py                 # migrate ken_links.db
    python scripts/09_phase2_migration.py --verify-only   # check, change nothing
    python scripts/09_phase2_migration.py --db path.db    # migrate another file

Design: docs/03-DATABASE/04-PHASE2-SCHEMA-DESIGN.md
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

PHASE2_TABLES = {
    "node_entities": """
        CREATE TABLE IF NOT EXISTS node_entities (
            node_entity_id    TEXT PRIMARY KEY,
            node_id           TEXT NOT NULL REFERENCES content_nodes(node_id),
            entity_id         TEXT NOT NULL REFERENCES content_entities(entity_id),
            entity_role       TEXT NOT NULL,
            source_field      TEXT,
            extracted_value   TEXT,
            normalized_value  TEXT,
            confidence_score  REAL DEFAULT 0.0,
            extraction_method TEXT,
            status            TEXT DEFAULT 'extracted',
            created_at        TEXT,
            updated_at        TEXT,
            UNIQUE (node_id, entity_id, entity_role)
        )""",
    "entity_extraction_logs": """
        CREATE TABLE IF NOT EXISTS entity_extraction_logs (
            log_id               INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id               TEXT NOT NULL,
            node_id              TEXT REFERENCES content_nodes(node_id),
            operation            TEXT,
            status               TEXT,
            entities_found       INTEGER DEFAULT 0,
            low_confidence_count INTEGER DEFAULT 0,
            error                TEXT,
            notes                TEXT,
            created_at           TEXT
        )""",
    "semantic_embeddings": """
        CREATE TABLE IF NOT EXISTS semantic_embeddings (
            embedding_id     TEXT PRIMARY KEY,
            node_id          TEXT NOT NULL UNIQUE REFERENCES content_nodes(node_id),
            text_hash        TEXT NOT NULL,
            source_text      TEXT,
            embedding_model  TEXT,
            embedding_vector TEXT,
            created_at       TEXT,
            updated_at       TEXT
        )""",
    "seo_opportunities": """
        CREATE TABLE IF NOT EXISTS seo_opportunities (
            opportunity_id   TEXT PRIMARY KEY,
            node_id          TEXT NOT NULL REFERENCES content_nodes(node_id),
            opportunity_type TEXT NOT NULL,
            priority         TEXT,
            reason           TEXT,
            evidence         TEXT,
            seo_score        REAL DEFAULT 0.0,
            business_score   REAL DEFAULT 0.0,
            status           TEXT DEFAULT 'open',
            created_at       TEXT,
            updated_at       TEXT,
            UNIQUE (node_id, opportunity_type)
        )""",
    "integration_placeholders": """
        CREATE TABLE IF NOT EXISTS integration_placeholders (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source         TEXT NOT NULL,
            node_id        TEXT REFERENCES content_nodes(node_id),
            url            TEXT,
            metric_name    TEXT,
            metric_value   REAL,
            date_range     TEXT,
            status         TEXT DEFAULT 'placeholder',
            notes          TEXT,
            created_at     TEXT
        )""",
}

PHASE2_INDEXES = [
    # Duplicate prevention at the DB level (review finding: Agent 2 dedupes in
    # Python, but nothing stopped another writer from inserting a duplicate)
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_entities_normalized_type "
    "ON content_entities(normalized_name, entity_type)",
    # Duplicate-edge prevention for Agent 3 (Day 6/Jul 9). Agent 3 always
    # writes symmetric edge types (same_market, same_industry, ...) with a
    # canonical source<target ordering, so this triple is a true natural key.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_relationship_edges_source_target_type "
    "ON relationship_edges(source_node_id, target_node_id, relationship_type)",
    "CREATE INDEX IF NOT EXISTS ix_node_entities_node_id ON node_entities(node_id)",
    "CREATE INDEX IF NOT EXISTS ix_node_entities_entity_id ON node_entities(entity_id)",
    "CREATE INDEX IF NOT EXISTS ix_node_entities_status ON node_entities(status)",
    "CREATE INDEX IF NOT EXISTS ix_node_entities_confidence ON node_entities(confidence_score)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_logs_run_id ON entity_extraction_logs(run_id)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_logs_node_id ON entity_extraction_logs(node_id)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_logs_status ON entity_extraction_logs(status)",
    "CREATE INDEX IF NOT EXISTS ix_semantic_embeddings_text_hash ON semantic_embeddings(text_hash)",
    "CREATE INDEX IF NOT EXISTS ix_seo_opportunities_node_id ON seo_opportunities(node_id)",
    "CREATE INDEX IF NOT EXISTS ix_seo_opportunities_type ON seo_opportunities(opportunity_type)",
    "CREATE INDEX IF NOT EXISTS ix_seo_opportunities_priority ON seo_opportunities(priority)",
    "CREATE INDEX IF NOT EXISTS ix_seo_opportunities_status ON seo_opportunities(status)",
    "CREATE INDEX IF NOT EXISTS ix_integration_placeholders_source ON integration_placeholders(source)",
    "CREATE INDEX IF NOT EXISTS ix_integration_placeholders_node_id ON integration_placeholders(node_id)",
    "CREATE INDEX IF NOT EXISTS ix_integration_placeholders_metric ON integration_placeholders(metric_name)",
]

PHASE1_TABLES = ["content_nodes", "content_entities", "relationship_edges", "crawl_logs"]


def backup_database(db_path: Path) -> Path:
    """Copy the DB file to a timestamped backup next to it. Abort on failure."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}_backup_phase2_{stamp}.db")
    shutil.copy2(db_path, backup_path)
    if not backup_path.exists() or backup_path.stat().st_size != db_path.stat().st_size:
        raise RuntimeError(f"Backup verification failed: {backup_path}")
    return backup_path


def existing_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def verify(conn: sqlite3.Connection) -> bool:
    """Print the state of all 9 expected tables; return True if all 5 new exist."""
    present = existing_tables(conn)
    ok = True
    print(f"{'table':<28} {'exists':<7} rows")
    for name in PHASE1_TABLES + list(PHASE2_TABLES):
        if name in present:
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(f"{name:<28} yes     {count}")
        else:
            print(f"{name:<28} MISSING -")
            ok = False
    index_count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%'"
    ).fetchone()[0]
    print(f"\nix_* indexes present: {index_count}")
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
        before = existing_tables(conn)
        with conn:  # single transaction
            for name, ddl in PHASE2_TABLES.items():
                conn.execute(ddl)
                print(f"{'created' if name not in before else 'exists '}: {name}")
            for statement in PHASE2_INDEXES:
                conn.execute(statement)
        print(f"\nIndexes ensured: {len(PHASE2_INDEXES)}")
        print("\n=== Post-migration verification ===")
        return 0 if verify(conn) else 2
    except Exception as exc:
        print(f"ERROR: migration failed, DB unchanged (transaction rolled back): {exc}",
              file=sys.stderr)
        print(f"Backup available at: {backup_path}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--verify-only", action="store_true",
                        help="Report table/index state without changing anything")
    args = parser.parse_args(argv)
    return migrate(Path(args.db), args.verify_only)


if __name__ == "__main__":
    raise SystemExit(main())
