"""Unit and live-data checks for PRD report link planning."""
from types import SimpleNamespace

from analysis.report_link_planner import (
    recommendation_category,
    select_balanced_recommendations,
)


def _rec(source, target, score, category):
    return SimpleNamespace(
        source_node_id=source,
        target_node_id=target,
        link_score=score,
        plan_category=category,
        source_plan_rank=0,
    )


def test_recommendation_categories_separate_regional_and_adjacent_reports():
    assert recommendation_category(
        "same_market", "report", "report"
    ) == "regional_report"
    assert recommendation_category(
        "adjacent_market", "report", "report"
    ) == "adjacent_report"
    assert recommendation_category(
        "report_article_support", "article", "report"
    ) == "supporting_content"


def test_selector_respects_capacity_and_keeps_a_report_mix():
    facts = {
        "source": {"content_type": "report", "internal_links_out": 23},
        "adjacent": {"content_type": "report", "internal_links_out": 2},
        "regional": {"content_type": "report", "internal_links_out": 2},
        "article": {"content_type": "article", "internal_links_out": 2},
    }
    candidates = [
        _rec("source", "adjacent", 95, "adjacent_report"),
        _rec("source", "regional", 85, "regional_report"),
        _rec("source", "article", 80, "supporting_content"),
    ]
    selected = select_balanced_recommendations(candidates, facts, set())
    assert len(selected) == 2
    assert {rec.plan_category for rec in selected} == {
        "adjacent_report", "regional_report",
    }
    assert {rec.source_plan_rank for rec in selected} == {1, 2}


def test_selector_preserves_human_approval_at_capacity():
    facts = {
        "source": {"content_type": "report", "internal_links_out": 25},
        "approved": {"content_type": "report", "internal_links_out": 1},
        "new": {"content_type": "report", "internal_links_out": 1},
    }
    approved = _rec("source", "approved", 70, "regional_report")
    new = _rec("source", "new", 99, "adjacent_report")
    selected = select_balanced_recommendations(
        [new, approved], facts, {("source", "approved")}
    )
    assert selected == [approved]
