"""Vector-search foundation: a real embed/index/search API on top of vectors,
built to work today at 500 pages and scale to the full ~42,000-page catalogue
without changing the interface.

Design (what "scales later" actually means here):
  - The public surface is `VectorStore.add(id, text)` and
    `VectorStore.search(query_text, top_k)`. Nothing outside this module knows
    HOW a piece of text becomes a vector or HOW nearest neighbours are found.
  - Today: vectors are TF-IDF (analysis/tfidf_similarity.py - deterministic,
    stdlib only, already computed for 498 pages). Search is brute-force cosine
    over vectors held in memory, loaded from SQLite. This is exact and fast
    enough for hundreds to a few thousand items - proven at today's 500-page
    scale.
  - At the full 42,000-page / paragraph-level scale, two things swap in behind
    the SAME interface, with zero change to any caller:
      1. the embedder: TF-IDF -> a real embedding model (sentence-transformers
         or an API), which is what actually catches synonyms ("EV" <->
         "electric vehicle") that TF-IDF term-overlap cannot
      2. the index: brute-force cosine -> a proper vector index/DB
         (pgvector, FAISS, or similar) for fast top-k over millions of vectors
  - Honest limitation of today's TF-IDF vectors: they weight shared TERMS, not
    shared MEANING. They are a real improvement over raw keyword-overlap
    (corpus-aware weighting, downweights boilerplate like "market"/"report"),
    but they will not match "EV" to "electric vehicle" the way a trained
    embedding model would. That upgrade is the swap described above, not a
    rewrite of anything that calls this module.

Storage: reuses semantic_embeddings (page-level, already populated in Phase 2)
and adds paragraph_embeddings (new, paragraph-level) - see
scripts/23_vector_search_migration.py.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from analysis.tfidf_similarity import Corpus, build_corpus, cosine

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "ken_links.db"

EMBEDDING_MODEL = "tfidf-v1"  # recorded per-vector so a future model swap is
                              # detectable and re-embedding can target only
                              # stale rows

# Index backend: "bruteforce" (default - exact cosine over in-memory dicts,
# proven at 500-page scale) or "sqlite_vec" (a real vector index; see
# analysis/vector_index.py). Selection is per-process via env so nothing
# breaks when the extension is missing - an unavailable backend falls back
# to bruteforce with a warning instead of failing.
VECTOR_BACKEND = os.environ.get("VECTOR_BACKEND", "bruteforce").lower()


@dataclass
class SearchResult:
    item_id: str
    score: float
    text: str = ""


@dataclass
class VectorStore:
    """An embed/index/search layer. `corpus` supplies the IDF weights (fit
    once over the full document set so scores are comparable across items)."""
    corpus: Corpus
    _vectors: dict[str, dict[str, float]] = field(default_factory=dict)
    _texts: dict[str, str] = field(default_factory=dict)

    _index: object | None = None  # SqliteVecIndex when the backend is active

    @classmethod
    def fit(cls, items: list[tuple[str, str]],
            backend: str | None = None) -> "VectorStore":
        """Build a store from (item_id, text) pairs, fitting IDF over all of
        them so results are internally consistent. `backend` overrides the
        VECTOR_BACKEND env selection for this store."""
        corpus = build_corpus([text for _, text in items])
        store = cls(corpus=corpus)
        for item_id, text in items:
            store.add(item_id, text)
        chosen = (backend or VECTOR_BACKEND).lower()
        if chosen == "sqlite_vec" and store._vectors:
            try:
                from analysis.vector_index import SqliteVecIndex
                vocab = sorted({t for v in store._vectors.values() for t in v})
                index = SqliteVecIndex(vocab)
                for item_id, vec in store._vectors.items():
                    index.add(item_id, vec)
                store._index = index
            except Exception as exc:  # extension missing/broken: stay exact
                import warnings
                warnings.warn(f"sqlite_vec backend unavailable ({exc}); "
                              "falling back to bruteforce")
        return store

    def add(self, item_id: str, text: str) -> None:
        self._vectors[item_id] = self.corpus.vector(text)
        self._texts[item_id] = text

    def embed_query(self, text: str) -> dict[str, float]:
        """Vectorise arbitrary query text against this store's fitted IDF."""
        return self.corpus.vector(text)

    def search(self, query_text: str, top_k: int = 5,
              exclude: set[str] | None = None) -> list[SearchResult]:
        """Top-k items by cosine similarity to `query_text`. Uses the
        vector index when one was built at fit time; exact brute-force
        cosine otherwise. Results are identical either way (the index is
        exact at this scale); only the lookup mechanism differs."""
        qvec = self.embed_query(query_text)
        exclude = exclude or set()
        if self._index is not None:
            hits = self._index.search(qvec, top_k=top_k + len(exclude))
            return [SearchResult(item_id=iid, score=score,
                                 text=self._texts.get(iid, ""))
                    for iid, score in hits if iid not in exclude][:top_k]
        scored = [
            SearchResult(item_id=iid, score=cosine(qvec, vec), text=self._texts[iid])
            for iid, vec in self._vectors.items() if iid not in exclude
        ]
        scored.sort(key=lambda r: -r.score)
        return scored[:top_k]

    def similarity(self, item_id_a: str, item_id_b: str) -> float:
        va, vb = self._vectors.get(item_id_a), self._vectors.get(item_id_b)
        if va is None or vb is None:
            return 0.0
        return cosine(va, vb)

    def __len__(self) -> int:
        return len(self._vectors)


def load_page_store(db_path: Path = DEFAULT_DB) -> VectorStore:
    """Build a VectorStore over every active page's stored document text
    (semantic_embeddings.source_text, populated in Phase 2)."""
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """SELECT e.node_id, e.source_text FROM semantic_embeddings e
               JOIN content_nodes n ON n.node_id = e.node_id
               WHERE n.status = 'active' AND e.source_text IS NOT NULL"""
        ).fetchall()
    finally:
        conn.close()
    return VectorStore.fit([(nid, text) for nid, text in rows])


def load_paragraph_store(node_ids: list[str] | None = None,
                         db_path: Path = DEFAULT_DB) -> VectorStore:
    """Build a VectorStore over stored paragraph text (paragraph_embeddings).
    Optionally restrict to a set of source node_ids."""
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        q = "SELECT paragraph_id, paragraph_text FROM paragraph_embeddings"
        params: list = []
        if node_ids:
            placeholders = ",".join("?" * len(node_ids))
            q += f" WHERE node_id IN ({placeholders})"
            params = list(node_ids)
        rows = conn.execute(q, params).fetchall()
    finally:
        conn.close()
    return VectorStore.fit([(pid, text) for pid, text in rows])


def store_paragraph_vectors(store: VectorStore, db_path: Path = DEFAULT_DB) -> None:
    """Persist a store's fitted vectors back into paragraph_embeddings, so a
    future run can reload them without recomputation (mirrors how
    semantic_embeddings caches page-level vectors)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for item_id, vec in store._vectors.items():
            conn.execute(
                "UPDATE paragraph_embeddings SET embedding_vector = ?, "
                "embedding_model = ? WHERE paragraph_id = ?",
                (json.dumps(vec), EMBEDDING_MODEL, item_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
