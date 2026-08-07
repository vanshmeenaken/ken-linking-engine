"""Tests for GET /api/recommendations/{id}/review (Phase 3): the API surface
for Agent 11's editorial review notes, so a human can see why/where/anchor/
risk for a recommendation and then approve or reject it via the existing
PATCH /api/recommendations/{id} endpoint."""

import sqlite3

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _a_pending_recommendation_id():
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        "SELECT recommendation_id FROM link_recommendations "
        "WHERE status = 'pending' LIMIT 1").fetchone()
    conn.close()
    return row[0]


def test_review_note_has_all_fields_for_a_real_recommendation():
    rec_id = _a_pending_recommendation_id()
    r = client.get(f"/api/recommendations/{rec_id}/review")
    assert r.status_code == 200
    body = r.json()
    assert body["recommendation_id"] == rec_id
    assert body["status"] == "pending"
    for field in ("headline", "why", "where", "anchor", "relationship",
                  "seo_value", "business_value", "risk", "plain_summary"):
        assert body[field], f"missing or empty field: {field}"


def test_review_note_unknown_id_404s():
    r = client.get("/api/recommendations/does-not-exist/review")
    assert r.status_code == 404


def test_review_note_reflects_decision_status():
    # approve/reject on this endpoint's twin PATCH must be visible back here,
    # since the dashboard re-fetches the note after deciding to disable the
    # approve/reject buttons. Restores the original status afterward so this
    # test does not permanently mutate the review queue.
    rec_id = _a_pending_recommendation_id()
    conn = sqlite3.connect("ken_links.db")
    original_updated_at = conn.execute(
        "SELECT updated_at FROM link_recommendations WHERE recommendation_id = ?",
        (rec_id,)).fetchone()[0]
    conn.close()
    try:
        patch = client.patch(f"/api/recommendations/{rec_id}",
                             json={"decision": "reject", "reviewed_by": "test-suite"})
        assert patch.status_code == 200
        r = client.get(f"/api/recommendations/{rec_id}/review")
        assert r.json()["status"] == "rejected"
    finally:
        conn = sqlite3.connect("ken_links.db")
        conn.execute(
            "UPDATE link_recommendations SET status='pending', approved_by=NULL, "
            "updated_at=? WHERE recommendation_id = ?", (original_updated_at, rec_id))
        conn.commit()
        conn.close()
