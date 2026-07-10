"""Tests for Agent 2 entity extraction (Phase 2, Day 3)."""

from agents.agent_2_entity_extraction import (
    CONFIDENCE,
    LOW_CONFIDENCE_THRESHOLD,
    EntityExtractionAgent,
    _country_from_title,
)


def _node(**overrides):
    base = {
        "node_id": "test-node-1",
        "url": "https://www.kenresearch.com/bahrain-pectin-market",
        "title": "Bahrain Pectin Market Share, Companies & Trends Report 2025-2031",
        "h1": "Bahrain Pectin Market",
        "meta_description": "",
        "content_type": "report",
        "industry": "Metal, Mining and Chemicals",
        "country": "bahrain",
    }
    base.update(overrides)
    return base


def _agent():
    return EntityExtractionAgent(db_path=":memory:")


def _by_type(result, entity_type):
    return [e for e in result.entities if e.entity_type == entity_type]


def test_full_report_extraction():
    result = _agent().extract_node(_node())
    assert not result.error
    types = {e.entity_type for e in result.entities}
    assert types == {"industry", "country", "region", "market", "time_period"}

    (industry,) = _by_type(result, "industry")
    assert industry.entity_name == "Metal, Mining and Chemicals"
    assert industry.confidence == CONFIDENCE["db_field"]

    (country,) = _by_type(result, "country")
    assert country.normalized_name == "bahrain"

    (region,) = _by_type(result, "region")
    assert region.entity_name == "Middle East"

    (market,) = _by_type(result, "market")
    assert market.entity_name == "Pectin Market"
    # title + h1 agree + slug agrees -> capped confidence
    assert market.confidence == CONFIDENCE["market_cap"]

    (period,) = _by_type(result, "time_period")
    assert period.entity_name == "2025-2031"


def test_scope_country_field_recovers_country_from_title():
    # Dry-run finding: UAE report stored country='global'
    result = _agent().extract_node(_node(
        url="https://www.kenresearch.com/united-arab-emirates-low-gwp-refrigerants-market",
        title="United Arab Emirates Low GWP Refrigerants Market Share, Companies & Trends Report 2025-2031",
        h1="United Arab Emirates Low GWP Refrigerants Market",
        country="global",
    ))
    (country,) = _by_type(result, "country")
    assert country.normalized_name == "uae"
    assert country.source_field == "title"
    assert country.confidence == CONFIDENCE["country_from_title"]
    (region,) = _by_type(result, "region")
    assert region.entity_name == "Middle East"
    (market,) = _by_type(result, "market")
    assert market.entity_name == "Low GWP Refrigerants Market"


def test_scope_country_without_title_country_stays_region():
    result = _agent().extract_node(_node(
        url="https://www.kenresearch.com/global-blood-screening-market",
        title="Global Blood Screening Market | 2024-2030 | Ken Research",
        h1="Global Blood Screening Market",
        country="global",
    ))
    assert _by_type(result, "country") == []
    (region,) = _by_type(result, "region")
    assert region.entity_name == "Global"
    assert result.region_backfill == "Global"


def test_market_confidence_tiers():
    # Title only (H1 disagrees, slug disagrees) -> base confidence
    result = _agent().extract_node(_node(
        url="https://www.kenresearch.com/something-else-entirely",
        title="Bahrain Pectin Market | 2025 | Ken Research",
        h1="A completely different heading",
    ))
    (market,) = _by_type(result, "market")
    assert market.confidence == CONFIDENCE["market_title_base"]
    assert market.source_field == "title"


def test_narrative_case_study_title_yields_no_market():
    result = _agent().extract_node(_node(
        content_type="case_study",
        url="https://www.kenresearch.com/case-study/data-centre-win",
        title="How Ken Research Helped a Data Centre Brand Win Indonesia's Enterprise Cloud Market",
        h1="",
    ))
    assert _by_type(result, "market") == []


def test_extraction_never_raises_on_bad_node():
    result = _agent().extract_node({
        "node_id": "bad", "url": "https://www.kenresearch.com/x",
        "title": None, "h1": None, "meta_description": None,
        "content_type": "", "industry": None, "country": None,
    })
    # Missing fields must degrade gracefully, not crash the run
    assert isinstance(result.entities, list)


def test_country_from_title_prefers_longest_surface_form():
    assert _country_from_title(
        "United Arab Emirates Low GWP Refrigerants Market"
    ) == "uae"
    assert _country_from_title("India Dental Market") == "india"
    # Scope lead is not a country
    assert _country_from_title("Global Blood Screening Market") == ""
    assert _country_from_title("No Geography Here Market") == ""


def test_low_confidence_threshold_boundary():
    assert LOW_CONFIDENCE_THRESHOLD == 0.50
    result = _agent().extract_node(_node())
    assert all(not e.low_confidence for e in result.entities)


def test_market_falls_back_to_h1_when_title_corrupted():
    # nan-poisoned title, real market name only recoverable from H1
    result = _agent().extract_node(_node(
        url="https://www.kenresearch.com/philippines-ulcerative-colitis-market",
        title="nan Market Analysis, Trends & Forecast 2025-2031",
        h1="Philippines Ulcerative Colitis Market Report Size Share Growth Drivers "
           "Trends Opportunities & Forecast 2025-2030",
        country="philippines",
    ))
    (market,) = _by_type(result, "market")
    assert market.entity_name == "Ulcerative Colitis Market"
    # H1 is the primary source (title was corrupted); the URL slug also
    # agrees ("...ulcerative-colitis-market"), adding confidence
    assert market.source_field == "h1+url_slug"


