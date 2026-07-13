"""Tests for Agent 4 SEO Opportunity (Phase 2, Day 3)."""

import sqlite3

import pytest

from agents.agent_4_seo_opportunity import SEOOpportunityAgent


def _make_db(tmp_path, nodes, entities=(), edges=()):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE content_nodes (
            node_id TEXT PRIMARY KEY, url TEXT, content_type TEXT, title TEXT,
            h1 TEXT, meta_description TEXT, internal_links_in INTEGER,
            orphan_status TEXT, page_authority_score REAL, intent_stage TEXT,
            global_or_local TEXT, business_priority TEXT,
            search_opportunity_score REAL, status TEXT DEFAULT 'active',
            updated_at TEXT);
        CREATE TABLE content_entities (
            entity_id TEXT PRIMARY KEY, entity_name TEXT, entity_type TEXT,
            normalized_name TEXT);
        CREATE TABLE node_entities (
            node_entity_id TEXT PRIMARY KEY, node_id TEXT, entity_id TEXT,
            entity_role TEXT, confidence_score REAL, status TEXT DEFAULT 'extracted');
        CREATE TABLE relationship_edges (
            edge_id TEXT PRIMARY KEY, source_node_id TEXT, target_node_id TEXT,
            relationship_type TEXT);
        CREATE TABLE seo_opportunities (
            opportunity_id TEXT PRIMARY KEY, node_id TEXT, opportunity_type TEXT,
            priority TEXT, reason TEXT, evidence TEXT, seo_score REAL,
            business_score REAL, status TEXT DEFAULT 'open',
            created_at TEXT, updated_at TEXT,
            UNIQUE (node_id, opportunity_type));
        CREATE TABLE entity_extraction_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, node_id TEXT,
            operation TEXT, status TEXT, entities_found INTEGER,
            low_confidence_count INTEGER, error TEXT, notes TEXT, created_at TEXT);
    """)
    for n in nodes:
        conn.execute(
            "INSERT INTO content_nodes (node_id, url, content_type, title, h1, "
            "meta_description, internal_links_in, orphan_status, "
            "page_authority_score, intent_stage, global_or_local, "
            "business_priority, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (n["node_id"], n.get("url", f"https://x/{n['node_id']}"),
             n.get("content_type", "report"), n.get("title", "T"),
             n.get("h1", "H"), n.get("meta_description", "M"),
             n.get("internal_links_in", 3), n.get("orphan_status", "normal"),
             n.get("page_authority_score", 20.0), n.get("intent_stage", "decision"),
             n.get("global_or_local", "local"), n.get("business_priority"),
             n.get("status", "active")),
        )
    for i, (node_id, etype, conf) in enumerate(entities):
        eid = f"e{i}"
        conn.execute("INSERT INTO content_entities VALUES (?,?,?,?)",
                     (eid, etype.title(), etype, etype))
        conn.execute("INSERT INTO node_entities VALUES (?,?,?,?,?,'extracted')",
                     (f"ne{i}", node_id, eid, etype, conf))
    for i, (s, t) in enumerate(edges):
        conn.execute("INSERT INTO relationship_edges VALUES (?,?,?,?)",
                     (f"edge{i}", s, t, "same_market"))
    conn.commit()
    conn.close()
    return path


def _types(opps):
    from collections import Counter
    return Counter(o.opportunity_type for o in opps)


def test_orphan_page_detected(tmp_path):
    db = _make_db(tmp_path, [
        {"node_id": "n1", "orphan_status": "orphan", "internal_links_in": 0},
    ], entities=[("n1", "market", 0.9), ("n1", "country", 0.9)],
       edges=[("n1", "n1")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert _types(opps)["orphan_page"] == 1


def test_high_priority_underlinked_is_decision_intent(tmp_path):
    db = _make_db(tmp_path, [
        {"node_id": "n1", "orphan_status": "under_linked", "intent_stage": "decision",
         "internal_links_in": 2},
    ], entities=[("n1", "market", 0.9), ("n1", "country", 0.9)], edges=[("n1", "n1")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert _types(opps)["high_priority_underlinked"] == 1
    assert _types(opps)["underlinked_page"] == 0


def test_underlinked_awareness_is_not_high_priority(tmp_path):
    db = _make_db(tmp_path, [
        {"node_id": "n1", "orphan_status": "under_linked", "intent_stage": "awareness",
         "internal_links_in": 2},
    ], entities=[("n1", "market", 0.9), ("n1", "country", 0.9)], edges=[("n1", "n1")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert _types(opps)["underlinked_page"] == 1
    assert _types(opps)["high_priority_underlinked"] == 0


def test_missing_market_entity_detected(tmp_path):
    db = _make_db(tmp_path, [{"node_id": "n1"}],
                  entities=[("n1", "country", 0.9)], edges=[("n1", "n1")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert _types(opps)["missing_market_entity"] == 1


def test_missing_geo_and_relationships(tmp_path):
    db = _make_db(tmp_path, [{"node_id": "n1"}],
                  entities=[("n1", "market", 0.9)])  # no geo, no edges
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    t = _types(opps)
    assert t["missing_geo_entity"] == 1
    assert t["missing_relationships"] == 1


def test_low_confidence_entity_flagged(tmp_path):
    db = _make_db(tmp_path, [{"node_id": "n1"}],
                  entities=[("n1", "market", 0.9), ("n1", "country", 0.3)],
                  edges=[("n1", "n1")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert _types(opps)["entity_low_confidence"] == 1


def test_stale_metadata_flagged(tmp_path):
    db = _make_db(tmp_path, [
        {"node_id": "n1", "meta_description": ""},
    ], entities=[("n1", "market", 0.9), ("n1", "country", 0.9)], edges=[("n1", "n1")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert _types(opps)["stale_metadata"] == 1


def test_clean_page_has_no_opportunities(tmp_path):
    # Both pages are clean AND genuinely linked to each other. A page-to-page
    # edge is required here: a self-loop edge ("n1","n1") is a page-scoped
    # entity fact, not a link, and no longer suppresses missing_relationships.
    db = _make_db(tmp_path, [
        {"node_id": "n1", "orphan_status": "well_linked", "internal_links_in": 8},
        {"node_id": "n2", "orphan_status": "well_linked", "internal_links_in": 8},
    ], entities=[("n1", "market", 0.9), ("n1", "country", 0.9),
                 ("n2", "market", 0.9), ("n2", "country", 0.9)],
       edges=[("n1", "n2")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert len(opps) == 0


def test_search_opportunity_score_is_max_weight(tmp_path):
    # orphan (1.0) + missing_market (0.4) -> page score should be 1.0
    db = _make_db(tmp_path, [
        {"node_id": "n1", "orphan_status": "orphan", "internal_links_in": 0},
    ], entities=[("n1", "country", 0.9)], edges=[("n1", "n1")])
    SEOOpportunityAgent(db).run(dry_run=False)
    conn = sqlite3.connect(db)
    score = conn.execute(
        "SELECT search_opportunity_score FROM content_nodes WHERE node_id='n1'"
    ).fetchone()[0]
    conn.close()
    assert score == 1.0


def test_idempotent_rerun(tmp_path):
    # n1 is an orphan but IS genuinely linked to n2, so its only opportunity
    # is orphan_page. n2 is clean. Running twice must not duplicate rows.
    db = _make_db(tmp_path, [
        {"node_id": "n1", "orphan_status": "orphan", "internal_links_in": 0},
        {"node_id": "n2", "orphan_status": "well_linked", "internal_links_in": 8},
    ], entities=[("n1", "market", 0.9), ("n1", "country", 0.9),
                 ("n2", "market", 0.9), ("n2", "country", 0.9)],
       edges=[("n1", "n2")])
    SEOOpportunityAgent(db).run(dry_run=False)
    SEOOpportunityAgent(db).run(dry_run=False)
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM seo_opportunities").fetchone()[0]
    conn.close()
    assert n == 1  # orphan only, not duplicated


def test_no_global_local_gap_noise(tmp_path):
    # Regression: global_local_gap was firing for nearly every page. It's now
    # removed — a single-geography market page must NOT generate it.
    db = _make_db(tmp_path, [
        {"node_id": "n1", "global_or_local": "local"},
    ], entities=[("n1", "market", 0.9), ("n1", "country", 0.9)], edges=[("n1", "n1")])
    opps, _ = SEOOpportunityAgent(db).run(dry_run=True)
    assert _types(opps)["global_local_gap"] == 0
