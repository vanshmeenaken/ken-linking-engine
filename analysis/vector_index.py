"""A real vector index backend (sqlite-vec) behind the VectorStore interface.

The master PRD's end-state names Postgres/pgvector for the 42k-page scale.
This machine has neither Docker nor Postgres, and pgvector has no official
Windows binary, so the index swap lands on sqlite-vec instead: a genuine
ANN-capable vector extension with the same role (replace brute-force cosine
with an indexed KNN query). The VectorStore interface is unchanged, so
swapping sqlite-vec for pgvector later is a backend change only - exactly
the deviation-and-revisit the vector_store design notes describe.

TF-IDF vectors are sparse dicts (term -> weight); a vec0 table needs dense
fixed-dimension floats. The index fixes its vocabulary at build time (the
fitted corpus's vocabulary), densifies each vector once, and answers top-k
via an indexed cosine MATCH query.
"""
from __future__ import annotations

import sqlite3
import struct


def sqlite_vec_available() -> bool:
    try:
        import sqlite_vec  # noqa: F401
        db = sqlite3.connect(":memory:")
        db.enable_load_extension(True)
        import sqlite_vec as sv
        sv.load(db)
        db.close()
        return True
    except Exception:
        return False


def _pack(values: list[float]) -> bytes:
    return struct.pack(f"{len(values)}f", *values)


class SqliteVecIndex:
    """Indexed top-k cosine search over dense-ified sparse vectors."""

    def __init__(self, vocabulary: list[str], path: str = ":memory:"):
        import sqlite_vec
        self.vocab = {term: i for i, term in enumerate(vocabulary)}
        self.dim = max(len(self.vocab), 1)
        self._ids: dict[int, str] = {}
        self.db = sqlite3.connect(path)
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self.db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING "
            f"vec0(embedding float[{self.dim}] distance_metric=cosine)")

    def _dense(self, sparse: dict[str, float]) -> list[float]:
        dense = [0.0] * self.dim
        for term, weight in (sparse or {}).items():
            i = self.vocab.get(term)
            if i is not None:
                dense[i] = weight
        return dense

    def add(self, item_id: str, sparse_vector: dict[str, float]) -> None:
        rowid = len(self._ids) + 1
        self._ids[rowid] = item_id
        self.db.execute(
            "INSERT INTO vectors(rowid, embedding) VALUES (?, ?)",
            (rowid, _pack(self._dense(sparse_vector))))

    def search(self, sparse_query: dict[str, float],
               top_k: int = 5) -> list[tuple[str, float]]:
        """[(item_id, cosine_similarity)] best-first. An all-zero query (no
        vocabulary overlap at all) returns [] - nothing genuinely matches."""
        dense = self._dense(sparse_query)
        if not any(dense):
            return []
        rows = self.db.execute(
            "SELECT rowid, distance FROM vectors WHERE embedding MATCH ? "
            "AND k = ?", (_pack(dense), max(int(top_k), 1))).fetchall()
        return [(self._ids[rowid], 1.0 - distance) for rowid, distance in rows]

    def __len__(self) -> int:
        return len(self._ids)

    def close(self) -> None:
        self.db.close()
