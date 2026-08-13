"""Tests for the manual interlinking workbench (/users): the sitemap cache
and related-page finder, plus the API a human uses to record link decisions
by hand (manual_link_plans)."""

import sqlite3

from fastapi.testclient import TestClient

from analysis.sitemap_index import (cache_status, classify_relation,
                                    find_related_in_sitemap, slug_of,
                                    slug_to_text)
from api.main import app

client = TestClient(app)

A_REPORT = ("https://www.kenresearch.com/industry-reports/"
            "south-africa-e-learning-and-skills-platforms-market")


# ── slug helpers ─────────────────────────────────────────────────────────────

def test_slug_of_handles_prefixes_and_noise():
    assert slug_of("https://www.kenresearch.com/industry-reports/india-ev-market") \
        == "india-ev-market"
    assert slug_of("https://www.kenresearch.com/india-ev-market/") == "india-ev-market"
    assert slug_of("https://www.kenresearch.com/india-ev-market?x=1#z") == "india-ev-market"


def test_slug_to_text_is_readable():
    assert slug_to_text("india-online-grocery-market") == "india online grocery market"


def test_classify_relation_distinguishes_same_subject_from_related():
    # same subject, different country -> regional
    assert classify_relation("india cold storage market",
                             "vietnam cold storage market") == "regional"
    # different subject, different country -> adjacent_regional
    assert classify_relation("india cold storage market",
                             "vietnam car rental market") == "adjacent_regional"
    # different subject, same country -> adjacent
    assert classify_relation("india cold storage market",
                             "india car rental market") == "adjacent"


# ── the sitemap cache ────────────────────────────────────────────────────────

def test_sitemap_cache_is_populated():
    status = cache_status()
    assert status["total"] > 100, "run refresh_sitemap_cache() to populate"
    # the report sitemap is the big one and must be present
    assert status["by_content_type"].get("report", 0) > 100


def test_sitemap_finder_returns_subject_matches_only():
    results = find_related_in_sitemap(A_REPORT, limit=10)
    assert results, "expected sitemap candidates for a real e-learning report"
    for r in results:
        # the subject gate must have accepted every candidate
        assert r["market_match_score"] >= 0.30
        assert r["technology_match_score"] >= 0.50
        assert r["found_via"] == "sitemap"
        assert r["url"] != A_REPORT


def test_sitemap_finder_excludes_the_source_itself():
    results = find_related_in_sitemap(A_REPORT, limit=40)
    assert all(slug_of(r["url"]) != slug_of(A_REPORT) for r in results)


def test_sitemap_finder_handles_nonsense_url():
    assert find_related_in_sitemap(
        "https://www.kenresearch.com/zzz-not-a-real-market-xyz", limit=5) == [] \
        or True  # a nonsense slug may match nothing; it must never raise


# ── the pages ────────────────────────────────────────────────────────────────

def test_users_page_and_button_are_served():
    r = client.get("/users")
    assert r.status_code == 200
    assert "Manual Interlinking Workbench" in r.text
    main = client.get("/dashboard")
    assert main.status_code == 200
    assert 'href="/users"' in main.text, "main dashboard is missing the Users button"


# ── related-page discovery ───────────────────────────────────────────────────

def test_related_prefers_inventory_then_tops_up_from_sitemap():
    r = client.get(f"/api/manual/related?url={A_REPORT}&limit=8")
    assert r.status_code == 200
    body = r.json()
    # the /industry-reports/ prefixed URL must still resolve to the inventory
    # row stored without that prefix (regression: it did not, so the trusted
    # relationship edges were skipped entirely)
    assert body["in_inventory"] is True
    assert body["counts"]["from_inventory"] > 0
    found_via = [c["found_via"] for c in body["candidates"]]
    assert found_via[0].startswith("inventory"), "inventory edges must come first"
    assert len(body["candidates"]) <= 8


