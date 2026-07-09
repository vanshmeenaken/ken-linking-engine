"""Tests for Agent 3 relationship mapping (Phase 2, Day 6 / final-PRD Jul 9)."""

import sqlite3

import pytest

from agents.agent_3_relationship_mapping import RelationshipMappingAgent


@pytest.fixture()
def agent(tmp_path):
    return RelationshipMappingAgent(db_path=tmp_path / "unused.db")


def _row(node_id, content_type="report", country="", region="", market="",
        global_or_local="local", url=None):
    return sqlite3.Row.__class__ if False else None  # placeholder, real rows built via sqlite3


def _make_db(tmp_path, nodes, entities):
    """nodes: list of dicts for content_nodes.
    entities: list of (node_id, entity_type, entity_name, entity_role) —
    creates one content_entities row per unique (name, type) and maps it."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE content_nodes (
            node_id TEXT PRIMARY KEY, url TEXT, content_type TEXT,
            country TEXT, region TEXT, market TEXT, global_or_local TEXT,
            status TEXT DEFAULT 'active');
        CREATE TABLE content_entities (
            entity_id TEXT PRIMARY KEY, entity_name TEXT, entity_type TEXT,
            normalized_name TEXT, parent_entity_id TEXT);
        CREATE TABLE node_entities (
            node_entity_id TEXT PRIMARY KEY, node_id TEXT, entity_id TEXT,
            entity_role TEXT, status TEXT DEFAULT 'extracted');
        CREATE TABLE relationship_edges (
            edge_id TEXT PRIMARY KEY, source_node_id TEXT, target_node_id TEXT,
            source_entity_id TEXT, target_entity_id TEXT, relationship_type TEXT,
            relationship_direction TEXT, confidence_score REAL,
            semantic_similarity_score REAL, entity_overlap_score REAL,
            geo_match_score REAL, market_match_score REAL,
            business_value_score REAL, seo_value_score REAL,
            created_by TEXT, status TEXT DEFAULT 'pending',
            created_at TEXT, updated_at TEXT,
            UNIQUE (source_node_id, target_node_id, relationship_type));
        CREATE TABLE entity_extraction_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, node_id TEXT,
            operation TEXT, status TEXT, entities_found INTEGER,
            low_confidence_count INTEGER, error TEXT, notes TEXT, created_at TEXT);
    """)
    for n in nodes:
        conn.execute(
            "INSERT INTO content_nodes VALUES (?,?,?,?,?,?,?,?)",
            (n["node_id"], n.get("url", f"https://x/{n['node_id']}"),
             n.get("content_type", "report"), n.get("country", ""),
             n.get("region", ""), n.get("market", ""),
             n.get("global_or_local", "local"), n.get("status", "active")),
        )
    entity_ids = {}
    for i, (node_id, etype, ename, erole) in enumerate(entities):
        key = (ename, etype)
        if key not in entity_ids:
            eid = f"ent-{i}"
            entity_ids[key] = eid
            conn.execute(
                "INSERT INTO content_entities VALUES (?,?,?,?,NULL)",
                (eid, ename, etype, ename.lower()),
            )
        conn.execute(
            "INSERT INTO node_entities VALUES (?,?,?,?, 'extracted')",
            (f"ne-{i}", node_id, entity_ids[key], erole),
        )
    conn.commit()
    conn.close()
    return path


