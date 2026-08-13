"""Tests for the 9 MCP servers (master PRD section 11): every tool function
is called directly against the live DB - counts where data exists, clean
shapes, and graceful unknown-id paths. The MCP protocol layer itself is the
SDK's job; what we own is the tool logic."""

import asyncio

import pytest

from mcp_servers import (content_inventory, crawler, embedding_search,
                         evidence_library, ga4, knowledge_graph, report_store,
                         search_console, seo_rules)

ALL_SERVERS = [content_inventory, knowledge_graph, embedding_search,
               evidence_library, seo_rules, crawler, search_console, ga4,
               report_store]

A_REAL_URL = "https://www.kenresearch.com/industry-reports/south-africa-e-learning-market"


# ── every server registers its tools ─────────────────────────────────────────

@pytest.mark.parametrize("module", ALL_SERVERS,
                         ids=[m.__name__.split(".")[-1] for m in ALL_SERVERS])
def test_server_registers_tools(module):
    tools = asyncio.run(module.server.list_tools())
    assert len(tools) >= 6
    for t in tools:
        assert t.description, f"tool {t.name} has no description"


# ── content inventory ────────────────────────────────────────────────────────

def test_content_inventory_lookup_and_search():
    page = content_inventory.get_page_by_url(A_REAL_URL)
    assert page.get("node_id")
    assert content_inventory.search_pages("cold storage", limit=5)
    assert content_inventory.get_page_by_url("https://x/nope") == {
        "found": False, "url": "https://x/nope"}


def test_content_inventory_orphans_and_recent():
    assert isinstance(content_inventory.get_orphan_pages(limit=5), list)
    recent = content_inventory.get_recently_published_pages(limit=3)
    assert len(recent) <= 3


# ── knowledge graph ──────────────────────────────────────────────────────────

def test_knowledge_graph_page_relationships():
    rels = knowledge_graph.get_relationships_for_page(A_REAL_URL)
    assert isinstance(rels, list)
    for r in rels:
        assert r["source_url"] and r["target_url"]


def test_knowledge_graph_explanation_unknown_edge():
    assert knowledge_graph.get_relationship_explanation("nope") == {
        "found": False, "edge_id": "nope"}


def test_knowledge_graph_has_no_write_tools():
    # the PRD lists create/update/reject edge tools; they are deliberately
    # absent (Agent 3's gated pipeline + human review own graph mutations)
    tools = {t.name for t in asyncio.run(knowledge_graph.server.list_tools())}
    for forbidden in ("create_relationship_edge",
                      "update_relationship_confidence", "reject_relationship"):
        assert forbidden not in tools


# ── embedding search ─────────────────────────────────────────────────────────

def test_embedding_search_pages_and_similarity():
    hits = embedding_search.semantic_search_pages("cold storage logistics",
                                                  limit=3)
    assert hits and all(h["score"] > 0 for h in hits)
    sim = embedding_search.get_embedding_similarity_score(
        "cold storage market", "cold chain warehousing")
    assert 0 <= sim["similarity"] <= 1


def test_embedding_search_similar_reports_excludes_self():
    similar = embedding_search.find_similar_reports(A_REAL_URL, limit=5)
    assert all(s["url"].rstrip("/") != A_REAL_URL.rstrip("/") for s in similar)


# ── evidence library ─────────────────────────────────────────────────────────

def test_evidence_library_search_and_unknown_id():
    claims = evidence_library.search_evidence("CAGR", limit=5)
    assert isinstance(claims, list)
    assert evidence_library.get_evidence_by_id("nope")["found"] is False


def test_evidence_library_case_studies():
    assert evidence_library.search_case_studies("market", limit=5)


# ── seo rules ────────────────────────────────────────────────────────────────

def test_seo_rules_anchor_validation():
    assert seo_rules.validate_anchor_text("click here")["valid"] is False
    assert seo_rules.validate_anchor_text(
        "India Electric Vehicle Market Outlook")["valid"] is True
    assert seo_rules.validate_anchor_text("")["valid"] is False


def test_seo_rules_placement_and_facets():
    assert seo_rules.validate_link_placement("contextual_body")["valid"] is True
    assert seo_rules.validate_link_placement("banner_ad")["valid"] is False
    assert seo_rules.validate_faceted_url_risk(
        "https://x/reports?sort=latest&price=low")["risky"] is True
    assert seo_rules.validate_faceted_url_risk(A_REAL_URL)["risky"] is False


def test_seo_rules_full_validation_runs():
    r = seo_rules.validate_recommendation(
        A_REAL_URL,
        "https://www.kenresearch.com/south-africa-e-learning-and-skills-platforms-market",
        "South Africa E-Learning and Skills Platforms Market")
    assert r["overall_status"] in ("approved_for_review", "needs_revision",
                                   "rejected")
    assert r["approval_required"] is True  # PRD section 26, always


# ── crawler ──────────────────────────────────────────────────────────────────

def test_crawler_db_backed_tools():
    assert isinstance(crawler.get_crawl_errors(limit=5), list)
    assert isinstance(crawler.get_blocked_urls(limit=5), list)
    over = crawler.get_pages_with_excessive_links(limit=3)
    assert len(over) <= 3


# ── search console / ga4 (live synced data) ──────────────────────────────────

def test_gsc_striking_distance_pages():
    pages = search_console.get_pages_ranking_positions_4_to_20(limit=5)
    assert isinstance(pages, list)
    for p in pages:
        assert 4 <= float(p["position"]) <= 20


def test_gsc_unknown_url_is_honest():
    r = search_console.get_page_clicks("https://x/never-seen")
    assert r["found"] is False


def test_ga4_top_pages_and_unknown_url():
    top = ga4.get_top_pages_by_sessions(limit=5)
    assert isinstance(top, list)
    assert ga4.get_page_sessions("https://x/never-seen")["found"] is False


# ── report store ─────────────────────────────────────────────────────────────

def test_report_store_search_and_related():
    reports = report_store.search_reports("e-learning", limit=5)
    assert reports
    related = report_store.get_related_reports(A_REAL_URL, limit=5)
    assert isinstance(related, list)


def test_report_store_metadata_unknown():
    assert report_store.get_report_metadata("https://x/nope")["found"] is False
