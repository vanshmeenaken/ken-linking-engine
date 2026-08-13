"""Tests for scripts/36_generate_woven_sentences.py: falls back to the
template when the LLM is unavailable, and only touches the columns it owns."""

import importlib.util
import os
import shutil
import sqlite3
from pathlib import Path

import integrations.nvidia_llm as nvidia_llm

SCRIPT_PATH = (Path(__file__).resolve().parent.parent / "scripts" /
              "36_generate_woven_sentences.py")
spec = importlib.util.spec_from_file_location("generate_woven_sentences", SCRIPT_PATH)
gen_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_mod)


def _unset_all_nvidia_keys(monkeypatch):
    """Remove EVERY NVIDIA key so the run cannot reach the network. Deleting
    only NVIDIA_API_KEY is not enough: api_keys() also reads NVIDIA_API_KEY_2,
    _3, ... which .env defines, and scripts/36 calls load_dotenv() at import,
    so a partial unset would let the test make real API calls."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    i = 2
    while True:
        name = f"NVIDIA_API_KEY_{i}"
        if name not in os.environ:
            break
        monkeypatch.delenv(name, raising=False)
        i += 1


def _scratch_db(tmp_path):
    src = Path(__file__).resolve().parent.parent / "ken_links.db"
    dst = tmp_path / "scratch_ken_links.db"
    shutil.copyfile(src, dst)
    return dst


def test_falls_back_to_template_when_llm_unavailable(tmp_path, monkeypatch):
    _unset_all_nvidia_keys(monkeypatch)  # forces the fallback, no network call
    db = _scratch_db(tmp_path)
    conn = sqlite3.connect(db)
    row = conn.execute(
        """SELECT recommendation_id FROM link_recommendations
           WHERE status != 'rejected' AND placement_type = 'contextual_body'
             AND suggested_sentence IS NOT NULL LIMIT 1"""
    ).fetchone()
    conn.close()
    assert row is not None, "no contextual_body row in the live DB to test against"

    gen_mod.main(["--db", str(db), "--limit", "1", "--workers", "1"])

    conn = sqlite3.connect(db)
    result = conn.execute(
        "SELECT woven_sentence, woven_sentence_source FROM link_recommendations "
        "WHERE recommendation_id = ?", (row[0],)).fetchone()
    conn.close()
    assert result[0]  # a sentence was written
    assert result[1] == "template"


def test_only_touches_woven_sentence_columns(tmp_path, monkeypatch):
    _unset_all_nvidia_keys(monkeypatch)
    db = _scratch_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    before = dict(conn.execute(
        """SELECT recommendation_id, status, approved_by, anchor_text,
                  suggested_sentence, link_score
           FROM link_recommendations WHERE status != 'rejected'
             AND placement_type = 'contextual_body'
             AND suggested_sentence IS NOT NULL LIMIT 1"""
    ).fetchone())
    conn.close()

    gen_mod.main(["--db", str(db), "--limit", "50", "--workers", "1"])

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    after = dict(conn.execute(
        """SELECT recommendation_id, status, approved_by, anchor_text,
                  suggested_sentence, link_score
           FROM link_recommendations WHERE recommendation_id = ?""",
        (before["recommendation_id"],)).fetchone())
    conn.close()
    assert before == after  # nothing but woven_sentence/_source changed
