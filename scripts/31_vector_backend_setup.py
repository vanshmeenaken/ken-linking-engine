"""Build the persistent vector index (ken_vectors.db) from stored vectors.

Densifies every TF-IDF vector in semantic_embeddings (pages) and
paragraph_embeddings (paragraphs) into two sqlite-vec tables and verifies
row counts match the source exactly. Re-runnable: rebuilds from scratch
each time (the source of truth stays in ken_links.db; ken_vectors.db is a
derived index).

The master PRD end-state names Postgres/pgvector; this machine has neither
Docker nor Postgres, so the index swap uses sqlite-vec behind the same
interface - swapping to pgvector later is a backend change only. See
analysis/vector_index.py.

Usage:
    python scripts/31_vector_backend_setup.py
    set VECTOR_BACKEND=sqlite_vec   (per-session, to route searches to it)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.vector_index import SqliteVecIndex, sqlite_vec_available

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
DEFAULT_OUT = ROOT / "ken_vectors.db"

SOURCES = {
    "page_vectors": ("SELECT node_id, embedding_vector FROM semantic_embeddings "
                     "WHERE embedding_vector IS NOT NULL"),
    "paragraph_vectors": ("SELECT paragraph_id, embedding_vector "
                          "FROM paragraph_embeddings "
                          "WHERE embedding_vector IS NOT NULL"),
}


def build(db_path: Path, out_path: Path) -> dict[str, tuple[int, int]]:
    """Returns {table: (source_rows, indexed_rows)} - the two must match."""
    if out_path.exists():
        out_path.unlink()
    src = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    results: dict[str, tuple[int, int]] = {}
    try:
        for table, query in SOURCES.items():
            rows = src.execute(query).fetchall()
            vectors = [(item_id, json.loads(vec)) for item_id, vec in rows]
            vocab = sorted({t for _, v in vectors for t in v})
            index = SqliteVecIndex(vocab, path=str(out_path) + f".{table}")
            for item_id, vec in vectors:
                index.add(item_id, vec)
            results[table] = (len(rows), len(index))
            index.close()
    finally:
        src.close()
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    if not sqlite_vec_available():
        print("sqlite-vec is not installed or cannot load. "
              "pip install sqlite-vec, then re-run.")
        return 1

    results = build(Path(args.db), Path(args.out))
    ok = True
    for table, (source_rows, indexed) in results.items():
        match = "OK" if source_rows == indexed else "MISMATCH"
        ok = ok and source_rows == indexed
        print(f"{table}: source {source_rows} -> indexed {indexed}  [{match}]")
    print(f"Index files: {args.out}.page_vectors / .paragraph_vectors")
    print("Route searches through it with: set VECTOR_BACKEND=sqlite_vec")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
