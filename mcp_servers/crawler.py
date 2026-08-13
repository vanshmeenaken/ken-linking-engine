"""MCP-6 Crawler Server (master PRD section 11).

Crawl-health queries over crawl_logs and content_nodes, plus a live
section-aware crawl of a single page (read-only fetch, nothing stored).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from mcp_servers._db import find_node_by_url, rows


def crawl_url(url: str) -> dict:
    """Live-fetch one page and return its real section structure
    (headings, paragraph counts, link/table/image counts). Read-only;
    nothing is stored."""
    from analysis.contextual_placement import fetch_sections
    try:
        sections = fetch_sections(url)
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}
    return {"ok": True, "url": url, "section_count": len(sections),
            "sections": [{
                "heading": s["heading"],
                "paragraphs": len(s["paragraphs"]),
                "internal_links": s["internal_link_count"],
                "tables": s["table_count"], "images": s["image_count"],
            } for s in sections]}


def crawl_section(url: str, section_heading: str) -> dict:
    """Live-fetch one page and return the full text of one section."""
    from analysis.contextual_placement import fetch_sections
    try:
        sections = fetch_sections(url)
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}
    wanted = (section_heading or "").strip().lower()
    for s in sections:
        if (s["heading"] or "").strip().lower() == wanted:
            return {"ok": True, "heading": s["heading"],
                    "paragraphs": s["paragraphs"],
                    "internal_links": s["internal_link_count"]}
    return {"ok": False, "url": url,
            "error": f'no section titled "{section_heading}"',
            "available": [s["heading"] for s in sections if s["heading"]]}


def get_crawl_errors(limit: int = 50) -> list[dict]:
    """Recent crawl failures from the crawl log."""
    return rows(
        """SELECT url, operation, status, http_status, error, crawled_at
           FROM crawl_logs WHERE status != 'success'
           ORDER BY crawled_at DESC LIMIT ?""", (min(int(limit), 500),))


def get_redirect_chains(limit: int = 50) -> list[dict]:
    """Pages whose stored state says they redirect or were removed."""
    return rows(
        """SELECT url, canonical_url, indexability_status, status
           FROM content_nodes
           WHERE indexability_status = 'redirected_removed'
              OR status = 'removed' LIMIT ?""", (min(int(limit), 500),))


def get_non_canonical_internal_links(limit: int = 50) -> list[dict]:
    """Pages whose URL differs from their canonical (link targets to avoid)."""
    return rows(
        """SELECT url, canonical_url FROM content_nodes
           WHERE canonical_url IS NOT NULL AND canonical_url != ''
             AND RTRIM(url, '/') != RTRIM(canonical_url, '/')
           LIMIT ?""", (min(int(limit), 500),))


def get_pages_deeper_than_depth(depth: int = 3, limit: int = 50) -> list[dict]:
    """Pages buried deeper than N clicks from the home page."""
    return rows(
        """SELECT url, title, crawl_depth FROM content_nodes
           WHERE crawl_depth > ? AND status = 'active'
           ORDER BY crawl_depth DESC LIMIT ?""",
        (int(depth), min(int(limit), 500)))


def get_pages_with_excessive_links(limit: int = 25) -> list[dict]:
    """Active pages with the most outgoing internal links (over-linking
    risk; report maximum is 25)."""
    return rows(
        """SELECT url, title, content_type, internal_links_out
           FROM content_nodes WHERE status = 'active'
           ORDER BY internal_links_out DESC LIMIT ?""",
        (min(int(limit), 200),))


def get_blocked_urls(limit: int = 50) -> list[dict]:
    """Pages that are not indexable (noindex / blocked / removed)."""
    return rows(
        """SELECT url, title, indexability_status, status FROM content_nodes
           WHERE indexability_status != 'indexable' LIMIT ?""",
        (min(int(limit), 500),))


def get_page_crawl_history(url: str, limit: int = 20) -> list[dict]:
    """Crawl-log entries for one page."""
    node = find_node_by_url(url)
    return rows(
        """SELECT operation, status, http_status, error, crawled_at
           FROM crawl_logs WHERE url = ? OR node_id = ?
           ORDER BY crawled_at DESC LIMIT ?""",
        (url, node["node_id"] if node else "", min(int(limit), 200)))


server = MCPServer(
    name="ken-crawler",
    instructions="Crawl-health queries and read-only live page fetches. "
                 "Nothing is stored or modified.")
for fn in (crawl_url, crawl_section, get_crawl_errors, get_redirect_chains,
           get_non_canonical_internal_links, get_pages_deeper_than_depth,
           get_pages_with_excessive_links, get_blocked_urls,
           get_page_crawl_history):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
