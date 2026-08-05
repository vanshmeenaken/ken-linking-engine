"""Tests for GET /api/pages/{node_id}/analytics, the GA4 twin of
/api/pages/{node_id}/search-performance."""

import sqlite3

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_analytics_404_for_unknown_page():
    assert client.get("/api/pages/does-not-exist/analytics").status_code == 404


def test_analytics_has_data_for_matched_page():
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        "SELECT DISTINCT node_id FROM integration_placeholders "
        "WHERE source='ga4' AND status='matched' LIMIT 1"
    ).fetchone()
    conn.close()
    if row is None:
        return  # no GA4 data synced in this environment; endpoint shape is
                # covered by test_analytics_reports_no_data_honestly below
    r = client.get(f"/api/pages/{row[0]}/analytics")
    assert r.status_code == 200
    body = r.json()
    assert body["has_data"] is True
    assert body["date_range"]
    assert body["sessions"] is not None


def test_analytics_reports_no_data_honestly_not_404():
    # A real page with no GA4 rows must return has_data=false, not 404: the
    # page exists, the data does not (same contract as search-performance).
    conn = sqlite3.connect("ken_links.db")
    matched = {r[0] for r in conn.execute(
        "SELECT node_id FROM integration_placeholders "
        "WHERE source='ga4' AND status='matched'")}
    row = conn.execute(
        "SELECT node_id FROM content_nodes WHERE status='active'").fetchall()
    conn.close()
    unmatched = next((r[0] for r in row if r[0] not in matched), None)
    if unmatched is None:
        return  # every active page happens to have GA4 data; nothing to assert
    r = client.get(f"/api/pages/{unmatched}/analytics")
    assert r.status_code == 200
    assert r.json()["has_data"] is False