def test_same_market_edge_created_between_two_pages_sharing_a_market(tmp_path):
    db = _make_db(
        tmp_path,
        nodes=[
            {"node_id": "n1", "region": "Middle East"},
            {"node_id": "n2", "region": "Middle East"},
        ],
        entities=[
            ("n1", "market", "Cold Storage Market", "primary_market"),
            ("n2", "market", "Cold Storage Market", "primary_market"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, summary = agent.run(dry_run=True)
    same_market = [e for e in result.edges if e.relationship_type == "same_market"]
    assert len(same_market) == 1
    assert {same_market[0].source_node_id, same_market[0].target_node_id} == {"n1", "n2"}


def test_no_same_market_edge_for_different_markets(tmp_path):
    db = _make_db(
        tmp_path,
        nodes=[{"node_id": "n1"}, {"node_id": "n2"}],
        entities=[
            ("n1", "market", "Cold Storage Market", "primary_market"),
            ("n2", "market", "Pectin Market", "primary_market"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    assert not any(e.relationship_type == "same_market" for e in result.edges)


def test_hub_market_precision_guard_skips_wide_clusters(tmp_path):
    # 13 pages all sharing one market — exceeds MAX_SAME_MARKET_PAGES_PER_ENTITY (12)
    nodes = [{"node_id": f"n{i}"} for i in range(13)]
    entities = [(f"n{i}", "market", "Generic Market", "primary_market") for i in range(13)]
    db = _make_db(tmp_path, nodes, entities)
    agent = RelationshipMappingAgent(db_path=db)
    result, summary = agent.run(dry_run=True)
    assert not any(e.relationship_type == "same_market" for e in result.edges)
    assert summary["hub_markets_skipped"] == 1


def test_country_region_requires_shared_industry(tmp_path):
    # hub (no country entity, has region) + local (has country) — SAME industry
    db = _make_db(
        tmp_path,
        nodes=[
            {"node_id": "hub", "region": "Middle East", "global_or_local": "global"},
            {"node_id": "local", "region": "Middle East", "country": "kuwait"},
        ],
        entities=[
            ("hub", "region", "Middle East", "region"),
            ("hub", "industry", "Technology & Telecom", "primary_industry"),
            ("local", "region", "Middle East", "region"),
            ("local", "country", "Kuwait", "country"),
            ("local", "industry", "Technology & Telecom", "primary_industry"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    cr = [e for e in result.edges if e.relationship_type == "country_region"]
    assert len(cr) == 1
    assert {cr[0].source_node_id, cr[0].target_node_id} == {"hub", "local"}


def test_country_region_rejects_mismatched_industry(tmp_path):
    # Regression: dry-run inspection found "GCC Coffee Market" wrongly linked
    # to "Kuwait Freight Trucking" — geography match alone is not enough.
    db = _make_db(
        tmp_path,
        nodes=[
            {"node_id": "hub", "region": "Middle East", "global_or_local": "global"},
            {"node_id": "local", "region": "Middle East", "country": "kuwait"},
        ],
        entities=[
            ("hub", "region", "Middle East", "region"),
            ("hub", "industry", "Food, Beverage & Tobacco", "primary_industry"),
            ("local", "region", "Middle East", "region"),
            ("local", "country", "Kuwait", "country"),
            ("local", "industry", "Automotive, Transportation & Logistics", "primary_industry"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    assert not any(e.relationship_type == "country_region" for e in result.edges)


def test_country_region_uses_entity_scope_not_stale_content_nodes_fields(tmp_path):
    # Regression: a page whose content_nodes.country/global_or_local are
    # stale ('global') but whose node_entities correctly holds a country
    # entity (Agent 2's fix) must be treated as LOCAL, not as a region hub.
    db = _make_db(
        tmp_path,
        nodes=[
            # stale content_nodes fields say 'global' — node_entities disagrees
            {"node_id": "stale_local", "country": "global",
             "global_or_local": "global", "region": "Middle East"},
            {"node_id": "other_local", "country": "kuwait",
             "region": "Middle East"},
        ],
        entities=[
            ("stale_local", "country", "UAE", "country"),  # entity-level truth
            ("stale_local", "region", "Middle East", "region"),
            ("stale_local", "industry", "Energy & Utilities", "primary_industry"),
            ("other_local", "country", "Kuwait", "country"),
            ("other_local", "region", "Middle East", "region"),
            ("other_local", "industry", "Energy & Utilities", "primary_industry"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    # Both pages have a country entity -> both are 'local' -> no hub exists
    # -> no country_region edge should be created between them
    assert not any(e.relationship_type == "country_region" for e in result.edges)


def test_global_local_edge_requires_same_market_and_different_scope(tmp_path):
    db = _make_db(
        tmp_path,
        nodes=[
            {"node_id": "g1", "global_or_local": "global"},
            {"node_id": "l1", "global_or_local": "local", "country": "bahrain"},
        ],
        entities=[
            ("g1", "market", "Silicone Market", "primary_market"),
            ("l1", "market", "Silicone Market", "primary_market"),
            ("l1", "country", "Bahrain", "country"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    gl = [e for e in result.edges if e.relationship_type == "global_local"]
    assert len(gl) == 1


def test_industry_market_edge_from_cooccurrence(tmp_path):
    db = _make_db(
        tmp_path,
        nodes=[{"node_id": "n1"}],
        entities=[
            ("n1", "market", "Freight Trucking Market", "primary_market"),
            ("n1", "industry", "Automotive, Transportation & Logistics", "primary_industry"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    im = [e for e in result.edges if e.relationship_type == "industry_market"]
    assert len(im) == 1
    assert im[0].source_node_id == "n1" and im[0].target_node_id == "n1"


def test_support_edge_requires_market_overlap_not_just_industry(tmp_path):
    # Regression: the old "weak" fallback linked completely unrelated
    # subjects sharing only industry+country (Sports Equipment case study ->
    # Online Grocery report). Must not happen anymore.
    db = _make_db(
        tmp_path,
        nodes=[
            {"node_id": "case", "content_type": "case_study", "country": "india"},
            {"node_id": "report", "content_type": "report", "country": "india"},
        ],
        entities=[
            ("case", "industry", "Consumer Products & Retail", "primary_industry"),
            ("case", "country", "India", "country"),
            ("case", "market", "Sports Equipment Market", "primary_market"),
            ("report", "industry", "Consumer Products & Retail", "primary_industry"),
            ("report", "country", "India", "country"),
            ("report", "market", "Online Grocery Market", "primary_market"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    assert not any(e.relationship_type == "case_study_support" for e in result.edges)


def test_support_edge_created_when_market_matches(tmp_path):
    db = _make_db(
        tmp_path,
        nodes=[
            {"node_id": "article", "content_type": "article"},
            {"node_id": "report", "content_type": "report"},
        ],
        entities=[
            ("article", "market", "Lubricants Market", "primary_market"),
            ("report", "market", "Lubricants Market", "primary_market"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    result, _ = agent.run(dry_run=True)
    ras = [e for e in result.edges if e.relationship_type == "report_article_support"]
    assert len(ras) == 1
    assert ras[0].source_node_id == "article" and ras[0].target_node_id == "report"


def test_live_run_writes_edges_and_is_idempotent(tmp_path):
    db = _make_db(
        tmp_path,
        nodes=[{"node_id": "n1"}, {"node_id": "n2"}],
        entities=[
            ("n1", "market", "Cold Storage Market", "primary_market"),
            ("n2", "market", "Cold Storage Market", "primary_market"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    agent.run(dry_run=False)
    conn = sqlite3.connect(db)
    count1 = conn.execute("SELECT COUNT(*) FROM relationship_edges").fetchone()[0]
    conn.close()
    assert count1 == 1

    # Re-run: must not create a duplicate row (unique index + ON CONFLICT)
    agent2 = RelationshipMappingAgent(db_path=db)
    agent2.run(dry_run=False)
    conn = sqlite3.connect(db)
    count2 = conn.execute("SELECT COUNT(*) FROM relationship_edges").fetchone()[0]
    status = conn.execute("SELECT status FROM relationship_edges").fetchone()[0]
    conn.close()
    assert count2 == 1
    assert status == "pending"


def test_stale_pending_edges_removed_on_rerun(tmp_path):
    # Regression: after source data changes, a re-run must remove edges the
    # agent created before but no longer produces (industry-cleanup re-run
    # left 94 stale edges before this fix).
    db = _make_db(
        tmp_path,
        nodes=[{"node_id": "n1"}, {"node_id": "n2"}],
        entities=[
            ("n1", "market", "Cold Storage Market", "primary_market"),
            ("n2", "market", "Cold Storage Market", "primary_market"),
        ],
    )
    RelationshipMappingAgent(db_path=db).run(dry_run=False)
    # Inject a stale pending agent_3 edge that current logic won't produce
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO relationship_edges (edge_id, source_node_id, target_node_id, "
        "relationship_type, created_by, status) VALUES "
        "('stale-1','n1','n2','industry_market','agent_3','pending')"
    )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM relationship_edges").fetchone()[0] == 2
    conn.close()

    _, summary = RelationshipMappingAgent(db_path=db).run(dry_run=False)
    conn = sqlite3.connect(db)
    remaining = {r[0] for r in conn.execute("SELECT edge_id FROM relationship_edges")}
    conn.close()
    assert "stale-1" not in remaining
    assert summary["stale_edges_removed"] == 1


def test_human_reviewed_edges_are_not_removed_as_stale(tmp_path):
    # A stale edge a human APPROVED (or rejected) must be preserved — only
    # untouched 'pending' agent edges are cleanup-eligible.
    db = _make_db(
        tmp_path,
        nodes=[{"node_id": "n1"}, {"node_id": "n2"}],
        entities=[
            ("n1", "market", "Cold Storage Market", "primary_market"),
            ("n2", "market", "Cold Storage Market", "primary_market"),
        ],
    )
    RelationshipMappingAgent(db_path=db).run(dry_run=False)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO relationship_edges (edge_id, source_node_id, target_node_id, "
        "relationship_type, created_by, status) VALUES "
        "('human-kept','n1','n2','industry_market','agent_3','approved')"
    )
    conn.commit()
    conn.close()

    RelationshipMappingAgent(db_path=db).run(dry_run=False)
    conn = sqlite3.connect(db)
    remaining = {r[0] for r in conn.execute("SELECT edge_id FROM relationship_edges")}
    conn.close()
    assert "human-kept" in remaining  # approved edge survives the re-run


def test_edges_default_status_pending(tmp_path):
    db = _make_db(
        tmp_path,
        nodes=[{"node_id": "n1"}, {"node_id": "n2"}],
        entities=[
            ("n1", "market", "Pectin Market", "primary_market"),
            ("n2", "market", "Pectin Market", "primary_market"),
        ],
    )
    agent = RelationshipMappingAgent(db_path=db)
    agent.run(dry_run=False)
    conn = sqlite3.connect(db)
    statuses = [r[0] for r in conn.execute("SELECT status FROM relationship_edges")]
    conn.close()
    assert all(s == "pending" for s in statuses)
