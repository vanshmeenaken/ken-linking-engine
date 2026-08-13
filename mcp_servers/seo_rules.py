"""MCP-5 SEO Rules Server (master PRD section 11).

Validation tools backed by Agent 10's rule engine and the shared anchor
rules. Pure checks - nothing is written anywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from agents.agent_10_seo_validation import (LINK_COUNT_RANGES,
                                            PLACEMENT_PRIORITY,
                                            SEOValidationAgent)
from analysis.anchor_text import GENERIC_ANCHORS, is_generic
from mcp_servers._db import DB_PATH, find_node_by_url

_agent = SEOValidationAgent(DB_PATH)


def validate_anchor_text(anchor: str) -> dict:
    """Whether an anchor is descriptive enough to use (PRD 18.3)."""
    anchor = (anchor or "").strip()
    if not anchor:
        return {"valid": False, "reason": "empty anchor"}
    if is_generic(anchor):
        return {"valid": False,
                "reason": f'"{anchor}" is on the never-use list',
                "never_use": sorted(GENERIC_ANCHORS)}
    if len(anchor.split()) == 1:
        return {"valid": True, "warning": "single-word anchor - prefer "
                "country + market + intent phrasing"}
    return {"valid": True, "reason": "descriptive anchor"}


def validate_canonical_target(url: str) -> dict:
    """Whether a URL is its own canonical (links must target canonicals)."""
    node = find_node_by_url(url)
    if not node:
        return {"valid": False, "reason": "URL not in inventory"}
    ok = node["url"] == node["canonical_url"]
    return {"valid": ok, "url": node["url"],
            "canonical_url": node["canonical_url"],
            "reason": "canonical" if ok else "link the canonical URL instead"}


def validate_indexable_target(url: str) -> dict:
    """Whether a target page is indexable (never link noindex/removed)."""
    node = find_node_by_url(url)
    if not node:
        return {"valid": False, "reason": "URL not in inventory"}
    ok = node["indexability_status"] == "indexable" and node["status"] == "active"
    return {"valid": ok, "indexability_status": node["indexability_status"],
            "page_status": node["status"]}


def validate_link_placement(placement: str) -> dict:
    """Whether a placement type is recognised, and its priority rank."""
    if placement in PLACEMENT_PRIORITY:
        return {"valid": True, "placement": placement,
                "priority_rank": PLACEMENT_PRIORITY.index(placement) + 1,
                "note": "1 = best (body paragraph); footer/sidebar are "
                        "flagged for review"}
    return {"valid": False, "placement": placement,
            "known_placements": list(PLACEMENT_PRIORITY)}


def validate_link_count(source_url: str, additional_links: int = 1) -> dict:
    """Whether adding N links would push a page past its type's maximum."""
    node = find_node_by_url(source_url)
    if not node:
        return {"valid": False, "reason": "URL not in inventory"}
    _, limit = LINK_COUNT_RANGES.get(
        node["content_type"], LINK_COUNT_RANGES["report"])
    projected = (node["internal_links_out"] or 0) + int(additional_links)
    return {"valid": projected <= limit,
            "current_links_out": node["internal_links_out"],
            "projected": projected, "maximum_for_type": limit,
            "content_type": node["content_type"]}


def validate_faceted_url_risk(url: str) -> dict:
    """Whether a URL looks like a faceted/parameterised page (PRD 18.7:
    never link those)."""
    risky = "?" in (url or "") and any(
        p in url.lower() for p in ("sort=", "price=", "filter=", "page=",
                                   "year=", "order="))
    return {"risky": risky,
            "reason": ("faceted/parameterised URL - link a curated landing "
                       "page instead" if risky else "no facet parameters")}


def validate_redirect_risk(url: str) -> dict:
    """Whether a URL is known to redirect (from crawl data)."""
    node = find_node_by_url(url)
    if not node:
        return {"known": False, "reason": "URL not in inventory"}
    redirected = node["indexability_status"] == "redirected_removed" or \
        node["status"] == "removed"
    return {"known": True, "redirects_or_removed": redirected,
            "indexability_status": node["indexability_status"]}


def validate_recommendation(source_url: str, target_url: str, anchor: str,
                            placement: str = "contextual_body") -> dict:
    """Full Agent 10 validation of a proposed link (all checks at once)."""
    source = find_node_by_url(source_url)
    target = find_node_by_url(target_url)
    if not source or not target:
        return {"overall_status": "rejected",
                "reason": "source or target not in inventory"}
    result = _agent.validate(source["node_id"], target["node_id"],
                             anchor, placement)
    return {"overall_status": result.overall_status,
            "approval_required": result.approval_required,
            "anchor_quality_score": result.anchor_quality_score,
            "risk_flags": [
                {"rule": f.rule, "severity": f.severity,
                 "description": f.description} for f in result.risk_flags],
            "deferred_checks": result.deferred_checks}


server = MCPServer(
    name="ken-seo-rules",
    instructions="SEO validation rules for internal links (Agent 10's rule "
                 "engine). Pure checks; nothing is modified.")
for fn in (validate_anchor_text, validate_canonical_target,
           validate_indexable_target, validate_link_placement,
           validate_link_count, validate_faceted_url_risk,
           validate_redirect_risk, validate_recommendation):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
