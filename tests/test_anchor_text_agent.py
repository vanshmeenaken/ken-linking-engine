"""Tests for Agent 7 Anchor Text Agent (Phase 3), the shared anchor helper,
and the editorial decision + anchor-bank API."""

import sqlite3

from fastapi.testclient import TestClient

from agents.agent_7_anchor_text import AnchorTextAgent
from analysis.anchor_text import (build_primary_anchor, format_geo, is_generic,
                                  with_market_suffix)
from api.main import app

client = TestClient(app)


# ── shared anchor helper ─────────────────────────────────────────────────────

def test_format_geo_keeps_acronyms_upper():
    assert format_geo("uae") == "UAE"
    assert format_geo("saudi arabia") == "Saudi Arabia"
    assert format_geo("apac") == "APAC"


def test_with_market_suffix_no_double():
    assert with_market_suffix("Cold Storage Market") == "Cold Storage Market"
    assert with_market_suffix("Online Grocery") == "Online Grocery Market"
    assert with_market_suffix("") == ""


def test_build_primary_anchor_country_market():
    a, q = build_primary_anchor("Online Grocery", "india")
    assert a == "India Online Grocery Market"
    assert q == 1.0


def test_is_generic():
    assert is_generic("Click Here")
    assert is_generic("read more")
    assert not is_generic("India Online Grocery Market")


# ── Agent 7 bank construction ────────────────────────────────────────────────

class _Row(dict):
    def __getitem__(self, k):
        return self.get(k)


def test_bank_has_diverse_categories_no_generic():
    bank = AnchorTextAgent._bank_for(_Row(
        node_id="n1", url="https://x/india-online-grocery-market",
        market="Online Grocery", country="india", region="asia pacific",
        title="India Online Grocery Market Size"))
    assert bank.primary_anchor == "India Online Grocery Market"
    # variations exist and none repeats the primary
    assert bank.secondary_anchors
    assert bank.commercial_anchors
    assert bank.primary_anchor not in bank.secondary_anchors
    # a regional variation is included
    assert any("Asia Pacific" in a for a in bank.secondary_anchors)
    # restricted list holds the generics, and no descriptive anchor is generic
    assert "click here" in bank.restricted_anchors
    for group in (bank.secondary_anchors, bank.long_tail_anchors,
                  bank.commercial_anchors):
        assert not any(is_generic(a) for a in group)


def test_bank_never_doubles_market():
    bank = AnchorTextAgent._bank_for(_Row(
        node_id="n1", url="https://x/y", market="Cold Storage Market",
        country="uae", region="", title=""))
    everything = ([bank.primary_anchor] + bank.secondary_anchors
                  + bank.long_tail_anchors + bank.commercial_anchors)
    assert not any("Market Market" in a for a in everything)


def test_stored_banks_exist():
    conn = sqlite3.connect("ken_links.db")
    n = conn.execute("SELECT COUNT(*) FROM anchor_banks").fetchone()[0]
    conn.close()
    assert n > 0


# ── anchor bank API ──────────────────────────────────────────────────────────

def test_page_anchors_endpoint():
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        "SELECT target_node_id FROM anchor_banks LIMIT 1").fetchone()
    conn.close()
    if row:
        r = client.get(f"/api/pages/{row[0]}/anchors")
        assert r.status_code == 200
        body = r.json()
        assert body["has_bank"] is True
        assert body["primary_anchor"]
    assert client.get("/api/pages/nope/anchors").status_code == 404


# ── editorial decision API ───────────────────────────────────────────────────

def test_approve_then_reject_recommendation():
    # This test writes through the real endpoint, so it captures the original
    # row and restores it at the end. A test must not drift real data.
    conn = sqlite3.connect("ken_links.db")
    orig = conn.execute(
        "SELECT recommendation_id, status, approved_by, anchor_text, "
        "risk_reason, updated_at FROM link_recommendations LIMIT 1").fetchone()
    conn.close()
    rid = orig[0]
    try:
        # approve, with an anchor edit
        r = client.patch(f"/api/recommendations/{rid}", json={
            "decision": "approve", "reviewed_by": "tester",
            "edited_anchor": "India Online Grocery Market Outlook"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "approved"
        assert body["approved_by"] == "tester"
        assert body["anchor_text"] == "India Online Grocery Market Outlook"

        # reject also works
        r2 = client.patch(f"/api/recommendations/{rid}", json={
            "decision": "reject", "reviewed_by": "tester"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "rejected"
    finally:
        conn = sqlite3.connect("ken_links.db")
        conn.execute(
            "UPDATE link_recommendations SET status=?, approved_by=?, "
            "anchor_text=?, risk_reason=?, updated_at=? WHERE recommendation_id=?",
            (orig[1], orig[2], orig[3], orig[4], orig[5], rid))
        conn.commit()
        conn.close()


def test_decision_validation_and_404():
    conn = sqlite3.connect("ken_links.db")
    rid = conn.execute(
        "SELECT recommendation_id FROM link_recommendations LIMIT 1").fetchone()[0]
    conn.close()
    # invalid decision value
    bad = client.patch(f"/api/recommendations/{rid}", json={
        "decision": "maybe", "reviewed_by": "t"})
    assert bad.status_code == 422
    # unknown recommendation
    missing = client.patch("/api/recommendations/does-not-exist", json={
        "decision": "approve", "reviewed_by": "t"})
    assert missing.status_code == 404
