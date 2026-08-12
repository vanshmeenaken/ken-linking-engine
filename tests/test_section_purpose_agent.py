"""Tests for the section-aware crawler (analysis/contextual_placement.py
fetch_sections) and Agent 9 Section Purpose (master PRD 13.9), plus the
placement guard in scripts/22 that keeps contextual links out of structural
sections (author bios, FAQs, CTAs...)."""

import importlib.util
import sqlite3
from pathlib import Path

import analysis.contextual_placement as cp
from agents.agent_9_section_purpose import (PURPOSE_RULES, build_section_records,
                                            classify_heading)

SCRIPT_22 = Path(__file__).resolve().parent.parent / "scripts" / "22_place_contextual_links.py"
spec = importlib.util.spec_from_file_location("place_contextual_links", SCRIPT_22)
place_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(place_mod)


# ── the section-aware crawler ────────────────────────────────────────────────

class _FakeResp:
    status_code = 200
    apparent_encoding = "utf-8"
    text = (
        "<html><body>"
        "<p>Intro paragraph before any heading, long enough to be kept as "
        "meaningful body text for the page.</p>"
        "<h2>CHAPTER 1 - MARKET SUMMARY</h2>"
        "<h2>Market Overview</h2>"
        "<p>The market grew strongly across the review period, driven by "
        "urbanization and rising disposable incomes in tier-2 cities.</p>"
        "<p><a href='/other-market-report'>Other Market Report</a> is linked "
        "here inside a real paragraph of genuine prose content on purpose.</p>"
        "<h2>Explore Related Reports</h2>"
        "<ul><li><a href='https://www.kenresearch.com/a'>A</a></li>"
        "<li><a href='https://www.kenresearch.com/b'>B</a></li>"
        "<li><a href='mailto:x@y.com'>mail</a></li>"
        "<li><a href='#top'>top</a></li></ul>"
        "</body></html>"
    )
    def raise_for_status(self): pass


def test_fetch_sections_structure(monkeypatch):
    monkeypatch.setattr(cp.requests, "get", lambda *a, **k: _FakeResp())
    secs = cp.fetch_sections("https://example.test/page")
    headings = [s["heading"] for s in secs]
    assert headings == [None, "CHAPTER 1 - MARKET SUMMARY", "Market Overview",
                        "Explore Related Reports"]
    intro, banner, overview, related = secs
    assert len(intro["paragraphs"]) == 1          # pre-heading intro kept
    assert banner["paragraphs"] == []             # banner kept, empty
    assert len(overview["paragraphs"]) == 2


def test_fetch_sections_counts_links_in_lists_not_just_paragraphs(monkeypatch):
    # regression: several report templates render related-report links as
    # <li>, which a <p>-only walk missed entirely; mailto/# never count
    monkeypatch.setattr(cp.requests, "get", lambda *a, **k: _FakeResp())
    secs = cp.fetch_sections("https://example.test/page")
    related = secs[-1]
    assert related["internal_link_count"] == 2
    overview = secs[2]
    assert overview["internal_link_count"] == 1   # the in-paragraph link


def test_fetch_paragraphs_still_flat_and_filtered(monkeypatch):
    monkeypatch.setattr(cp.requests, "get", lambda *a, **k: _FakeResp())
    paras = cp.fetch_paragraphs("https://example.test/page")
    assert len(paras) == 3  # intro + two overview paragraphs


# ── heading classification (verified against real page headings) ─────────────

def test_classify_real_report_headings():
    assert classify_heading("CHAPTER 4 - Market Size & Growth") == "chapter_banner"
    assert classify_heading("Market Overview") == "overview"
    assert classify_heading("Market Size, Growth Forecast and Trends") == "market_size"
    assert classify_heading("Growth Drivers, Market Challenges & Market Opportunities") \
        == "industry_analysis"
    assert classify_heading("Regional Analysis") == "regional"
    assert classify_heading("Market Segmentation Framework") == "segmentation"
    assert classify_heading("Competitive Landscape Overview") == "competitive"
    assert classify_heading("Research Methodology") == "methodology"
    assert classify_heading("Explore Related Reports") == "related_reports"
    assert classify_heading("Other Regional/Country Reports") == "related_reports"
    assert classify_heading("Other Adjacent Reports") == "related_reports"
    assert classify_heading("Market Report Structure") == "toc"
    assert classify_heading(None) == "intro"


def test_classify_case_study_and_article_headings():
    assert classify_heading("Client Background") == "case_study"
    assert classify_heading("Why: The Business Problem") == "case_study"
    assert classify_heading("Results and Impact") == "case_study"
    # bare question words match exactly, never as substrings
    assert classify_heading("Why?") == "case_study"
    assert classify_heading("How") == "case_study"
    assert classify_heading("Conclusion") == "overview"
    assert classify_heading("Related tags") == "navigation"


