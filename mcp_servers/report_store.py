"""MCP-11 Report Store Server (master PRD section 11).

Read-only access to report metadata: search, filters, related reports (via
relationship edges and link recommendations).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from mcp_servers._db import find_node_by_url, one, rows

_REPORT_COLS = ("node_id, url, title, market, industry, sub_industry, "
                "country, region, published_date, updated_date, "
                "business_priority, status")


def search_reports(query: str, limit: int = 20) -> list[dict]:
    """Reports matching a text query (title or market)."""
    like = f"%{query}%"
    return rows(
        f"""SELECT {_REPORT_COLS} FROM content_nodes
            WHERE content_type = 'report' AND status = 'active'
              AND (title LIKE ? OR market LIKE ?)
            ORDER BY business_priority DESC LIMIT ?""",
        (like, like, min(int(limit), 200)))


def get_report_by_id(node_id: str) -> dict:
    """Full report record by node_id."""
    return one(
        "SELECT * FROM content_nodes WHERE node_id = ? "
        "AND content_type = 'report'",
        (node_id,)) or {"found": False, "node_id": node_id}


def get_report_metadata(url: str) -> dict:
    """Report metadata by URL."""
    node = find_node_by_url(url)
    if not node or node["content_type"] != "report":
        return {"found": False, "url": url}
    return {k: node[k] for k in
            ("node_id", "url", "title", "market", "industry", "country",
             "region", "published_date", "updated_date",
             "business_priority")}


def list_reports_by_industry(industry: str, limit: int = 50) -> list[dict]:
    """Active reports in one industry."""
    return rows(
        f"""SELECT {_REPORT_COLS} FROM content_nodes
            WHERE content_type = 'report' AND status = 'active'
              AND LOWER(industry) = LOWER(?) LIMIT ?""",
        (industry, min(int(limit), 500)))


def list_reports_by_country(country: str, limit: int = 50) -> list[dict]:
    """Active reports for one country."""
    return rows(
        f"""SELECT {_REPORT_COLS} FROM content_nodes
            WHERE content_type = 'report' AND status = 'active'
              AND LOWER(country) = LOWER(?) LIMIT ?""",
        (country, min(int(limit), 500)))


def list_reports_by_market(market: str, limit: int = 50) -> list[dict]:
    """Active reports covering one market (substring match)."""
    return rows(
        f"""SELECT {_REPORT_COLS} FROM content_nodes
            WHERE content_type = 'report' AND status = 'active'
              AND market LIKE ? LIMIT ?""",
        (f"%{market}%", min(int(limit), 500)))


def get_report_update_date(url: str) -> dict:
    """When a report was published and last updated."""
    node = find_node_by_url(url)
    if not node:
        return {"found": False, "url": url}
    return {"url": node["url"], "published_date": node["published_date"],
            "updated_date": node["updated_date"]}


def get_related_reports(url: str, limit: int = 10) -> list[dict]:
    """Reports related to this one (from the trusted relationship graph)."""
    node = find_node_by_url(url)
    if not node:
        return []
    return rows(
        """SELECT e.relationship_type, e.confidence_score,
                  CASE WHEN e.source_node_id = ? THEN t.url ELSE s.url END
                      AS related_url,
                  CASE WHEN e.source_node_id = ? THEN t.title ELSE s.title END
                      AS related_title
           FROM relationship_edges e
           JOIN content_nodes s ON s.node_id = e.source_node_id
           JOIN content_nodes t ON t.node_id = e.target_node_id
           WHERE (e.source_node_id = ? OR e.target_node_id = ?)
             AND e.source_node_id != e.target_node_id
           ORDER BY e.confidence_score DESC LIMIT ?""",
        (node["node_id"], node["node_id"], node["node_id"], node["node_id"],
         min(int(limit), 100)))


server = MCPServer(
    name="ken-report-store",
    instructions="Read-only report metadata and related-report lookups "
                 "over the 500-page sample inventory.")
for fn in (search_reports, get_report_by_id, get_report_metadata,
           list_reports_by_industry, list_reports_by_country,
           list_reports_by_market, get_report_update_date,
           get_related_reports):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
