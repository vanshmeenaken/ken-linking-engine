"""Tests for the vector index backend (analysis/vector_index.py) and its
integration into VectorStore: backend parity (same results both ways),
graceful fallback, and the setup script's count verification."""

import pytest

from analysis.vector_index import SqliteVecIndex, sqlite_vec_available
from analysis.vector_store import VectorStore

FIXTURE = [
    ("a", "The car rental market is dominated by short-term rental services."),
    ("b", "Cold storage warehousing capacity is expanding across the region."),
    ("c", "Electric vehicle charging infrastructure grows with EV adoption."),
    ("d", "The cold chain logistics market supports frozen food distribution."),
]

needs_vec = pytest.mark.skipif(not sqlite_vec_available(),
                               reason="sqlite-vec not installed")


@needs_vec
def test_backend_parity_same_top1():
    # both backends must return the SAME best match for the same query -
    # the index changes the lookup mechanism, never the answer
    brute = VectorStore.fit(FIXTURE, backend="bruteforce")
    indexed = VectorStore.fit(FIXTURE, backend="sqlite_vec")
    assert indexed._index is not None, "sqlite_vec index was not built"
    for query in ("cold storage refrigerated warehouse",
                  "car rental services", "EV charging"):
        b = brute.search(query, top_k=1)[0]
        i = indexed.search(query, top_k=1)[0]
        assert b.item_id == i.item_id, f"backends disagree for '{query}'"
        assert abs(b.score - i.score) < 0.01  # same cosine, float tolerance


@needs_vec
def test_backend_parity_respects_exclude():
    indexed = VectorStore.fit(FIXTURE, backend="sqlite_vec")
    top = indexed.search("cold storage refrigerated warehouse", top_k=2,
                         exclude={"b"})
    assert all(r.item_id != "b" for r in top)


@needs_vec
def test_index_returns_empty_for_no_overlap_query():
    indexed = VectorStore.fit(FIXTURE, backend="sqlite_vec")
    # a query sharing no vocabulary with the corpus matches nothing - the
    # index must say so rather than return arbitrary neighbours
    assert indexed.search("zzz qqq xxx", top_k=3) == []


def test_unknown_backend_falls_back_to_bruteforce():
    store = VectorStore.fit(FIXTURE, backend="no_such_backend")
    assert store._index is None
    assert store.search("cold storage", top_k=1)[0].item_id in ("b", "d")


def test_default_backend_is_bruteforce():
    # nothing in the existing pipeline changes behavior without opting in
    store = VectorStore.fit(FIXTURE)
    assert store._index is None


@needs_vec
def test_setup_script_counts_match(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "vector_setup", Path(__file__).resolve().parent.parent / "scripts" /
        "31_vector_backend_setup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = mod.build(Path("ken_links.db"), tmp_path / "vectors.db")
    assert results["page_vectors"][0] > 0
    for table, (source_rows, indexed) in results.items():
        assert source_rows == indexed, f"{table} count mismatch"
