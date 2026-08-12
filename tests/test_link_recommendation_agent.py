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


def test_list_recommendations_filter_by_relationship_class():
    r = client.get("/api/recommendations?relationship_class=regional&limit=200")
    assert r.status_code == 200
    recommendations = r.json()["recommendations"]
    assert recommendations
    assert all(rec["relationship_class"] == "regional"
               for rec in recommendations)
    assert all("suggested_sentence" in rec for rec in recommendations)


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


def test_bidirectional_edges_generate_reciprocal_recommendations():
    conn = sqlite3.connect('ken_links.db')
    reciprocal = conn.execute(
        '''SELECT COUNT(*) FROM link_recommendations a
           WHERE a.status != 'rejected' AND EXISTS (
               SELECT 1 FROM link_recommendations b
               WHERE b.source_node_id=a.target_node_id
                 AND b.target_node_id=a.source_node_id
                 AND b.status != 'rejected'
           )'''
    ).fetchone()[0]
    conn.close()
    assert reciprocal > 0


def test_report_plans_respect_prd_maximums():
    conn = sqlite3.connect('ken_links.db')
    reports = conn.execute(
        'SELECT COUNT(*) FROM report_link_plans'
    ).fetchone()[0]
    bad = conn.execute(
        '''SELECT COUNT(*) FROM report_link_plans
           WHERE projected_outgoing_links > 25
              OR total_opportunities > 30'''
    ).fetchone()[0]
    conn.close()
    assert reports > 0
    assert bad == 0


def test_report_link_plan_api_shape():
    stats = client.get('/api/report-link-plans/stats')
    assert stats.status_code == 200
    assert stats.json()['link_range'] == {'minimum': 10, 'maximum': 25}
    response = client.get('/api/report-link-plans?limit=5')
    assert response.status_code == 200
    assert response.json()['plans']
    plan = response.json()['plans'][0]
    for field in (
        'existing_outgoing_links', 'recommended_outgoing_links',
        'incoming_opportunities', 'projected_outgoing_links',
        'regional_report_opportunities', 'adjacent_report_opportunities',
        'plan_status', 'opportunity_status', 'gap_reason',
    ):
        assert field in plan
