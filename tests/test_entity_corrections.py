"""Tests for the Day 4 correction toolkit (scripts/10_entity_corrections.py)."""

import runpy
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.taxonomy import normalize_market_name

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "10_entity_corrections.py"


@pytest.fixture()
def db(tmp_path):
    """Minimal Phase 2 schema with two duplicate market entities."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE content_nodes (node_id TEXT PRIMARY KEY, url TEXT);
        CREATE TABLE content_entities (
            entity_id TEXT PRIMARY KEY, entity_name TEXT, entity_type TEXT,
            normalized_name TEXT, aliases TEXT, industry TEXT, country TEXT,
            region TEXT, confidence_score REAL, created_at TEXT, updated_at TEXT);
        CREATE TABLE node_entities (
            node_entity_id TEXT PRIMARY KEY, node_id TEXT, entity_id TEXT,
            entity_role TEXT, source_field TEXT, extracted_value TEXT,
            normalized_value TEXT, confidence_score REAL, extraction_method TEXT,
            status TEXT DEFAULT 'extracted', created_at TEXT, updated_at TEXT,
            UNIQUE (node_id, entity_id, entity_role));
        CREATE TABLE entity_extraction_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, node_id TEXT,
            operation TEXT, status TEXT, entities_found INTEGER,
            low_confidence_count INTEGER, error TEXT, notes TEXT, created_at TEXT);
    """)
    conn.execute("INSERT INTO content_nodes VALUES ('n1','https://x/one')")
    conn.execute("INSERT INTO content_nodes VALUES ('n2','https://x/two')")
    # Duplicate pair: plural + singular
    conn.execute(
        "INSERT INTO content_entities VALUES "
        "('e-plural','Power Tools Market','market','power tools market','','','','',0.9,'','')")
    conn.execute(
        "INSERT INTO content_entities VALUES "
        "('e-singular','Power Tool Market','market','power tool market','','','','',0.75,'','')")
    conn.execute(
        "INSERT INTO node_entities VALUES "
        "('m1','n1','e-plural','primary_market','title','raw one','power tools market',"
        "0.9,'pattern','extracted','','')")
    conn.execute(
        "INSERT INTO node_entities VALUES "
        "('m2','n2','e-singular','primary_market','title','raw two','power tool market',"
        "0.6,'pattern','extracted','','')")
    conn.commit()
    conn.close()
    return path


def _run(db_path, *args):
    """Invoke the correction script as a CLI (its filename is not importable)."""
    argv_backup = sys.argv
    sys.argv = ["10_entity_corrections.py", "--db", str(db_path), *args]
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as exc:
        return exc.code or 0
    finally:
        sys.argv = argv_backup
    return 0


def test_dedup_key_folds_plurals():
    assert normalize_market_name("Power Tools Market") == normalize_market_name("Power Tool Market")
    assert normalize_market_name("Pharmaceuticals Market") == normalize_market_name("Pharmaceutical Market")
    # Guards: short words and -ss/-us/-is endings unchanged
    assert normalize_market_name("Gas Market") == "gas market"
    assert normalize_market_name("Glass Market") == "glass market"
    assert normalize_market_name("Failure Analysis Market") == "failure analysis market"


def test_merge_duplicates_dry_run_changes_nothing(db):
    assert _run(db, "merge-duplicates") == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM content_entities").fetchone()[0] == 2
    conn.close()


def test_merge_duplicates_apply(db):
    assert _run(db, "merge-duplicates", "--apply") == 0
    conn = sqlite3.connect(db)
    # One entity remains — the one with more pages (tie -> first), mappings repointed
    assert conn.execute("SELECT COUNT(*) FROM content_entities").fetchone()[0] == 1
    remaining = conn.execute("SELECT entity_id FROM content_entities").fetchone()[0]
    ids = {r[0] for r in conn.execute("SELECT entity_id FROM node_entities")}
    assert ids == {remaining}
    # Merge is logged
    assert conn.execute(
        "SELECT COUNT(*) FROM entity_extraction_logs WHERE operation='merge_duplicate'"
    ).fetchone()[0] == 1
    conn.close()


def test_reject_preserves_original(db):
    assert _run(db, "reject", "--id", "m1", "--notes", "wrong market") == 0
    conn = sqlite3.connect(db)
    status, extracted = conn.execute(
        "SELECT status, extracted_value FROM node_entities WHERE node_entity_id='m1'"
    ).fetchone()
    assert status == "rejected"
    assert extracted == "raw one"  # original untouched
    conn.close()


def test_correct_stores_value_keeps_original_and_remaps_entity(db):
    assert _run(db, "correct", "--id", "m2", "--value", "Hand Tools Market") == 0
    conn = sqlite3.connect(db)
    status, extracted, normalized, entity_id = conn.execute(
        "SELECT status, extracted_value, normalized_value, entity_id "
        "FROM node_entities WHERE node_entity_id='m2'"
    ).fetchone()
    assert status == "corrected"
    assert extracted == "raw two"
    assert normalized == "Hand Tools Market"
    # Review finding fix: mapping must point at the corrected entity so API
    # joins show the right name — not stay on the old wrong entity
    assert entity_id not in ("e-plural", "e-singular")
    name, key = conn.execute(
        "SELECT entity_name, normalized_name FROM content_entities WHERE entity_id=?",
        (entity_id,),
    ).fetchone()
    assert name == "Hand Tools Market"
    assert key == "hand tool market"  # depluralized dedup key
    conn.close()


def test_correct_to_existing_entity_reuses_it(db):
    # Correcting to a value whose entity already exists must reuse that
    # entity, not create a duplicate
    assert _run(db, "correct", "--id", "m2", "--value", "Power Tools Market") == 0
    conn = sqlite3.connect(db)
    entity_id = conn.execute(
        "SELECT entity_id FROM node_entities WHERE node_entity_id='m2'"
    ).fetchone()[0]
    # Reused the entity whose stored dedup key matches ('power tool market'
    # — the fixture's e-singular); crucially, no third entity was created
    assert entity_id == "e-singular"
    assert conn.execute("SELECT COUNT(*) FROM content_entities").fetchone()[0] == 2
    conn.close()


def test_approve(db):
    assert _run(db, "approve", "--id", "m1") == 0
    conn = sqlite3.connect(db)
    assert conn.execute(
        "SELECT status FROM node_entities WHERE node_entity_id='m1'"
    ).fetchone()[0] == "approved"
    conn.close()
