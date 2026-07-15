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
