"""Tests for the TF-IDF similarity engine (Phase 2, Day 2)."""

import math

from analysis.tfidf_similarity import build_corpus, cosine, tokenize


def test_tokenize_drops_stopwords_and_short_tokens():
    toks = tokenize("The India EV Market a to of")
    assert "india" in toks and "ev" in toks and "market" in toks
    assert "the" not in toks and "to" not in toks and "of" not in toks
    assert "a" not in toks  # length-1 dropped


def test_identical_documents_have_similarity_1():
    corpus = build_corpus(["india electric vehicle market", "saudi cement market"])
    v = corpus.vector("india electric vehicle market")
    assert abs(cosine(v, v) - 1.0) < 1e-9


def test_disjoint_documents_have_similarity_0():
    corpus = build_corpus([
        "india electric vehicle market",
        "bahrain pectin chemical market",
    ])
    a = corpus.vector("india electric vehicle")
    b = corpus.vector("bahrain pectin chemical")
    assert cosine(a, b) == 0.0


def test_partial_overlap_between_0_and_1():
    corpus = build_corpus([
        "india infusion pumps market",
        "saudi insulin infusion pumps market",
        "bahrain pectin market",
    ])
    a = corpus.vector("india infusion pumps market")
    b = corpus.vector("saudi insulin infusion pumps market")
    score = cosine(a, b)
    assert 0.0 < score < 1.0
    # shares "infusion pumps market" -> should be meaningfully similar
    assert score > 0.3


def test_idf_downweights_ubiquitous_terms():
    # 'market' in every doc -> near-zero idf; 'xenon' in one -> high idf
    corpus = build_corpus([
        "alpha market", "beta market", "gamma market", "xenon market",
    ])
    assert corpus.idf["market"] < corpus.idf["xenon"]


def test_cosine_symmetric():
    corpus = build_corpus(["a b c market", "b c d market", "x y z market"])
    a = corpus.vector("a b c market")
    b = corpus.vector("b c d market")
    assert abs(cosine(a, b) - cosine(b, a)) < 1e-12


def test_empty_and_unseen_text_safe():
    corpus = build_corpus(["india market", "saudi market"])
    assert corpus.vector("") == {}
    assert cosine({}, corpus.vector("india market")) == 0.0
    # entirely unseen terms -> empty vector, similarity 0
    assert corpus.vector("zzz qqq") == {}


def test_vector_is_unit_normalized():
    corpus = build_corpus(["india electric vehicle market", "saudi cement market"])
    v = corpus.vector("india electric vehicle market")
    norm = math.sqrt(sum(w * w for w in v.values()))
    assert abs(norm - 1.0) < 1e-9
