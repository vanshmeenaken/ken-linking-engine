"""Tests for the Phase 2 Day 9 relationship, opportunity and intelligence
API endpoints (api/main.py), plus regression guards for the industry_market
self-loop fix (scripts/18_fix_industry_market_edges.py)."""

import sqlite3

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _live_db():
    conn = sqlite3.connect("ken_links.db")
    conn.row_factory = sqlite3.Row
    return conn


# ── relationships ────────────────────────────────────────────────────────────

def test_relationship_types_summary():
    r = client.get("/api/relationships/types")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(body["types"])
    for t in body["types"]:
        assert 0.0 <= t["avg_confidence"] <= 1.0
        assert t["edge_count"] > 0


def test_list_relationships_basic_and_shape():
    r = client.get("/api/relationships?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert len(body["relationships"]) <= 5
    for e in body["relationships"]:
        # every listed edge must carry both page ends with context
        assert e["source_url"] and e["target_url"]
        assert e["source_node_id"] != e["target_node_id"]  # no self-loops surface


def test_list_relationships_filter_by_type():
    r = client.get("/api/relationships?relationship_type=same_market&limit=200")
    assert r.status_code == 200
    assert all(e["relationship_type"] == "same_market"
               for e in r.json()["relationships"])


def test_list_relationships_min_confidence():
    r = client.get("/api/relationships?min_confidence=0.7&limit=200")
    assert r.status_code == 200
    assert all(e["confidence_score"] >= 0.7 for e in r.json()["relationships"])


def test_relationships_pending_route_not_swallowed_by_type_route():
    # /api/relationships/pending and /types are literal routes, not filter values
    r = client.get("/api/relationships/pending?limit=5")
    assert r.status_code == 200
    assert all(e["confidence_score"] is not None for e in r.json()["pending"])


def test_page_relationships_valid_and_bidirectional():
    conn = _live_db()
    node = conn.execute(
        "SELECT source_node_id FROM relationship_edges "
        "WHERE source_node_id != target_node_id LIMIT 1"
    ).fetchone()[0]
    conn.close()
    r = client.get(f"/api/pages/{node}/relationships")
    assert r.status_code == 200
    body = r.json()
    assert body["relationship_count"] == len(body["relationships"])
    for e in body["relationships"]:
        assert e["this_page_role"] in ("source", "target")
        assert e["other_node_id"] != node  # never related to itself


def test_page_relationships_404():
    assert client.get("/api/pages/does-not-exist-xyz/relationships").status_code == 404


def test_entity_relationships_valid_and_404():
    conn = _live_db()
    row = conn.execute(
        "SELECT source_entity_id FROM relationship_edges "
        "WHERE source_entity_id IS NOT NULL LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        r = client.get(f"/api/entities/{row[0]}/relationships")
        assert r.status_code == 200
        assert "relationship_count" in r.json()
    assert client.get("/api/entities/nope-xyz/relationships").status_code == 404


# ── opportunities ────────────────────────────────────────────────────────────

def test_list_opportunities_basic():
    r = client.get("/api/opportunities?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert len(body["opportunities"]) <= 5


def test_opportunities_filter_by_type():
    r = client.get("/api/opportunities?opportunity_type=orphan_page&limit=500")
    assert r.status_code == 200
    assert all(o["opportunity_type"] == "orphan_page"
               for o in r.json()["opportunities"])


def test_opportunities_orphans_shortcut():
    r = client.get("/api/opportunities/orphans?limit=10")
    assert r.status_code == 200
    assert all(o["opportunity_type"] == "orphan_page"
               for o in r.json()["opportunities"])


def test_opportunities_high_priority_only_high_business():
    r = client.get("/api/opportunities/high-priority?limit=200")
    assert r.status_code == 200
    body = r.json()
    assert all(o["business_priority"] == "High" for o in body["opportunities"])
    assert all(o["status"] == "open" for o in body["opportunities"])


# ── intelligence summaries ───────────────────────────────────────────────────

def test_intelligence_stats_matches_db():
    r = client.get("/api/intelligence/stats")
    assert r.status_code == 200
    body = r.json()
    conn = _live_db()
    assert body["relationship_edges"] == conn.execute(
        "SELECT COUNT(*) FROM relationship_edges").fetchone()[0]
    assert body["active_pages"] == conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status='active'").fetchone()[0]
    conn.close()
    assert set(body["business_priority_bands"]).issubset({"High", "Medium", "Low"})


def test_relationship_coverage_shape_and_target():
    r = client.get("/api/intelligence/relationship-coverage")
    assert r.status_code == 200
    body = r.json()
    p = body["page_to_page_connectivity"]
    assert 0.0 <= p["pct"] <= 100.0
    assert p["target_pct"] == 70.0
    assert body["total_edges"] == sum(body["edges_by_type"].values())


def test_business_priority_breakdown():
    r = client.get("/api/intelligence/business-priority?top=5")
    assert r.status_code == 200
    body = r.json()
    assert set(body["bands"]).issubset({"High", "Medium", "Low"})
    assert all(p["business_priority"] == "High"
               for p in body["top_high_priority_pages"])


def test_global_local_segmentation():
    r = client.get("/api/intelligence/global-local")
    assert r.status_code == 200
    assert "segmentation" in r.json()


# ── Google integration endpoints (must work BEFORE credentials exist) ───────

def test_integrations_status_reports_honestly_without_credentials():
    # Before access is granted these must report "no data" cleanly — never
    # 500, and never imply Ken has no search traffic.
    r = client.get("/api/integrations/status")
    assert r.status_code == 200
    body = r.json()
    for source in ("gsc", "ga4"):
        assert "has_data" in body[source]
        assert isinstance(body[source]["metric_rows"], int)
    assert "credentials_configured" in body


def test_striking_distance_empty_without_gsc_data():
    r = client.get("/api/opportunities/striking-distance")
    assert r.status_code == 200
    body = r.json()
    assert body["position_range"] == [4.0, 20.0]
    if not body["has_data"]:
        assert body["count"] == 0
        assert body["note"]  # must explain WHY it is empty


def test_page_search_performance_404_for_unknown_page():
    r = client.get("/api/pages/not-a-real-page/search-performance")
    assert r.status_code == 404


def test_page_search_performance_reports_no_data_not_404_for_real_page():
    # A real page with no GSC data yet must return has_data=false, not 404:
    # the page exists, the data does not.
    conn = _live_db()
    node = conn.execute(
        "SELECT node_id FROM content_nodes WHERE status='active' LIMIT 1"
    ).fetchone()[0]
    conn.close()
    r = client.get(f"/api/pages/{node}/search-performance")
    assert r.status_code == 200
    assert "has_data" in r.json()


# ── regression guards for the self-loop fix ─────────────────────────────────

def test_no_self_loop_edges_remain():
    # The industry_market self-loop fix must hold: relationship_edges may only
    # contain genuine page-to-page edges. A self-loop here means page-scoped
    # entity facts have leaked back into the links table.
    conn = _live_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM relationship_edges "
        "WHERE source_node_id = target_node_id"
    ).fetchone()[0]
    conn.close()
    assert n == 0, f"{n} self-loop edges present — the industry_market fix regressed"


def test_no_industry_market_edge_type():
    # industry_market is no longer an edge type; it lives in
    # content_entities.parent_entity_id
    conn = _live_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM relationship_edges "
        "WHERE relationship_type = 'industry_market'"
    ).fetchone()[0]
    conn.close()
    assert n == 0


def test_coverage_canary_is_zero():
    body = client.get("/api/intelligence/relationship-coverage").json()
    assert body["self_loop_edges"] == 0


def test_connectivity_and_missing_relationships_reconcile():
    # connected pages + missing_relationships opportunities must equal active
    # pages: every active page either has a page-to-page edge or is flagged as
    # missing one. This is the cross-agent consistency the self-loop fix restored.
    conn = _live_db()
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status='active'").fetchone()[0]
    connected = conn.execute(
        """SELECT COUNT(DISTINCT n.node_id) FROM content_nodes n
           JOIN relationship_edges e
             ON (e.source_node_id=n.node_id OR e.target_node_id=n.node_id)
           WHERE n.status='active' AND e.source_node_id != e.target_node_id"""
    ).fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM seo_opportunities "
        "WHERE opportunity_type='missing_relationships'"
    ).fetchone()[0]
    conn.close()
    assert connected + missing == active
