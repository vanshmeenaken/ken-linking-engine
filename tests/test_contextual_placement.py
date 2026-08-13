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
        "WHERE placement_type='contextual_body' "
        "AND placement_status='confirmed' AND "
        "(suggested_sentence IS NULL OR suggested_sentence='')").fetchone()[0]
    invalid_status = conn.execute(
        "SELECT COUNT(*) FROM link_recommendations "
        "WHERE placement_status NOT IN ('planned','confirmed','unresolved') "
        "OR placement_status IS NULL").fetchone()[0]
    # no target receives the same anchor from two sources
    dup_anchor = conn.execute(
        "SELECT COUNT(*) FROM (SELECT target_node_id, anchor_text, COUNT(*) k, "
        "SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) pending_count "
        "FROM link_recommendations WHERE status != 'rejected' "
        "GROUP BY target_node_id, anchor_text "
        "HAVING k > 1 AND pending_count > 0)").fetchone()[0]
    conn.close()
    assert missing == 0
    assert ctx_no_sentence == 0, "a contextual link has no sentence to place it in"
    assert invalid_status == 0
    assert dup_anchor == 0, "a pending link repeats an active anchor for its target"


# ── two links from the same source must never share a sentence ──────────────

def test_semantic_exclusion_forces_a_distinct_sentence():
    # regression: Russia's page had exactly one strong sentence, and two
    # different targets both anchored to the literal same sentence - found
    # via manual review of the live queue
    paras = [
        "The future of the Russia e-learning and skills platforms market "
        "appears promising, driven by technological advancements and "
        "evolving educational needs across the region.",
        "Investment in the e-learning and skills platforms market continues "
        "to grow as employers fund digital reskilling programs broadly.",
    ]
    first = best_placement_semantic(paras, "South Africa E-Learning Market")
    assert first is not None
    used = {first["sentence"].strip().lower()}
    second = best_placement_semantic(
        paras, "South Africa E-Learning and Skills Platforms Market",
        exclude_sentences=used)
    assert second is not None
    assert second["sentence"] != first["sentence"]


def test_semantic_exclusion_returns_none_when_only_one_sentence_exists():
    paras = ["The future of the market appears promising for e-learning "
            "platforms across the region this year."]
    first = best_placement_semantic(paras, "E-Learning Market")
    used = {first["sentence"].strip().lower()}
    second = best_placement_semantic(paras, "E-Learning Market",
                                     exclude_sentences=used)
    assert second is None  # nothing distinct left - caller falls through


def test_keyword_exclusion_forces_a_distinct_sentence():
    paras = [
        "The car rental market benefits from rising tourism and business "
        "travel across major metropolitan hubs this year.",
        "Fleet electrification in the car rental market accelerates as "
        "operators respond to corporate sustainability mandates broadly.",
    ]
    kw = {"car", "rental"}
    first = best_placement(paras, kw)
    used = {first["sentence"].strip().lower()}
    second = best_placement(paras, kw, exclude_sentences=used)
    assert second is not None
    assert second["sentence"] != first["sentence"]


def test_used_sentences_seeded_from_all_confirmed_not_just_approved():
    # regression: seeding the collision-guard only from approved/deployed
    # rows missed a partial-reopen scenario - two PENDING rows on the same
    # source page, one left 'confirmed' from an earlier run and one
    # reopened for re-placement, ended up sharing the exact same sentence
    # because the reopened row never learned the confirmed sibling's spot
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "place_contextual_links",
        Path(__file__).resolve().parent.parent / "scripts" /
        "22_place_contextual_links.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = inspect_source = mod.__file__
    import re as _re
    text = Path(src).read_text(encoding="utf-8")
    # the seed query must key off placement_status='confirmed', not status
    seed_block = text[text.index("used_sentences: dict"):text.index("used_sentences: dict") + 700]
    assert "status != 'rejected'" in seed_block
    assert "placement_status = 'confirmed'" in seed_block
    assert "status IN ('approved', 'deployed')" not in seed_block


def test_template_section_descriptor_blurbs_are_boilerplate():
    # regression: Ken's report template renders a section-descriptor blurb
    # under several headings - the IDENTICAL sentence on 13+ pages with only
    # the market name swapped in. It mentions the market so it scores well,
    # but template text is not "about" any one market, so a link there is
    # not genuinely contextual. Found via manual review of LLM rewrites.
    assert is_boilerplate(
        "Comprehensive analysis of key factors shaping the Indonesia Online "
        "Grocery Market, including growth drivers, market challenges, and "
        "emerging opportunities across consumer segments.")
    assert is_boilerplate(
        "This section evaluates the historical market size, analyzes "
        "year-over-year growth dynamics, and presents the forecast outlook.")


def test_blurb_filter_does_not_reject_genuine_analysis_prose():
    # sentences that genuinely analyse a market must survive, even when they
    # use words like "analysis", "growth drivers", or "competitive landscape"
    assert not is_boilerplate(
        "Growth drivers in the Indonesia online grocery market are shifting "
        "from discount-led acquisition toward basket economics and retention.")
    assert not is_boilerplate(
        "Our analysis of the competitive landscape shows the top three "
        "players hold a combined 46% share of national GMV.")
    assert not is_boilerplate(
        "The market size reached USD 1.2 billion in 2025, with year-over-year "
        "growth moderating to 14% as pandemic demand normalised.")