def test_related_works_for_a_url_outside_the_inventory():
    # a real sitemap report that is NOT in the 500-page sample: the whole
    # point of the sitemap fallback
    conn = sqlite3.connect("ken_links.db")
    row = conn.execute(
        """SELECT s.url FROM sitemap_urls s
           WHERE s.content_type='report'
             AND NOT EXISTS (SELECT 1 FROM content_nodes n
                             WHERE LOWER(n.url) LIKE '%' || s.slug)
           LIMIT 1""").fetchone()
    conn.close()
    assert row is not None, "expected at least one sitemap-only report"
    r = client.get(f"/api/manual/related?url={row[0]}&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["in_inventory"] is False
    for c in body["candidates"]:
        assert c["found_via"] == "sitemap"


# ── reading the page's own content ───────────────────────────────────────────

def test_content_marks_blocked_sections_but_still_shows_them():
    r = client.get(f"/api/manual/content?url={A_REPORT}")
    assert r.status_code == 200
    body = r.json()
    assert body["section_count"] > 0
    purposes = {s["purpose"]: s["linkable"] for s in body["sections"]}
    # the editorial rule: the hero stat and Market Overview are never linkable
    if "intro" in purposes:
        assert purposes["intro"] is False
    if "overview" in purposes:
        assert purposes["overview"] is False
    # blocked sections are still returned - the reader must see the whole page
    assert any(not s["linkable"] for s in body["sections"])
    # paragraph indexes are unique and contiguous across the page
    idx = [p["paragraph_index"] for s in body["sections"] for p in s["paragraphs"]]
    assert idx == sorted(idx) and len(idx) == len(set(idx))


def test_content_reports_a_bad_url_honestly():
    r = client.get("/api/manual/content?url=https://not-a-real-domain-xyz.test/x")
    assert r.status_code == 502
    assert "Could not read" in r.json()["detail"]


# ── saving human decisions ───────────────────────────────────────────────────

def _cleanup(plan_id):
    conn = sqlite3.connect("ken_links.db")
    conn.execute("DELETE FROM manual_link_plans WHERE plan_id = ?", (plan_id,))
    conn.commit()
    conn.close()


def test_save_list_and_delete_a_decision():
    payload = {
        "source_url": A_REPORT,
        "target_url": "https://www.kenresearch.com/russia-e-learning-skills-platforms-market",
        "anchor_text": "Russia E-Learning Market",
        "section_heading": "Competitive Landscape Overview",
        "paragraph_index": 12,
        "paragraph_excerpt": "The market is fragmented across providers.",
        "placement_note": "end of the paragraph",
        "relation_label": "adjacent_regional",
        "found_via": "inventory_edge",
        "created_by": "pytest",
    }
    created = client.post("/api/manual/links", json=payload)
    assert created.status_code == 200
    plan_id = created.json()["plan_id"]
    try:
        listed = client.get(f"/api/manual/links?url={A_REPORT}")
        assert listed.status_code == 200
        assert any(p["plan_id"] == plan_id for p in listed.json()["plans"])
        mine = next(p for p in listed.json()["plans"] if p["plan_id"] == plan_id)
        assert mine["anchor_text"] == "Russia E-Learning Market"
        assert mine["created_by"] == "pytest"
        assert mine["status"] == "planned"
    finally:
        deleted = client.delete(f"/api/manual/links/{plan_id}")
        assert deleted.status_code == 200
        _cleanup(plan_id)
    assert client.delete(f"/api/manual/links/{plan_id}").status_code == 404


def test_self_link_and_empty_anchor_are_rejected():
    base = {"source_url": "https://www.kenresearch.com/a",
            "target_url": "https://www.kenresearch.com/a/",
            "anchor_text": "Something"}
    assert client.post("/api/manual/links", json=base).status_code == 422
    assert client.post("/api/manual/links", json={
        **base, "target_url": "https://www.kenresearch.com/b",
        "anchor_text": "   "}).status_code == 422


def test_manual_plans_are_separate_from_machine_recommendations():
    # human-authored instructions must never be written into the machine's
    # recommendation queue, or provenance is lost
    conn = sqlite3.connect("ken_links.db")
    before = conn.execute("SELECT COUNT(*) FROM link_recommendations").fetchone()[0]
    conn.close()
    created = client.post("/api/manual/links", json={
        "source_url": A_REPORT,
        "target_url": "https://www.kenresearch.com/global-e-learning-market",
        "anchor_text": "Global E-Learning Market", "created_by": "pytest"})
    plan_id = created.json()["plan_id"]
    conn = sqlite3.connect("ken_links.db")
    after = conn.execute("SELECT COUNT(*) FROM link_recommendations").fetchone()[0]
    conn.close()
    _cleanup(plan_id)
    assert before == after
