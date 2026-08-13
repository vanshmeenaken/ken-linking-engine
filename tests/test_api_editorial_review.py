"""Tests for GET /api/recommendations/{id}/review (Phase 3): the API surface
for Agent 11's editorial review notes, so a human can see why/where/anchor/
risk for a recommendation and then approve or reject it via the existing
PATCH /api/recommendations/{id} endpoint."""

import sqlite3

from fastapi.testclient import TestClient

from analysis.report_link_planner import refresh_report_link_plans
from api.main import app

client = TestClient(app)


def _a_recommendation_id():
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        "SELECT recommendation_id FROM link_recommendations LIMIT 1").fetchone()
    conn.close()
    return row[0]


def test_review_note_has_all_fields_for_a_real_recommendation():
    rec_id = _a_recommendation_id()
    r = client.get(f"/api/recommendations/{rec_id}/review")
    assert r.status_code == 200
    body = r.json()
    assert body["recommendation_id"] == rec_id
    assert body["status"] in {"pending", "approved", "rejected"}
    for field in ("headline", "why", "where", "anchor", "relationship",
                  "seo_value", "business_value", "risk", "plain_summary"):
        assert body[field], f"missing or empty field: {field}"


def test_review_note_unknown_id_404s():
    r = client.get("/api/recommendations/does-not-exist/review")
    assert r.status_code == 404


def test_review_note_reflects_decision_status():
    # approve/reject on this endpoint's twin PATCH must be visible back here,
    # since the dashboard re-fetches the note after deciding to disable the
    # approve/reject buttons. Restores the original row afterward so this test
    # does not permanently mutate the review queue.
    rec_id = _a_recommendation_id()
    conn = sqlite3.connect("ken_links.db")
    original = conn.execute(
        "SELECT status, approved_by, risk_reason, updated_at "
        "FROM link_recommendations WHERE recommendation_id = ?",
        (rec_id,)).fetchone()
    conn.close()
    try:
        patch = client.patch(f"/api/recommendations/{rec_id}",
                             json={"decision": "reject", "reviewed_by": "test-suite"})
        assert patch.status_code == 200
        r = client.get(f"/api/recommendations/{rec_id}/review")
        assert r.json()["status"] == "rejected"
    finally:
        conn = sqlite3.connect("ken_links.db")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "UPDATE link_recommendations SET status=?, approved_by=?, "
            "risk_reason=?, updated_at=? WHERE recommendation_id = ?",
            (original[0], original[1], original[2], original[3], rec_id))
        refresh_report_link_plans(conn, original[3] or 'test-restore')
        conn.commit()
        conn.close()


def test_page_recommendations_report_link_spread():
    # the spread block tells an editor whether a page's outgoing links are
    # distributed across its real sections or bunched in one place; it only
    # exists for pages Agent 9 has sectioned
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        """SELECT DISTINCT lr.source_node_id FROM link_recommendations lr
           JOIN section_purpose_map s ON s.node_id = lr.source_node_id
           WHERE s.linkable = 1 LIMIT 1""").fetchone()
    conn.close()
    assert row is not None, "run agents/agent_9_section_purpose.py first"
    r = client.get(f"/api/pages/{row[0]}/recommendations")
    assert r.status_code == 200
    spread = r.json()["link_spread"]
    assert spread is not None
    assert spread["linkable_sections"]
    assert "of" in spread["spread_note"]
