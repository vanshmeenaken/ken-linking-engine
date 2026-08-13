"""MCP-9 GA4 Server (master PRD section 11).

Read-only access to the REAL Google Analytics 4 data synced into
integration_placeholders by scripts/20_sync_ga4.py. Metrics available from
the sync: sessions, users, engaged_sessions, avg_engagement_seconds,
key_events. PRD tools with no synced data source (scroll depth, internal
link clicks, lead sources, assisted conversions) are honestly absent, not
faked - they need GA4 custom events that do not exist yet.
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
        """SELECT metric_name, metric_value, date_range
           FROM integration_placeholders
           WHERE source = 'ga4' AND node_id = ? AND status = 'matched'""",
        (node["node_id"],))
    if not metrics:
        return {"found": True, "url": node["url"], "has_ga4_data": False,
                "note": "no GA4 rows matched this page in the last sync"}
    out = {"found": True, "url": node["url"], "has_ga4_data": True,
           "date_range": metrics[0]["date_range"]}
    for m in metrics:
        out[m["metric_name"]] = m["metric_value"]
    return out


def get_page_sessions(url: str) -> dict:
    """Sessions and users for one page."""
    m = _page_metrics(url)
    if not m.get("has_ga4_data"):
        return m
    return {k: m[k] for k in ("found", "url", "date_range", "sessions",
                              "users") if k in m}


def get_page_engagement(url: str) -> dict:
    """Engagement metrics for one page (engaged sessions, avg seconds)."""
    m = _page_metrics(url)
    if not m.get("has_ga4_data"):
        return m
    return {k: m[k] for k in ("found", "url", "date_range",
                              "engaged_sessions", "avg_engagement_seconds")
            if k in m}


def get_conversion_events(url: str) -> dict:
    """Key events (GA4's conversions) recorded for one page."""
    m = _page_metrics(url)
    if not m.get("has_ga4_data"):
        return m
    return {k: m[k] for k in ("found", "url", "date_range", "key_events")
            if k in m}


def get_all_page_metrics(url: str) -> dict:
    """Every synced GA4 metric for one page."""
    return _page_metrics(url)


def get_top_pages_by_sessions(limit: int = 25) -> list[dict]:
    """Pages with the most sessions in the synced window."""
    return rows(
        """SELECT url, metric_value AS sessions FROM integration_placeholders
           WHERE source = 'ga4' AND metric_name = 'sessions'
             AND status = 'matched'
           ORDER BY CAST(metric_value AS REAL) DESC LIMIT ?""",
        (min(int(limit), 200),))


def get_top_pages_by_key_events(limit: int = 25) -> list[dict]:
    """Pages driving the most key events (conversions) - the money pages."""
    return rows(
        """SELECT url, metric_value AS key_events
           FROM integration_placeholders
           WHERE source = 'ga4' AND metric_name = 'key_events'
             AND status = 'matched'
             AND CAST(metric_value AS REAL) > 0
           ORDER BY CAST(metric_value AS REAL) DESC LIMIT ?""",
        (min(int(limit), 200),))


server = MCPServer(
    name="ken-ga4",
    instructions="Read-only Google Analytics 4 data (synced). Scroll depth, "
                 "link clicks, and lead-source tools are absent because the "
                 "GA4 property has no such custom events yet - not faked.")
for fn in (get_page_sessions, get_page_engagement, get_conversion_events,
           get_all_page_metrics, get_top_pages_by_sessions,
           get_top_pages_by_key_events):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
