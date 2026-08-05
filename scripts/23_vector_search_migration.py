"""Vector-search schema migration: adds paragraph_embeddings.

Additive only, idempotent (CREATE ... IF NOT EXISTS), backs up first - same
pattern as scripts/09_phase2_migration.py and scripts/21_phase3_migration.py.

paragraph_embeddings stores one row per body paragraph of a crawled source
page: the paragraph's text and its vector (analysis/vector_store.py), so
contextual placement can rank paragraphs by similarity instead of recomputing
vectors on every run.

Usage:
    python scripts/23_vector_search_migration.py
    python scripts/23_vector_search_migration.py --verify-only
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "ken_links.db"

DDL = """
    CREATE TABLE IF NOT EXISTS paragraph_embeddings (
        paragraph_id      TEXT PRIMARY KEY,
        node_id           TEXT NOT NULL REFERENCES content_nodes(node_id),
        paragraph_index   INTEGER NOT NULL,
        paragraph_text    TEXT NOT NULL,
        embedding_model   TEXT,
        embedding_vector  TEXT,
        created_at        TEXT,
        updated_at        TEXT,
        UNIQUE (node_id, paragraph_index)
    )"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_paragraph_embeddings_node "
    "ON paragraph_embeddings(node_id)",
]


def backup_database(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}_backup_vectorsearch_{stamp}.db")
    shutil.copy2(db_path, backup_path)
    if not backup_path.exists() or backup_path.stat().st_size != db_path.stat().st_size:
        raise RuntimeError(f"Backup verification failed: {backup_path}")
    return backup_path


def verify(conn: sqlite3.Connection) -> bool:
    tables = {r[0] for r in
              conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    present = "paragraph_embeddings" in tables
    if present:
        n = conn.execute("SELECT COUNT(*) FROM paragraph_embeddings").fetchone()[0]
        print(f"paragraph_embeddings: yes    rows={n}")
    else:
        print("paragraph_embeddings: MISSING")
    return present


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
        conn.execute("BEGIN")
        conn.execute(DDL)
        for idx in INDEXES:
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
