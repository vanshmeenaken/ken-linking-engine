"""Normalization tests for config/taxonomy.py (Phase 2, Day 2 Module 2.2)."""

from config.taxonomy import (
    ENTITY_TYPES,
    classify_geo,
    extract_market_from_title,
    normalize_country,
    normalize_industry,
    normalize_market_name,
    region_for_country,
)


def test_entity_types_match_master_prd():
    assert len(ENTITY_TYPES) == 15
    for required in ("industry", "market", "segment", "country", "region"):
        assert required in ENTITY_TYPES


def test_country_aliases_resolve_to_one_entity():
    # Phase 2 plan Day 4 acceptance: UAE and United Arab Emirates → one entity
    assert normalize_country("UAE") == "uae"
    assert normalize_country("United Arab Emirates") == "uae"
    assert normalize_country("u.a.e.") == "uae"
    assert normalize_country("KSA") == "saudi arabia"
    assert normalize_country("Kingdom of Saudi Arabia") == "saudi arabia"
    assert normalize_country("United States") == "usa"
    assert normalize_country("Viet Nam") == "vietnam"


def test_scope_values_are_not_countries():
    # Day 1 audit finding #3: global/gcc stored in the country column
    assert normalize_country("global") == ""
    assert normalize_country("gcc") == ""
    assert classify_geo("global") == ("region", "Global")
    assert classify_geo("gcc") == ("region", "Middle East")
    assert classify_geo("mena") == ("region", "Middle East")
    assert classify_geo("asia pacific") == ("region", "Asia Pacific")


def test_classify_geo_real_countries():
    assert classify_geo("India") == ("country", "india")
    assert classify_geo("United Arab Emirates") == ("country", "uae")
    assert classify_geo("nonsense value") == ("", "")


def test_region_for_country():
    assert region_for_country("india") == "Asia Pacific"
    assert region_for_country("saudi arabia") == "Middle East"
    assert region_for_country("UAE") == "Middle East"
    assert region_for_country("brazil") == "Latin America"
    assert region_for_country("unknown") == ""


def test_industry_normalization():
    assert normalize_industry("healthcare") == "Healthcare"
    assert normalize_industry("Technology & Telecom") == "Technology & Telecom"
    assert normalize_industry("technology and telecom") == "Technology & Telecom"
    # Prefix tolerance (same as Agent 1)
    assert normalize_industry("Automotive, Transportation and Warehousing") == (
        "Automotive, Transportation & Logistics"
    )
    assert normalize_industry("not an industry") == ""
    # Review finding: real Phase 1 labels that must resolve via aliases
    assert normalize_industry("Banking Financial Services and Insurance") == "BFSI"
    assert normalize_industry("Educational Services") == "Education & Recruitment"
    # Deliberately unmapped labels (not industries / ambiguous)
    assert normalize_industry("Articles") == ""
    assert normalize_industry("Consulting") == ""


def test_market_extraction_pipe_pattern():
    # Observed pattern 1: "{Geo} {Market} | 2019-2030 | Ken Research"
    result = extract_market_from_title(
        "Qatar Aviation Cybersecurity Market | 2019-2030 | Ken Research",
        geography_words=["qatar"],
    )
    assert result == "Aviation Cybersecurity Market"


def test_market_extraction_trends_report_pattern():
    # Observed pattern 2: "{Geo} {Market} Share, Companies & Trends Report 2025-2031"
    result = extract_market_from_title(
        "Bahrain Pectin Market Share, Companies & Trends Report 2025-2031",
        geography_words=["bahrain"],
    )
    assert result == "Pectin Market"


def test_market_extraction_multiword_geography():
    result = extract_market_from_title(
        "United Arab Emirates Low GWP Refrigerants Market Share, Companies & Trends Report 2025-2031",
        geography_words=["united arab emirates"],
    )
    assert result == "Low GWP Refrigerants Market"


def test_market_extraction_handles_mojibake_dash():
    # Day 1 audit: "Indonesia Basalt Fiber Market | 2019 � 2030 | Ken Research"
    result = extract_market_from_title(
        "Indonesia Basalt Fiber Market | 2019 � 2030 | Ken Research",
        geography_words=["indonesia"],
    )
    assert result == "Basalt Fiber Market"


def test_market_extraction_rejects_unusable_titles():
    assert extract_market_from_title("") == ""
    assert extract_market_from_title("Ken Research") == ""
    assert extract_market_from_title("Market") == ""  # one word only


def test_normalized_market_name_dedup_key():
    a = normalize_market_name("Pectin Market")
    b = normalize_market_name("  pectin   market ")
    assert a == b == "pectin market"


def test_market_extraction_rejects_nan_corruption():
    # Real Phase 1 data corruption: pandas NaN leaked into title field
    assert extract_market_from_title(
        "nan Market Analysis, Trends & Forecast 2025-2031",
        geography_words=["philippines"],
    ) == ""
    assert extract_market_from_title("nan Market Size & Forecast Report") == ""
