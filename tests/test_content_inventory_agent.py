from bs4 import BeautifulSoup

from agents.agent_1_content_inventory import (
    PageResult,
    calculate_authority_scores,
    calculate_crawl_depth,
    classify_content_type,
    determine_orphan_status,
    normalize_url,
)


def test_normalize_url():
    assert normalize_url(
        "HTTP://KENRESEARCH.COM/articles/example/?utm_source=test#section"
    ) == "https://www.kenresearch.com/articles/example"


def test_calculate_structural_depth():
    assert calculate_crawl_depth("https://www.kenresearch.com/") == 0
    assert calculate_crawl_depth("https://www.kenresearch.com/report/india/ev") == 3


def test_classification_uses_strong_url_patterns():
    assert classify_content_type(
        "https://www.kenresearch.com/articles/ev-market", "report"
    ) == "article"
    assert classify_content_type(
        "https://www.kenresearch.com/case-studies/client", "report"
    ) == "case_study"


def test_classification_uses_live_page_evidence():
    soup = BeautifulSoup(
        "<nav class='breadcrumb'>Home / Articles</nav>", "html.parser"
    )
    assert classify_content_type(
        "https://www.kenresearch.com/insight/example", "", soup
    ) == "article"


def test_trusted_inventory_type_beats_generic_template_text():
    soup = BeautifulSoup(
        "<nav class='breadcrumb'>Consulting services</nav>", "html.parser"
    )
    assert classify_content_type(
        "https://www.kenresearch.com/india-ev-market", "report", soup
    ) == "report"


def test_orphan_status_boundaries():
    assert determine_orphan_status(0) == "orphan"
    assert determine_orphan_status(1) == "under_linked"
    assert determine_orphan_status(2) == "under_linked"
    assert determine_orphan_status(3) == "normal"
    assert determine_orphan_status(5) == "normal"
    assert determine_orphan_status(6) == "well_linked"


def test_authority_scores_are_bounded_and_monotonic():
    low = PageResult(
        node_id="1", requested_url="https://www.kenresearch.com/a",
        http_status=200, internal_links_in=0, internal_links_out=1,
    )
    high = PageResult(
        node_id="2", requested_url="https://www.kenresearch.com/b",
        http_status=200, internal_links_in=10, internal_links_out=20,
    )
    calculate_authority_scores([low, high])
    assert 0 <= low.page_authority_score < high.page_authority_score <= 100
