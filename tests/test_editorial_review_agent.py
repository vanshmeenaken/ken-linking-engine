"""Tests for Agent 11 Editorial Review (master PRD 13.11, Phase 3): the
human-readable review note generator. This agent never approves or rejects
anything - it only explains a recommendation for a human to decide."""

import sqlite3

from agents.agent_11_editorial_review import build_review_note, clean_title


def _rec(**overrides):
    base = {
        "recommendation_id": "r1", "relationship_type": "same_market",
        "anchor_text": "India Online Grocery Market",
        "placement_type": "contextual_body", "placement_section": "Market Overview",
        "suggested_sentence": "Indonesia grocery demand is rising fast.",
        "link_score": 75.0, "score_band": "secondary",
        "seo_score": 80.0, "business_score": 90.0, "ai_readiness_score": 60.0,
        "risk_flag": "low", "risk_reason": None,
    }
    base.update(overrides)
    return base


# ── title cleanup (display-only) ─────────────────────────────────────────────

def test_clean_title_pipe_format():
    assert clean_title("Qatar Nordic Regulatory Affairs Market | 2019-2030 | Ken Research") \
        == "Qatar Nordic Regulatory Affairs Market"


def test_clean_title_colon_format_and_double_space():
    # regression: raw stored title has a genuine double space before the
    # branding suffix; the cleaned title must not carry it forward
    cleaned = clean_title("India Online Grocery Market,  E-groceries: Ken Research")
    assert "Ken Research" not in cleaned
    assert "  " not in cleaned  # no double space


def test_clean_title_handles_plain_title():
    assert clean_title("Plain Market Report") == "Plain Market Report"


# ── the review note itself ───────────────────────────────────────────────────

def test_review_note_has_all_prd_required_parts():
    # master PRD 13.11: why recommended, where to place, what anchor, what
    # relationship, SEO/business value, risk - every field must be present
    note = build_review_note(_rec(), "Source Page Title", "Target Page Title")
    assert note.why and note.where and note.anchor and note.relationship
    assert note.seo_value and note.business_value and note.risk
    assert note.anchor == "India Online Grocery Market"


def test_review_note_never_shows_toc_line_as_placement():
    # the note must reflect whatever is actually stored; this asserts the
    # sentence passed through unchanged (the TOC filtering itself is tested in
    # test_contextual_placement.py) so a reviewer sees real prose, not a label
    note = build_review_note(_rec(suggested_sentence="A genuine market sentence."),
                             "Source", "Target")
    assert "A genuine market sentence." in note.where


def test_related_reports_block_placement_explained_plainly():
    note = build_review_note(
        _rec(placement_type="related_reports_block", suggested_sentence=None),
        "Source", "Target")
    assert "Related Reports" in note.where
    assert "no single sentence" in note.where.lower()


def test_risk_reason_appended_when_present():
    note = build_review_note(
        _rec(risk_flag="medium", risk_reason="footer_placement: avoid footer for reports"),
        "Source", "Target")
    assert "Needs a second look" in note.risk
    assert "footer_placement" in note.plain_summary


def test_unknown_relationship_type_falls_back_gracefully():
    note = build_review_note(_rec(relationship_type="some_future_type"), "S", "T")
    assert "some_future_type" in note.relationship


# ── sanity against the real, current dataset ─────────────────────────────────

def test_builds_cleanly_against_every_real_recommendation():
    conn = sqlite3.connect("ken_links.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM link_recommendations").fetchall()
    for row in rows:
        s = conn.execute("SELECT title FROM content_nodes WHERE node_id=?",
                         (row["source_node_id"],)).fetchone()[0]
        t = conn.execute("SELECT title FROM content_nodes WHERE node_id=?",
                         (row["target_node_id"],)).fetchone()[0]
        note = build_review_note(dict(row), s, t)
        assert note.plain_summary  # never empty/crashes for real data
        assert "Ken Research" not in note.headline  # branding stripped
    conn.close()