def test_classify_traps_found_via_manual_review():
    # author bio vector-matched a cement target before the guard existed
    assert classify_heading("About the Author - Rajat Goyal:") == "author"
    # sales pitch containing the word "challenge" must be CTA, not analysis
    assert classify_heading("Let's Talk Strategy - Turn Challenge into Opportunity") == "cta"
    # one template opens with a full-sentence headline: prose, hence overview
    assert classify_heading(
        "Global Application Container Market, valued at USD 5.8 billion, "
        "thrives on cloud adoption and microservices momentum") == "overview"
    assert classify_heading("Players Mentioned in the Report:") == "competitive"


def test_every_emittable_purpose_has_a_rule():
    from agents.agent_9_section_purpose import _PURPOSE_KEYWORDS
    purposes = {p for p, _ in _PURPOSE_KEYWORDS}
    purposes |= {"intro", "chapter_banner", "overview", "case_study", "other"}
    missing = purposes - set(PURPOSE_RULES)
    assert not missing, f"purposes without rules: {missing}"


# ── section records and honesty flags ────────────────────────────────────────

def _sec(heading, n_paras=1, links=0, order=0):
    return {"heading": heading, "order": order,
            "paragraphs": ["x" * 70] * n_paras, "internal_link_count": links}


def test_flags_purposeless_and_missing_links():
    records = build_section_records("n1", "https://x/p", [
        _sec("Mystery Heading Nobody Understands", n_paras=0),   # purposeless
        _sec("Market Overview", n_paras=3, links=0, order=1),    # missing links
        _sec("Market Overview", n_paras=3, links=2, order=2),    # fine
        _sec("CHAPTER 2 - SCOPE", n_paras=0, order=3),           # banner: no flag
    ])
    assert records[0].flag_purposeless is True
    assert records[1].flag_missing_links is True
    assert records[2].flag_missing_links is False
    assert records[3].flag_purposeless is False


# ── the placement guard in scripts/22 ────────────────────────────────────────

def test_structural_purposes_are_excluded_from_contextual_placement():
    for purpose in ("faq", "author", "cta", "toc", "methodology",
                    "chapter_banner", "navigation"):
        assert purpose in place_mod.EXCLUDED_PLACEMENT_PURPOSES
    # content purposes must stay allowed
    for purpose in ("intro", "overview", "market_size", "regional",
                    "case_study", "other"):
        assert purpose not in place_mod.EXCLUDED_PLACEMENT_PURPOSES


def test_best_section_for_prefers_relationship_fit():
    sections = [
        {"heading": "Market Overview", "purpose": "overview", "n_paras": 3},
        {"heading": "Regional Analysis", "purpose": "regional", "n_paras": 2},
        {"heading": "FAQs", "purpose": "faq", "n_paras": 4},
    ]
    # a same-market link belongs in the regional section first
    assert place_mod.best_section_for(sections, "same_market") == "Regional Analysis"
    # an adjacent-market link prefers analysis/overview
    assert place_mod.best_section_for(sections, "adjacent_market") == "Market Overview"


def test_best_section_for_never_recommends_empty_sections():
    sections = [{"heading": "Regional Analysis", "purpose": "regional", "n_paras": 0}]
    assert place_mod.best_section_for(sections, "same_market") is None


# ── live data sanity ─────────────────────────────────────────────────────────

def test_section_purpose_map_populated_and_consistent():
    conn = sqlite3.connect("ken_links.db")
    total = conn.execute("SELECT COUNT(*) FROM section_purpose_map").fetchone()[0]
    assert total > 0, "run agents/agent_9_section_purpose.py to populate it"
    unknown = conn.execute(
        "SELECT DISTINCT purpose FROM section_purpose_map").fetchall()
    for (purpose,) in unknown:
        assert purpose in PURPOSE_RULES, f"stored purpose '{purpose}' has no rule"
    orphaned = conn.execute(
        """SELECT COUNT(*) FROM section_purpose_map s
           WHERE NOT EXISTS (SELECT 1 FROM content_nodes n
                             WHERE n.node_id = s.node_id)""").fetchone()[0]
    conn.close()
    assert orphaned == 0


def test_no_placement_left_unresolved():
    # after the retry run, every recommendation has a confirmed placement
    conn = sqlite3.connect("ken_links.db")
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM link_recommendations "
        "WHERE placement_status = 'unresolved'").fetchone()[0]
    conn.close()
    assert unresolved == 0
