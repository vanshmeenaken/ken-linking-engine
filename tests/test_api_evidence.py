"""Tests for the Agent 8 evidence API endpoints (paragraph_evidence_map)."""

import sqlite3

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _a_mapped_node_id():
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        "SELECT node_id FROM paragraph_evidence_map LIMIT 1").fetchone()
    conn.close()
    return row[0]


def test_evidence_stats_shape_and_consistency():
    r = client.get("/api/evidence/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["pages_mapped"] > 0
    assert body["paragraphs_mapped"] >= body["pages_mapped"]
    assert body["market_claims"] == sum(body["claims_by_support"].values())
    for row in body["top_pages_with_unsupported_claims"]:
        assert row["url"] and row["unsupported_claims"] > 0


def test_page_evidence_for_a_mapped_page():
    node_id = _a_mapped_node_id()
    r = client.get(f"/api/pages/{node_id}/evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["mapped"] is True
    assert body["paragraph_count"] == len(body["paragraphs"])
    for p in body["paragraphs"]:
        assert p["classification"] in ("market_claim", "context")
        if p["classification"] == "market_claim":
            assert p["support_status"] in (
                "supported", "section_supported", "unsupported")
        else:
            assert p["support_status"] is None


def test_page_evidence_unknown_page_404s():
    r = client.get("/api/pages/does-not-exist/evidence")
    assert r.status_code == 404


def test_page_evidence_unmapped_page_is_honest():
    # an active page that Agent 8 has not crawled must say mapped=false,
    # not pretend it has zero claims
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        """SELECT node_id FROM content_nodes WHERE status='active'
           AND node_id NOT IN (SELECT DISTINCT node_id
                               FROM paragraph_evidence_map)
           LIMIT 1""").fetchone()
    conn.close()
    if row is None:
        return  # every page mapped - nothing to assert
    r = client.get(f"/api/pages/{row[0]}/evidence")
    assert r.status_code == 200
    assert r.json()["mapped"] is False
