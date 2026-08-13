"""MCP-4 Evidence Library Server (master PRD section 11).

Connects paragraphs to research proof, backed by Agent 8's
paragraph_evidence_map. Two PRD-specified tools write INTERNAL DB state only
(map_paragraph_to_evidence, flag_unsupported_claim) - they annotate the
evidence map, never the live site.
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from mcp_servers._db import DB_PATH, one, rows


def search_evidence(query: str, limit: int = 10) -> list[dict]:
    """Evidence-bearing paragraphs matching a text query."""
    like = f"%{query}%"
    return rows(
        """SELECT evidence_row_id, url, section_heading, paragraph_text,
                  support_status, evidence_target_url, evidence_score
           FROM paragraph_evidence_map
           WHERE paragraph_text LIKE ? AND classification = 'market_claim'
           LIMIT ?""", (like, min(int(limit), 100)))


def get_evidence_by_id(evidence_id: str) -> dict:
    """One evidence-map row by its id."""
    return one("SELECT * FROM paragraph_evidence_map WHERE evidence_row_id = ?",
               (evidence_id,)) or {"found": False, "evidence_id": evidence_id}


def search_case_studies(query: str, limit: int = 10) -> list[dict]:
    """Case-study pages matching a text query."""
    like = f"%{query}%"
    return rows(
        """SELECT node_id, url, title, market, country FROM content_nodes
           WHERE content_type = 'case_study' AND status = 'active'
             AND (title LIKE ? OR market LIKE ?) LIMIT ?""",
        (like, like, min(int(limit), 100)))


def search_charts(query: str, limit: int = 10) -> list[dict]:
    """Sections whose pages carry charts/images, matching a query.
    (Chart-level indexing does not exist yet; section-level image counts
    from the crawler are the honest granularity available.)"""
    like = f"%{query}%"
    return rows(
        """SELECT node_id, url, heading, image_count FROM section_purpose_map
           WHERE image_count > 0 AND (heading LIKE ? OR url LIKE ?)
           LIMIT ?""", (like, like, min(int(limit), 100)))


def search_tables(query: str, limit: int = 10) -> list[dict]:
    """Sections whose pages carry data tables, matching a query."""
    like = f"%{query}%"
    return rows(
        """SELECT node_id, url, heading, table_count FROM section_purpose_map
           WHERE table_count > 0 AND (heading LIKE ? OR url LIKE ?)
           LIMIT ?""", (like, like, min(int(limit), 100)))


def get_evidence_confidence_score(evidence_id: str) -> dict:
    """The similarity score behind one evidence attachment."""
    row = one(
        """SELECT evidence_row_id, evidence_score, evidence_target_url,
                  support_status FROM paragraph_evidence_map
           WHERE evidence_row_id = ?""", (evidence_id,))
    return row or {"found": False, "evidence_id": evidence_id}


def map_paragraph_to_evidence(evidence_row_id: str, target_node_id: str,
                              reason: str = "") -> dict:
    """Manually attach an evidence page to a paragraph (internal DB only).

    This annotates paragraph_evidence_map - it does NOT create a link
    recommendation and touches nothing on the live site.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        target = conn.execute(
            "SELECT node_id, url, content_type FROM content_nodes "
            "WHERE node_id = ?", (target_node_id,)).fetchone()
        if target is None:
            return {"updated": False, "error": f"unknown node {target_node_id}"}
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        n = conn.execute(
            """UPDATE paragraph_evidence_map
               SET evidence_target_node_id = ?, evidence_target_url = ?,
                   evidence_type = ?, updated_at = ?
               WHERE evidence_row_id = ?""",
            (target["node_id"], target["url"], target["content_type"],
             now, evidence_row_id)).rowcount
        conn.commit()
        return {"updated": n == 1, "evidence_row_id": evidence_row_id,
                "evidence_target_url": target["url"], "note": reason}
    finally:
        conn.close()


def flag_unsupported_claim(evidence_row_id: str, reason: str) -> dict:
    """Flag a claim as needing evidence (internal DB only): sets its
    support_status to 'unsupported' and records why."""
    conn = sqlite3.connect(DB_PATH)
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        n = conn.execute(
            """UPDATE paragraph_evidence_map
               SET support_status = 'unsupported', updated_at = ?
               WHERE evidence_row_id = ? AND classification = 'market_claim'""",
            (now, evidence_row_id)).rowcount
        conn.commit()
        return {"flagged": n == 1, "evidence_row_id": evidence_row_id,
                "reason": reason}
    finally:
        conn.close()


server = MCPServer(
    name="ken-evidence-library",
    instructions="Paragraph-to-evidence mapping (Agent 8). Two tools write "
                 "internal annotations to paragraph_evidence_map; nothing "
                 "touches the live site.")
for fn in (search_evidence, get_evidence_by_id, search_case_studies,
           search_charts, search_tables, get_evidence_confidence_score,
           map_paragraph_to_evidence, flag_unsupported_claim):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
