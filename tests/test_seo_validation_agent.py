"""Tests for Agent 10 SEO validation (master PRD §18 rule engine)."""

import sqlite3

import pytest

from agents.agent_10_seo_validation import SEOValidationAgent


def _make_db(tmp_path, nodes):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE content_nodes (
            node_id TEXT PRIMARY KEY, url TEXT, canonical_url TEXT,
            content_type TEXT, indexability_status TEXT,
            internal_links_out INTEGER, status TEXT)
    """)
    for n in nodes:
        conn.execute(
            "INSERT INTO content_nodes VALUES (?,?,?,?,?,?,?)",
            (n["node_id"], n["url"], n.get("canonical_url", n["url"]),
             n.get("content_type", "report"),
             n.get("indexability_status", "indexable"),
             n.get("internal_links_out", 5),
             n.get("status", "active")),
        )
    conn.commit()
    conn.close()
    return path


def _agent(tmp_path, nodes):
    return SEOValidationAgent(db_path=_make_db(tmp_path, nodes))


def test_clean_link_approved(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t"},
    ])
    r = agent.validate("s", "t", "India Electric Vehicle Market Outlook")
    assert r.overall_status == "approved_for_review"
    assert r.risk_flags == []
    assert r.approval_required is True


def test_non_canonical_target_rejected(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t", "canonical_url": "https://x/t-canonical"},
    ])
    r = agent.validate("s", "t", "Good Anchor Market", proposed_target_url="https://x/t")
    assert r.overall_status == "rejected"
    assert r.canonical_status == "FAIL"
    assert any(f.rule == "non_canonical_target" for f in r.risk_flags)


def test_noindex_target_rejected(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t", "indexability_status": "noindex"},
    ])
    r = agent.validate("s", "t", "Good Anchor Market")
    assert r.overall_status == "rejected"
    assert r.indexability_status == "FAIL"


def test_removed_page_rejected(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t",
         "indexability_status": "redirected_removed", "status": "removed"},
    ])
    r = agent.validate("s", "t", "Good Anchor Market")
    assert r.overall_status == "rejected"


@pytest.mark.parametrize("anchor", ["click here", "Read More", "this report", "learn more"])
def test_avoid_list_anchors_need_revision(tmp_path, anchor):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t"},
    ])
    r = agent.validate("s", "t", anchor)
    assert r.overall_status == "needs_revision"
    assert any(f.rule == "generic_anchor_text" for f in r.risk_flags)
    assert r.anchor_quality_score < 0.5


def test_empty_anchor_rejected(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t"},
    ])
    r = agent.validate("s", "t", "")
    assert r.overall_status == "rejected"
    assert r.anchor_quality_score == 0.0


def test_generic_single_word_anchor_flagged_medium(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t"},
    ])
    r = agent.validate("s", "t", "India")
    assert r.overall_status == "approved_for_review"  # MEDIUM alone still passes
    assert any(f.rule == "generic_single_word_anchor" for f in r.risk_flags)
    assert r.anchor_quality_score == 0.5


def test_faceted_url_flagged(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t?sort=latest&price=low"},
    ])
    r = agent.validate("s", "t", "Good Market Report",
                       proposed_target_url="https://x/t?sort=latest&price=low")
    # canonical_url defaults to the node's own (faceted) URL in this fixture,
    # so canonical check passes here — faceted_url_risk alone is HIGH, not
    # BLOCKER, so this needs human revision rather than outright rejection
    assert r.overall_status == "needs_revision"
    assert r.faceted_url_status == "FAIL"
    assert any(f.rule == "faceted_url_risk" for f in r.risk_flags)


def test_link_count_exceeded_flagged(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s", "content_type": "case_study",
         "internal_links_out": 12},  # case_study max is 12
        {"node_id": "t", "url": "https://x/t"},
    ])
    r = agent.validate("s", "t", "Good Market Report")
    assert r.link_count_status == "FAIL"
    assert r.overall_status == "needs_revision"  # HIGH severity — not silently approved


def test_self_link_rejected(tmp_path):
    agent = _agent(tmp_path, [{"node_id": "s", "url": "https://x/s"}])
    r = agent.validate("s", "s", "Good Market Report")
    assert r.overall_status == "rejected"
    assert any(f.rule == "self_link" for f in r.risk_flags)


def test_footer_placement_flagged_but_not_blocked(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t"},
    ])
    r = agent.validate("s", "t", "Good Market Report", placement="footer")
    assert r.overall_status == "approved_for_review"  # MEDIUM only
    assert any(f.rule == "footer_placement" for f in r.risk_flags)


def test_missing_node_rejected(tmp_path):
    agent = _agent(tmp_path, [{"node_id": "s", "url": "https://x/s"}])
    r = agent.validate("s", "does-not-exist", "Good Market Report")
    assert r.overall_status == "rejected"
    assert any(f.rule == "node_not_found" for f in r.risk_flags)


def test_deferred_checks_documented_not_silently_skipped(tmp_path):
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t"},
    ])
    r = agent.validate("s", "t", "Good Market Report")
    assert len(r.deferred_checks) == 2
    assert any("anchor_diversity" in d for d in r.deferred_checks)
    assert any("cannibalization" in d for d in r.deferred_checks)


def test_approval_required_always_true(tmp_path):
    # Master PRD §26 — no content-body link change auto-publishes, ever
    agent = _agent(tmp_path, [
        {"node_id": "s", "url": "https://x/s"},
        {"node_id": "t", "url": "https://x/t"},
    ])
    for anchor in ["Great Market Anchor", "click here", ""]:
        r = agent.validate("s", "t", anchor)
        assert r.approval_required is True
