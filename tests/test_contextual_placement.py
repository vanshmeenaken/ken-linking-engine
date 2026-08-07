"""Tests for contextual link placement (analysis/contextual_placement.py) and
the enrichment it produces in link_recommendations."""

import sqlite3

from analysis.contextual_placement import (best_placement, best_placement_semantic,
                                          is_boilerplate, is_toc_or_heading,
                                          subject_text, target_keywords,
                                          _split_sentences)
from analysis.vector_store import VectorStore


# ── subject vs geography: the precision rule ─────────────────────────────────

def test_keywords_are_subject_not_geography():
    # geography must be excluded so only the market/subject can place a link
    kw = target_keywords("Cold Storage", "uae", "middle east", "UAE Cold Storage Market")
    assert "cold" in kw and "storage" in kw
    assert "uae" not in kw and "middle" not in kw and "east" not in kw


def test_geography_only_overlap_is_not_a_contextual_home():
    # a paragraph that shares only the region, not the subject, must NOT match
    paras = ["A Middle Eastern real-estate consulting firm expanded into Saudi "
             "Arabia to diversify its property portfolio across the region."]
    kw = target_keywords("Cold Storage", "uae", "middle east", "UAE Cold Storage Market")
    assert best_placement(paras, kw) is None


def test_subject_overlap_is_a_contextual_home():
    paras = ["The future of the coin operated commercial laundry market looks "
             "strong as demand for self-service laundry rises across cities."]
    kw = target_keywords("Coin Operated Commercial Laundry", "thailand", "apac",
                         "Thailand Coin Operated Commercial Laundry Market")
    placed = best_placement(paras, kw)
    assert placed is not None
    assert "laundry" in placed["sentence"].lower()


def test_picks_the_most_relevant_sentence_in_a_paragraph():
    para = ("Intro sentence with nothing useful here. The car rental market is "
            "dominated by short-term and long-term rental services. Closing line.")
    kw = target_keywords("Car Rental", "vietnam", "apac", "Vietnam Car Rental Market")
    placed = best_placement([para], kw)
    assert placed is not None
    assert "rental" in placed["sentence"].lower()


def test_split_sentences_ignores_fragments():
    s = _split_sentences("Short. This is a full sentence long enough to keep.")
    assert all(len(x) > 30 for x in s)


# ── vector-search placement ──────────────────────────────────────────────────

def test_vector_search_finds_the_relevant_paragraph():
    paras = [
        "Intro sentence with nothing useful here about general trends.",
        "The car rental market is dominated by short-term and long-term "
        "rental services across the region.",
        "Closing thoughts on the broader economy and unrelated topics.",
    ]
    placed = best_placement_semantic(paras, "Car Rental Market")
    assert placed is not None
    assert placed["paragraph_index"] == 1
    assert placed["method"] == "vector"


def test_vector_search_returns_none_below_threshold():
    paras = ["A paragraph about something completely unrelated to the query topic."]
    placed = best_placement_semantic(paras, "Cold Storage Refrigeration Logistics")
    assert placed is None


def test_vector_search_empty_paragraphs_returns_none():
    assert best_placement_semantic([], "Car Rental Market") is None


# ── boilerplate filtering (regression: company pitch outscored real content) ─

def test_boilerplate_detected():
    assert is_boilerplate(
        "We have set a benchmark in the industry by offering our clients "
        "with syndicated and customized market research reports.")
    assert is_boilerplate(
        "What makes us stand out is that our consultants follows Robust, "
        "Refine and Result methodology.")
    assert not is_boilerplate(
        "Brazil Pharmaceuticals market in terms of revenue increased at a "
        "double digit CAGR during the review period.")


