"""Tests for Agent 6 Link Recommendation Engine (Phase 3) and its API."""

import sqlite3

from fastapi.testclient import TestClient

from agents.agent_6_link_recommendation import LinkRecommendationAgent, band
from api.main import app

client = TestClient(app)


# ── score bands (master PRD 17.2) ────────────────────────────────────────────

def test_score_bands():
    assert band(95) == "priority"
    assert band(85) == "strong"
    assert band(70) == "secondary"
    assert band(55) == "hold"
    assert band(40) == "drop"


# ── anchor text quality ──────────────────────────────────────────────────────

class _Row(dict):
    def __getitem__(self, k):
        return self.get(k)


def test_anchor_no_double_market():
    # market field already ends in "Market" -> must not append another
    a, q = LinkRecommendationAgent._build_anchor(
        _Row(market="Cold Storage Market", country="uae", title=""))
    assert a == "UAE Cold Storage Market"
    assert "Market Market" not in a
    assert q == 1.0


def test_anchor_uppercases_geo_acronyms():
    a, _ = LinkRecommendationAgent._build_anchor(
        _Row(market="Online Grocery", country="uae", title=""))
    assert a.startswith("UAE ")  # not "Uae"


def test_anchor_appends_market_when_missing():
    a, _ = LinkRecommendationAgent._build_anchor(
        _Row(market="Online Grocery", country="india", title=""))
    assert a == "India Online Grocery Market"


def test_anchor_never_generic():
    # even the title fallback must not be a banned generic phrase
    a, q = LinkRecommendationAgent._build_anchor(
        _Row(market="", country="", title="Some Report | Ken Research"))
    assert a.lower() not in {"click here", "read more", "this report", "learn more"}


# ── the real generated set ───────────────────────────────────────────────────

def test_recommendations_exist_and_are_scored():
    conn = sqlite3.connect("ken_links.db")
    n = conn.execute("SELECT COUNT(*) FROM link_recommendations").fetchone()[0]
    # every recommendation must be a genuine page-to-page link, scored >= 50
    bad = conn.execute(
        "SELECT COUNT(*) FROM link_recommendations "
        "WHERE source_node_id = target_node_id OR link_score < 50").fetchone()[0]
    conn.close()
    assert n > 0
    assert bad == 0, "a recommendation is a self-link or below the 50 floor"


def test_no_double_market_in_stored_anchors():
    conn = sqlite3.connect("ken_links.db")
    bad = conn.execute(
        "SELECT COUNT(*) FROM link_recommendations "
        "WHERE anchor_text LIKE '%Market Market%'").fetchone()[0]
    conn.close()
    assert bad == 0


def test_adjacent_report_recommendations_are_included():
    # Adjacent/related report links belong in Related Reports blocks even when
    # they do not share the exact same market or geography.
    conn = sqlite3.connect("ken_links.db")
    count = conn.execute(
        """SELECT COUNT(*)
           FROM link_recommendations lr
           JOIN content_nodes s ON s.node_id = lr.source_node_id
           JOIN content_nodes t ON t.node_id = lr.target_node_id
           WHERE lr.relationship_type = 'adjacent_market'
             AND s.content_type = 'report'
             AND t.content_type = 'report'
             AND lr.placement_type = 'related_reports_block'"""
    ).fetchone()[0]
    conn.close()
    assert count >= 10


def test_adjacent_recommendations_pass_market_technology_gate():
    conn = sqlite3.connect("ken_links.db")
    bad = conn.execute(
        """SELECT COUNT(*) FROM link_recommendations
           WHERE relationship_type='adjacent_market'
             AND (market_match_score < 0.30 OR technology_match_score < 0.50)"""
    ).fetchone()[0]
    classes = {
        row[0] for row in conn.execute(
            "SELECT DISTINCT relationship_class FROM link_recommendations"
        )
    }
    conn.close()
    assert bad == 0
    assert classes <= {"regional", "adjacent", "adjacent_regional"}

def test_no_duplicate_source_target_pairs():
    # Regression: two pages can share more than one relationship type; the same
    # source->target link must still be recommended only once (highest score).
    conn = sqlite3.connect("ken_links.db")
    dup = conn.execute(
        "SELECT COUNT(*) FROM (SELECT source_node_id, target_node_id, COUNT(*) k "
        "FROM link_recommendations GROUP BY source_node_id, target_node_id "
        "HAVING k > 1)").fetchone()[0]
    conn.close()
    assert dup == 0, "the same source->target link is recommended more than once"


# ── API ──────────────────────────────────────────────────────────────────────

def test_review_queue_returns_pending_scored():
    r = client.get("/api/recommendations/review-queue?limit=10")
    assert r.status_code == 200
    for rec in r.json()["recommendations"]:
        assert rec["score_band"] != "drop"
        assert rec["link_score"] >= 50


def test_recommendations_stats():
    r = client.get("/api/recommendations/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 0
    assert "by_band" in body and "by_validation" in body


def test_list_recommendations_filter_by_band():
    r = client.get("/api/recommendations?band=secondary&limit=200")
    assert r.status_code == 200
    assert all(rec["score_band"] == "secondary"
               for rec in r.json()["recommendations"])


def test_page_recommendations_shape_and_404():
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        "SELECT source_node_id FROM link_recommendations LIMIT 1").fetchone()
    conn.close()
    if row:
        r = client.get(f"/api/pages/{row[0]}/recommendations")
        assert r.status_code == 200
        assert "links_to_add" in r.json()
    assert client.get("/api/pages/not-real/recommendations").status_code == 404