def test_narrative_tail_fallback_recovers_article_market():
    result = _agent().extract_node(_node(
        content_type="article",
        url="https://www.kenresearch.com/articles/akzonobel-growth-strategy",
        title="AkzoNobel Growth in Vietnam Paints Market | Ken Research",
        h1="5% Growth in a 2% Market: How Is AkzoNobel Winning",
        country="vietnam",
    ))
    (market,) = _by_type(result, "market")
    assert market.entity_name == "Paints Market"
    assert "narrative_tail" in market.source_field
    assert market.confidence == CONFIDENCE["market_narrative_tail"]


def test_narrative_tail_fallback_scoped_to_articles_only():
    # Same narrative title, but on a case_study page — must NOT fire.
    # Case-study titles use a different style this fallback wasn't built
    # for (tested: 14/15 recoveries were garbage before this restriction).
    result = _agent().extract_node(_node(
        content_type="case_study",
        url="https://www.kenresearch.com/case-studies/akzonobel-growth-strategy",
        title="AkzoNobel Growth in Vietnam Paints Market | Ken Research",
        h1="5% Growth in a 2% Market: How Is AkzoNobel Winning",
        country="vietnam",
    ))
    assert _by_type(result, "market") == []


def _make_min_db(tmp_path, node):
    """Minimal real content_nodes table Agent 2's run() can read/write."""
    import sqlite3
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE content_nodes (
            node_id TEXT PRIMARY KEY, url TEXT, title TEXT, h1 TEXT,
            meta_description TEXT, content_type TEXT, industry TEXT,
            country TEXT, market TEXT DEFAULT '', region TEXT DEFAULT '',
            status TEXT DEFAULT 'active', updated_at TEXT);
        CREATE TABLE content_entities (
            entity_id TEXT PRIMARY KEY, entity_name TEXT, entity_type TEXT,
            normalized_name TEXT, aliases TEXT, industry TEXT, country TEXT,
            region TEXT, confidence_score REAL, created_at TEXT, updated_at TEXT,
            UNIQUE (normalized_name, entity_type));
        CREATE TABLE node_entities (
            node_entity_id TEXT PRIMARY KEY, node_id TEXT, entity_id TEXT,
            entity_role TEXT, source_field TEXT, extracted_value TEXT,
            normalized_value TEXT, confidence_score REAL, extraction_method TEXT,
            status TEXT DEFAULT 'extracted', created_at TEXT, updated_at TEXT,
            UNIQUE (node_id, entity_id, entity_role));
        CREATE TABLE entity_extraction_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, node_id TEXT,
            operation TEXT, status TEXT, entities_found INTEGER,
            low_confidence_count INTEGER, error TEXT, notes TEXT, created_at TEXT);
    """)
    conn.execute(
        "INSERT INTO content_nodes (node_id, url, title, h1, meta_description, "
        "content_type, industry, country, status) VALUES (?,?,?,?,?,?,?,?,'active')",
        (node["node_id"], node["url"], node["title"], node["h1"], "",
         node.get("content_type", "report"), node.get("industry", ""),
         node.get("country", "")),
    )
    conn.commit()
    conn.close()
    return path


def test_stale_mapping_removed_when_extraction_no_longer_produces_it(tmp_path):
    # Regression: a case-study page kept two generations of a wrong market
    # entity across re-runs (a guard fix now correctly rejects the title,
    # but the old mapping wasn't cleaned up). Run once with a title that
    # extracts a market, then edit the title so extraction correctly
    # produces nothing, re-run, and confirm the stale row is gone.
    db = _make_min_db(tmp_path, {
        "node_id": "n1", "url": "https://www.kenresearch.com/x",
        "title": "India Sleep Market", "h1": "India Sleep Market",
        "country": "india",
    })
    import sqlite3
    agent1 = EntityExtractionAgent(db_path=db)
    agent1.run(dry_run=False)
    conn = sqlite3.connect(db)
    assert conn.execute(
        "SELECT COUNT(*) FROM node_entities WHERE node_id='n1' AND entity_role='primary_market'"
    ).fetchone()[0] == 1
    conn.close()

    # Now the title no longer yields a market at all
    conn = sqlite3.connect(db)
    conn.execute("UPDATE content_nodes SET title=?, h1=? WHERE node_id='n1'",
                 ("Completely Unrelated Story About Nothing Specific", "Completely Unrelated Story About Nothing Specific"))
    conn.commit()
    conn.close()

    agent2 = EntityExtractionAgent(db_path=db)
    _, summary = agent2.run(dry_run=False)
    conn = sqlite3.connect(db)
    remaining = conn.execute(
        "SELECT COUNT(*) FROM node_entities WHERE node_id='n1' AND entity_role='primary_market'"
    ).fetchone()[0]
    conn.close()
    assert remaining == 0
    assert summary["stale_mappings_removed"] == 1


def test_human_reviewed_mapping_not_removed_as_stale(tmp_path):
    db = _make_min_db(tmp_path, {
        "node_id": "n1", "url": "https://www.kenresearch.com/x",
        "title": "India Sleep Market", "h1": "India Sleep Market",
        "country": "india",
    })
    import sqlite3
    EntityExtractionAgent(db_path=db).run(dry_run=False)
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE node_entities SET status='approved' WHERE node_id='n1' "
        "AND entity_role='primary_market'"
    )
    conn.commit()
    conn.execute("UPDATE content_nodes SET title=?, h1=? WHERE node_id='n1'",
                 ("Completely Unrelated Story About Nothing Specific", "Completely Unrelated Story About Nothing Specific"))
    conn.commit()
    conn.close()

    EntityExtractionAgent(db_path=db).run(dry_run=False)
    conn = sqlite3.connect(db)
    remaining = conn.execute(
        "SELECT COUNT(*) FROM node_entities WHERE node_id='n1' AND entity_role='primary_market'"
    ).fetchone()[0]
    conn.close()
    assert remaining == 1  # approved mapping survives
