"""Tests for Agent 5 Business Priority (Phase 2, Day 3)."""

import runpy
import sqlite3
import sys
from pathlib import Path

from agents.agent_5_business_priority import (
    COUNTRY_PRIORITY,
    INDUSTRY_PRIORITY,
    WEIGHTS,
    band,
)

SCRIPT = Path(__file__).resolve().parents[1] / "agents" / "agent_5_business_priority.py"


def _make_db(tmp_path, nodes):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE content_nodes (
            node_id TEXT PRIMARY KEY, url TEXT, industry TEXT, country TEXT,
            intent_stage TEXT, page_authority_score REAL,
            search_opportunity_score REAL, business_priority TEXT,
            status TEXT DEFAULT 'active', updated_at TEXT)
    """)
    for n in nodes:
        conn.execute(
            "INSERT INTO content_nodes (node_id, url, industry, country, "
            "intent_stage, page_authority_score, status) VALUES (?,?,?,?,?,?,?)",
            (n["node_id"], f"https://x/{n['node_id']}", n.get("industry", ""),
             n.get("country", ""), n.get("intent_stage", "decision"),
             n.get("page_authority_score", 20.0), n.get("status", "active")),
        )
    conn.commit()
    conn.close()
    return path


def _run(db_path):
    argv = sys.argv
    sys.argv = ["agent_5_business_priority.py", "--db", str(db_path)]
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit:
        pass
    finally:
        sys.argv = argv


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_band_thresholds():
    assert band(0.7) == "High"
    assert band(0.5) == "Medium"
    assert band(0.3) == "Low"


def test_high_priority_commercial_page_in_mvp_scope(tmp_path):
    # decision intent + MVP industry + MVP country + high authority -> High
    db = _make_db(tmp_path, [
        {"node_id": "n1", "industry": "Healthcare", "country": "india",
         "intent_stage": "decision", "page_authority_score": 90.0},
    ])
    _run(db)
    conn = sqlite3.connect(db)
    assert conn.execute(
        "SELECT business_priority FROM content_nodes WHERE node_id='n1'"
    ).fetchone()[0] == "High"
    conn.close()


def test_low_priority_awareness_page_outside_mvp_scope(tmp_path):
    # awareness article + non-MVP industry + non-MVP country + low authority -> Low
    db = _make_db(tmp_path, [
        {"node_id": "n1", "industry": "Media & Entertainment", "country": "kenya",
         "intent_stage": "awareness", "page_authority_score": 0.0},
    ])
    _run(db)
    conn = sqlite3.connect(db)
    assert conn.execute(
        "SELECT business_priority FROM content_nodes WHERE node_id='n1'"
    ).fetchone()[0] == "Low"
    conn.close()


def test_all_active_pages_get_a_band(tmp_path):
    db = _make_db(tmp_path, [
        {"node_id": f"n{i}", "intent_stage": "consideration"} for i in range(5)
    ])
    _run(db)
    conn = sqlite3.connect(db)
    filled = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE business_priority IN ('High','Medium','Low')"
    ).fetchone()[0]
    conn.close()
    assert filled == 5


def test_mvp_scope_config_present():
    # The MVP-scope industries/countries (master PRD §31.2) are weighted up
    for ind in ("Healthcare", "Automotive, Transportation & Logistics", "Technology & Telecom"):
        assert INDUSTRY_PRIORITY[ind] == 1.0
    for c in ("india", "saudi arabia", "uae"):
        assert COUNTRY_PRIORITY[c] == 1.0
