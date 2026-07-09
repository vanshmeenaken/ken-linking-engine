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
