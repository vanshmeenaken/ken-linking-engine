"""Tests for scripts/24_export_approved_links.py: the manual deployment
export (master PRD MVP capability, section 17) that turns editorially-
approved recommendations into a CSV for the web team, since there is no
live CMS write access. Runs against a throwaway copy of the real DB so it
never mutates the actual review queue."""

import importlib.util
import shutil
import sqlite3
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "24_export_approved_links.py"
spec = importlib.util.spec_from_file_location("export_approved_links_script", SCRIPT_PATH)
export_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_mod)


def _scratch_db(tmp_path):
    src = Path(__file__).resolve().parent.parent / "ken_links.db"
    dst = tmp_path / "scratch_ken_links.db"
    shutil.copyfile(src, dst)
    return dst


def _reset_recommendations(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE link_recommendations SET status='pending', approved_by=NULL")
    conn.commit()
    conn.close()


def test_no_approved_recommendations_writes_header_only(tmp_path):
    db = _scratch_db(tmp_path)
    _reset_recommendations(db)
    out = tmp_path / "export.csv"
    count = export_mod.export_approved_links(str(db), out)
    assert count == 0
    assert out.read_text(encoding="utf-8").strip() == ",".join(export_mod.COLUMNS)


def test_approved_recommendations_are_exported(tmp_path):
    db = _scratch_db(tmp_path)
    _reset_recommendations(db)
    conn = sqlite3.connect(db)
    ids = [r[0] for r in conn.execute(
        "SELECT recommendation_id FROM link_recommendations LIMIT 2").fetchall()]
    conn.executemany(
        "UPDATE link_recommendations SET status='approved', approved_by='test' "
        "WHERE recommendation_id = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()

    out = tmp_path / "export.csv"
    count = export_mod.export_approved_links(str(db), out)
    assert count == 2

    import csv
    with out.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert {r["recommendation_id"] for r in rows} == set(ids)
    for r in rows:
        assert r["source_url"] and r["target_url"] and r["anchor_text"]
        assert r["recommendation_reason"]
        assert r["editorial_note"]
        assert r["approved_by"] == "test"


def test_rejected_and_pending_are_not_exported(tmp_path):
    db = _scratch_db(tmp_path)
    _reset_recommendations(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE link_recommendations SET status='rejected' "
        "WHERE recommendation_id = (SELECT recommendation_id FROM link_recommendations LIMIT 1)")
    conn.commit()
    conn.close()

    out = tmp_path / "export.csv"
    count = export_mod.export_approved_links(str(db), out)
    assert count == 0  # rejected and pending links are not approved for handover
