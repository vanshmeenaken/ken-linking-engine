"""MCP-8 Search Console Server (master PRD section 11).

Read-only access to the REAL Google Search Console data synced into
integration_placeholders by scripts/19_sync_gsc.py (verified side-by-side
against Google's own console during Phase 2).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from mcp_servers._db import find_node_by_url, rows


def _page_metrics(url: str) -> dict:
    node = find_node_by_url(url)
    if not node:
        return {"found": False, "url": url}
    metrics = rows(
        """SELECT metric_name, metric_value, date_range FROM
           integration_placeholders
           WHERE source = 'gsc' AND node_id = ? AND status = 'matched'""",
        (node["node_id"],))
    if not metrics:
        return {"found": True, "url": node["url"], "has_gsc_data": False,
                "note": "no GSC rows matched this page in the last sync"}
    out = {"found": True, "url": node["url"], "has_gsc_data": True,
           "date_range": metrics[0]["date_range"]}
    for m in metrics:
        out[m["metric_name"]] = m["metric_value"]
    return out


def get_page_queries(url: str) -> dict:
    """All synced GSC metrics for one page (queries are not stored
    per-page in the current sync; page-level metrics are)."""
    return _page_metrics(url)


def get_page_impressions(url: str) -> dict:
    """Search impressions for one page."""
    m = _page_metrics(url)
    return {k: m[k] for k in ("found", "url", "date_range", "impressions")
            if k in m} if m.get("has_gsc_data") else m


def get_page_clicks(url: str) -> dict:
    """Search clicks for one page."""
    m = _page_metrics(url)
    return {k: m[k] for k in ("found", "url", "date_range", "clicks")
            if k in m} if m.get("has_gsc_data") else m


def get_page_ctr(url: str) -> dict:
    """Click-through rate for one page."""
    m = _page_metrics(url)
    return {k: m[k] for k in ("found", "url", "date_range", "ctr")
            if k in m} if m.get("has_gsc_data") else m


def get_page_average_position(url: str) -> dict:
    """Average search ranking position for one page."""
    m = _page_metrics(url)
    return {k: m[k] for k in ("found", "url", "date_range", "position")
            if k in m} if m.get("has_gsc_data") else m


def get_pages_with_high_impressions_low_ctr(limit: int = 25) -> list[dict]:
    """Pages people see in search but rarely click - link/title opportunities."""
    return rows(
        """SELECT i.url, imp.metric_value AS impressions,
                  i.metric_value AS ctr
           FROM integration_placeholders i
           JOIN integration_placeholders imp
             ON imp.node_id = i.node_id AND imp.source = 'gsc'
            AND imp.metric_name = 'impressions'
           WHERE i.source = 'gsc' AND i.metric_name = 'ctr'
             AND i.status = 'matched'
             AND CAST(imp.metric_value AS REAL) > 100
             AND CAST(i.metric_value AS REAL) < 0.01
           ORDER BY CAST(imp.metric_value AS REAL) DESC LIMIT ?""",
        (min(int(limit), 200),))


def get_pages_ranking_positions_4_to_20(limit: int = 25) -> list[dict]:
    """Striking-distance pages (positions 4-20): closest to page-1 wins,
    the priority targets for internal links."""
    return rows(
        """SELECT url, metric_value AS position FROM integration_placeholders
           WHERE source = 'gsc' AND metric_name = 'position'
             AND status = 'matched'
             AND CAST(metric_value AS REAL) BETWEEN 4 AND 20
           ORDER BY CAST(metric_value AS REAL) LIMIT ?""",
        (min(int(limit), 500),))


def get_indexing_status() -> dict:
    """Inventory-level indexability summary (from crawl data; GSC's own
    index-coverage API is not part of the current sync)."""
    counts = rows(
        """SELECT indexability_status, COUNT(*) AS pages FROM content_nodes
           GROUP BY indexability_status""")
    return {"by_indexability": {r["indexability_status"]: r["pages"]
                                for r in counts},
            "note": "from crawl data; GSC index-coverage API not synced"}


server = MCPServer(
    name="ken-search-console",
    instructions="Read-only Google Search Console data (synced, verified "
                 "against Google's console). Covers pages matched in the "
                 "last sync window.")
for fn in (get_page_queries, get_page_impressions, get_page_clicks,
           get_page_ctr, get_page_average_position,
           get_pages_with_high_impressions_low_ctr,
           get_pages_ranking_positions_4_to_20, get_indexing_status):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