def test_boilerplate_never_wins_over_genuine_content():
    # Regression: a company "why choose us" paragraph previously outscored a
    # real market-content paragraph for a target whose promotional title words
    # ("Growth, Players, Trade Insights") happened to overlap with Ken's sales
    # language. The boilerplate paragraph must be filtered before ranking, not
    # merely outscored, so it can NEVER win regardless of query wording.
    paras = [
        "Brazil Pharmaceuticals market in terms of revenue increased at a "
        "double digit CAGR during the review period.",
        "We have set a benchmark in the industry by offering our clients "
        "with syndicated and customized market research reports featuring "
        "coverage of entire market as well as meticulous research and "
        "analyst insights.",
    ]
    filtered = [p for p in paras if not is_boilerplate(p)]
    assert len(filtered) == 1
    q = subject_text("Pharmaceutical Market",
                     "Vietnam Pharmaceutical Market Entry Strategy | Growth, "
                     "Players & Trade Insights")
    placed = best_placement_semantic(filtered, q)
    assert placed is not None
    assert "Brazil Pharmaceuticals" in placed["sentence"]


# ── TOC/heading filtering (regression: TOC lines placed as if they were prose) ─

def test_toc_headings_detected():
    # Regression: report pages render their Table of Contents as <p> tags. A
    # TOC line's heading literally repeats the target market name (e.g.
    # "5.3 Indonesia Online Grocery Market Segmentation..."), so it vector-
    # matched well despite being a heading label, not a sentence to embed a
    # link in. Found via manual review of a real placed recommendation.
    assert is_toc_or_heading("1.1 Executive Summary- How is Online Grocery Market Positioned")
    assert is_toc_or_heading("5.3 Indonesia Online Grocery Market Segmentation By Mode of Payment")
    assert is_toc_or_heading("9.1.1 Cross Comparison Matrix of Major Players (Year of Establishment)")


def test_toc_filter_does_not_reject_genuine_sentences():
    # A sentence that happens to start with a number/percentage must NOT be
    # caught: "5.3%" has no whitespace right after the digits, only "5.3 "
    # (a bare TOC-style numbering followed by a space) should match.
    assert not is_toc_or_heading(
        "5.3% of the total demand comes from tier-2 cities, according to surveys.")
    assert not is_toc_or_heading(
        "Brazil Pharmaceuticals market in terms of revenue increased at a "
        "double digit CAGR during the review period.")


def test_fetch_paragraphs_filters_toc_and_boilerplate_together(monkeypatch):
    import analysis.contextual_placement as cp

    class _FakeResp:
        status_code = 200
        text = (
            "<html><body>"
            "<p>1.1 Executive Summary of the market landscape overview here</p>"
            "<p>Brazil Pharmaceuticals market in terms of revenue increased at "
            "a double digit CAGR during the review period across the country.</p>"
            "<p>We have set a benchmark in the industry by offering our clients "
            "with syndicated and customized market research reports and more.</p>"
            "</body></html>"
        )
        apparent_encoding = "utf-8"
        def raise_for_status(self): pass

    monkeypatch.setattr(cp.requests, "get", lambda *a, **k: _FakeResp())
    paras = cp.fetch_paragraphs("https://example.test/page")
    assert len(paras) == 1
    assert "Brazil Pharmaceuticals" in paras[0]


# ── the enriched recommendations in the DB ───────────────────────────────────

def test_recommendations_have_placement_and_varied_anchors():
    conn = sqlite3.connect("ken_links.db")
    # every recommendation has a placement type
    missing = conn.execute(
        "SELECT COUNT(*) FROM link_recommendations "
        "WHERE placement_type IS NULL OR placement_type = ''").fetchone()[0]
    # contextual ones carry the sentence they belong in
    ctx_no_sentence = conn.execute(
        "SELECT COUNT(*) FROM link_recommendations "
        "WHERE placement_type='contextual_body' AND "
        "(suggested_sentence IS NULL OR suggested_sentence='')").fetchone()[0]
    # no target receives the same anchor from two sources
    dup_anchor = conn.execute(
        "SELECT COUNT(*) FROM (SELECT target_node_id, anchor_text, COUNT(*) k "
        "FROM link_recommendations GROUP BY target_node_id, anchor_text "
        "HAVING k > 1)").fetchone()[0]
    conn.close()
    assert missing == 0
    assert ctx_no_sentence == 0, "a contextual link has no sentence to place it in"
    assert dup_anchor == 0, "a target still gets the same anchor from two sources"
