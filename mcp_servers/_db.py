"""Shared read-only database access for the MCP servers.

Every server opens ken_links.db in SQLite read-only mode (mode=ro), so no
MCP tool can modify state by accident - the PRD's hard rule (section 26: no
write/publish without human approval) is enforced at the connection level,
not by convention. The one PRD-specified exception (Evidence Library's two
internal-DB tools) opens its own writable connection explicitly and touches
only paragraph_evidence_map.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "ken_links.db"


def connect_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows(query: str, params: tuple = ()) -> list[dict]:
    conn = connect_ro()
    try:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def one(query: str, params: tuple = ()) -> dict | None:
    conn = connect_ro()
    try:
        r = conn.execute(query, params).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def normalise_url(url: str) -> str:
    """Match a caller-supplied URL against stored URLs forgivingly:
    scheme/trailing-slash insensitive."""
    u = (url or "").strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u


def find_node_by_url(url: str) -> dict | None:
    """Look up a content node by URL, tolerant of scheme and trailing slash."""
    u = normalise_url(url)
    return one(
        """SELECT * FROM content_nodes
           WHERE REPLACE(REPLACE(RTRIM(url, '/'), 'https://', ''),
                         'http://', '') = ?""", (u,))
