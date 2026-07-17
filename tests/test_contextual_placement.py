"""Tests for contextual link placement (analysis/contextual_placement.py) and
the enrichment it produces in link_recommendations."""

import sqlite3

from analysis.contextual_placement import (best_placement, target_keywords,
                                          _split_sentences)


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
