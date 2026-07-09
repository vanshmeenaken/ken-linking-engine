"""Tests for the Phase 2 Day 5 entity API endpoints (api/main.py)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _live_db():
    return sqlite3.connect("ken_links.db")


def test_list_entities_basic():
    r = client.get("/api/entities?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert len(body["entities"]) <= 5


def test_list_entities_filters_by_type():
    r = client.get("/api/entities?entity_type=market&limit=200")
    assert r.status_code == 200
    body = r.json()
    assert all(e["entity_type"] == "market" for e in body["entities"])


def test_list_entities_excludes_orphaned_zero_page_entities():
    # Regression: an entity whose only mappings are all rejected must not
    # appear in browse/taxonomy listings (page_count would show 0, which is
    # noise — the entity_id detail lookup still works for audit purposes)
    r = client.get("/api/entities?limit=500")
    assert r.status_code == 200
    assert all(e["page_count"] > 0 for e in r.json()["entities"])


def test_list_entities_search():
    r = client.get("/api/entities?search=Bahrain")
    assert r.status_code == 200
    body = r.json()
    if body["total"]:
        assert any("bahrain" in e["entity_name"].lower()
                   or "bahrain" in e["normalized_name"].lower()
                   for e in body["entities"])


def test_low_confidence_route_does_not_collide_with_entity_id_route():
    # /api/entities/low-confidence must resolve as the literal route, not be
    # swallowed by /api/entities/{entity_id}
    r = client.get("/api/entities/low-confidence?threshold=0.7")
    assert r.status_code == 200
    body = r.json()
    assert "mappings" in body
    assert all(m["confidence_score"] < 0.7 for m in body["mappings"])
    assert all(m["status"] == "extracted" for m in body["mappings"])


def test_entity_detail_found_and_not_found():
    conn = _live_db()
    entity_id = conn.execute(
        "SELECT entity_id FROM content_entities LIMIT 1"
    ).fetchone()[0]
    conn.close()

    r = client.get(f"/api/entities/{entity_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["entity_id"] == entity_id
    assert "pages" in body
    assert body["page_count"] == len(body["pages"])

    r = client.get("/api/entities/does-not-exist-at-all")
    assert r.status_code == 404


def test_page_entities_found_and_not_found():
    conn = _live_db()
    node_id = conn.execute("SELECT node_id FROM content_nodes LIMIT 1").fetchone()[0]
    conn.close()

    r = client.get(f"/api/pages/{node_id}/entities")
    assert r.status_code == 200
    body = r.json()
    assert body["node_id"] == node_id
    assert body["entity_count"] == len(body["entities"])

    r = client.get("/api/pages/does-not-exist/entities")
    assert r.status_code == 404


def test_taxonomy_markets_and_regions():
    r = client.get("/api/taxonomy/markets")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(body["markets"])
    assert all(m["page_count"] > 0 for m in body["markets"])

    r = client.get("/api/taxonomy/regions")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(body["regions"])
    region_names = {r["name"] for r in body["regions"]}
    assert "Middle East" in region_names or "Asia Pacific" in region_names


def test_entity_coverage_matches_live_db():
    # Regression: this endpoint previously crashed with
    # "Cannot operate on a closed database" (conn.close() ran before the
    # covered() helper, which needs conn, was called)
    r = client.get("/api/intelligence/entity-coverage")
    assert r.status_code == 200
    body = r.json()

    conn = _live_db()
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status='active'"
    ).fetchone()[0]
    conn.close()

    assert body["active_pages"] == active
    for key in ("pages_with_any_entity", "pages_with_geography",
                "pages_with_industry_or_market", "pages_with_market"):
        assert key in body["coverage"]
        assert 0 <= body["coverage"][key]["pct"] <= 100
    assert body["coverage"]["pages_with_any_entity"]["pct"] >= 95.0
    assert body["coverage"]["pages_with_geography"]["pct"] >= 90.0
    assert "extracted" in body["mapping_statuses"]


def test_validate_internal_link_endpoint():
    conn = _live_db()
    good = conn.execute(
        "SELECT node_id FROM content_nodes WHERE status='active' "
        "AND indexability_status='indexable' LIMIT 2"
    ).fetchall()
    conn.close()
    assert len(good) == 2
    r = client.post("/api/internal-linking/validate", json={
        "source_node_id": good[0][0],
        "target_node_id": good[1][0],
        "anchor_text": "Some Market Report",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["overall_status"] in ("approved_for_review", "needs_revision", "rejected")
    assert body["approval_required"] is True
