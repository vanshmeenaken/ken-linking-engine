"""Tests for the vector-search foundation (analysis/vector_store.py)."""

import sqlite3

from analysis.vector_store import VectorStore


def test_fit_and_search_ranks_by_relevance():
    items = [
        ("a", "Cold storage and refrigerated warehousing solutions for perishables."),
        ("b", "Car rental and mobility services across major cities."),
        ("c", "Unrelated commentary about the weather and travel plans."),
    ]
    store = VectorStore.fit(items)
    results = store.search("Cold Storage Refrigeration", top_k=3)
    assert results[0].item_id == "a"
    # scores are sorted descending
    assert results[0].score >= results[1].score >= results[2].score


def test_search_excludes_ids():
    items = [("a", "car rental market"), ("b", "car rental services")]
    store = VectorStore.fit(items)
    results = store.search("car rental", top_k=5, exclude={"a"})
    assert all(r.item_id != "a" for r in results)


def test_similarity_between_two_known_items():
    items = [("a", "electric vehicle charging infrastructure"),
             ("b", "electric vehicle charging stations"),
             ("c", "completely different topic about textiles")]
    store = VectorStore.fit(items)
    assert store.similarity("a", "b") > store.similarity("a", "c")


def test_similarity_unknown_id_returns_zero():
    store = VectorStore.fit([("a", "some text")])
    assert store.similarity("a", "does-not-exist") == 0.0


def test_empty_store_length():
    store = VectorStore.fit([])
    assert len(store) == 0


def test_len_matches_item_count():
    store = VectorStore.fit([("a", "text one"), ("b", "text two")])
    assert len(store) == 2


# ── persisted vectors (paragraph_embeddings, written by the placement run) ───

def test_paragraph_embeddings_table_populated():
    conn = sqlite3.connect("ken_links.db")
    n = conn.execute("SELECT COUNT(*) FROM paragraph_embeddings").fetchone()[0]
    conn.close()
    assert n > 0, "run scripts/22_place_contextual_links.py to populate it"


def test_paragraph_embedding_vectors_are_valid_json():
    import json
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        "SELECT embedding_vector FROM paragraph_embeddings "
        "WHERE embedding_vector IS NOT NULL LIMIT 1").fetchone()
    conn.close()
    assert row is not None
    vec = json.loads(row[0])
    assert isinstance(vec, dict)
    assert all(isinstance(v, (int, float)) for v in vec.values())
