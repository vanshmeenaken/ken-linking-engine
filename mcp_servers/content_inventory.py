"""MCP-1 Content Inventory Server (master PRD section 11).

Structured read-only access to the page inventory (content_nodes). Tool
names match the PRD spec exactly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from mcp_servers._db import find_node_by_url, one, rows

_PAGE_COLS = ("node_id, url, canonical_url, title, content_type, industry, "
              "market, country, region, status, indexability_status, "
              "internal_links_in, internal_links_out, orphan_status, "
              "business_priority, published_date, updated_date")


def get_page_by_url(url: str) -> dict:
    """Full page record for one URL (scheme/trailing-slash tolerant)."""
    return find_node_by_url(url) or {"found": False, "url": url}


def get_page_by_id(node_id: str) -> dict:
    """Full page record for one node_id."""
    return one("SELECT * FROM content_nodes WHERE node_id = ?",
               (node_id,)) or {"found": False, "node_id": node_id}


def search_pages(query: str, limit: int = 20) -> list[dict]:
    """Search pages by title, URL, or market (case-insensitive substring)."""
    like = f"%{query}%"
    return rows(
        f"""SELECT {_PAGE_COLS} FROM content_nodes
            WHERE title LIKE ? OR url LIKE ? OR market LIKE ?
            ORDER BY business_priority DESC LIMIT ?""",
        (like, like, like, min(int(limit), 200)))


def list_pages_by_industry(industry: str, limit: int = 50) -> list[dict]:
    """Active pages in one industry."""
    return rows(
        f"""SELECT {_PAGE_COLS} FROM content_nodes
            WHERE LOWER(industry) = LOWER(?) AND status='active'
            LIMIT ?""", (industry, min(int(limit), 500)))


def list_pages_by_country(country: str, limit: int = 50) -> list[dict]:
    """Active pages for one country."""
    return rows(
        f"""SELECT {_PAGE_COLS} FROM content_nodes
            WHERE LOWER(country) = LOWER(?) AND status='active'
            LIMIT ?""", (country, min(int(limit), 500)))


def list_pages_by_market(market: str, limit: int = 50) -> list[dict]:
    """Active pages covering one market (substring match)."""
    return rows(
        f"""SELECT {_PAGE_COLS} FROM content_nodes
            WHERE market LIKE ? AND status='active' LIMIT ?""",
        (f"%{market}%", min(int(limit), 500)))


def list_pages_by_node_type(content_type: str, limit: int = 50) -> list[dict]:
    """Active pages of one content type (report, article, case_study)."""
    return rows(
        f"""SELECT {_PAGE_COLS} FROM content_nodes
            WHERE LOWER(content_type) = LOWER(?) AND status='active'
            LIMIT ?""", (content_type, min(int(limit), 500)))


def get_canonical_url(url: str) -> dict:
    """The canonical URL for a page, and whether it differs from the URL."""
    node = find_node_by_url(url)
    if not node:
        return {"found": False, "url": url}
    return {"url": node["url"], "canonical_url": node["canonical_url"],
            "is_canonical": node["url"] == node["canonical_url"]}


def get_page_status(url: str) -> dict:
    """Status, indexability, and link health for one page."""
    node = find_node_by_url(url)
    if not node:
        return {"found": False, "url": url}
    return {k: node[k] for k in
            ("url", "status", "indexability_status", "orphan_status",
             "internal_links_in", "internal_links_out", "crawl_depth")}


def get_internal_links_in(url: str) -> dict:
    """How many internal links point TO this page (plus who recommends to)."""
    node = find_node_by_url(url)
    if not node:
        return {"found": False, "url": url}
    recommended = rows(
        """SELECT source_url, anchor_text, status FROM link_recommendations
           WHERE target_node_id = ?""", (node["node_id"],))
    return {"url": node["url"], "internal_links_in": node["internal_links_in"],
            "recommended_inbound": recommended}


def get_internal_links_out(url: str) -> dict:
    """How many internal links this page sends OUT (plus recommendations)."""
    node = find_node_by_url(url)
    if not node:
        return {"found": False, "url": url}
    recommended = rows(
        """SELECT target_url, anchor_text, status FROM link_recommendations
           WHERE source_node_id = ?""", (node["node_id"],))
    return {"url": node["url"], "internal_links_out": node["internal_links_out"],
            "recommended_outbound": recommended}


def get_orphan_pages(limit: int = 50) -> list[dict]:
    """Active pages no other page links to."""
    return rows(
        f"""SELECT {_PAGE_COLS} FROM content_nodes
            WHERE orphan_status = 'orphan' AND status = 'active'
            LIMIT ?""", (min(int(limit), 500),))


def get_recently_published_pages(limit: int = 20) -> list[dict]:
    """Most recently published active pages."""
    return rows(
        f"""SELECT {_PAGE_COLS} FROM content_nodes
            WHERE status='active' AND published_date IS NOT NULL
            ORDER BY published_date DESC LIMIT ?""",
        (min(int(limit), 200),))


server = MCPServer(
    name="ken-content-inventory",
    instructions="Read-only access to Ken Research's page inventory "
                 "(500-page sample). No tool can modify anything.")
for fn in (get_page_by_url, get_page_by_id, search_pages,
           list_pages_by_industry, list_pages_by_country,
           list_pages_by_market, list_pages_by_node_type, get_canonical_url,
           get_page_status, get_internal_links_in, get_internal_links_out,
           get_orphan_pages, get_recently_published_pages):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
