"""Add woven_sentence to link_recommendations.

Stores the natural-language rewrite of each contextual placement's existing
sentence with the anchor woven in (scripts/36_generate_woven_sentences.py
populates it, via the NVIDIA LLM with a deterministic template fallback).
Precomputed and stored rather than generated on every API request - an LLM
call per page load would be slow and needlessly re-spend the API budget on
data that does not change between requests.

Backs up the database first. Additive and idempotent.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"


def migrate(db_path: Path) -> Path | None:
    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(link_recommendations)")}
        if "woven_sentence" in cols and "woven_sentence_source" in cols:
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(
            f"{db_path.stem}_backup_woven_sentence_{stamp}.db")
        shutil.copy2(db_path, backup)
        if "woven_sentence" not in cols:
            conn.execute(
                "ALTER TABLE link_recommendations ADD COLUMN woven_sentence TEXT")
        if "woven_sentence_source" not in cols:
            # 'llm' or 'template' - which path produced the stored rewrite,
            # so a later re-run can target only template fallbacks for retry
            conn.execute(
                "ALTER TABLE link_recommendations "
                "ADD COLUMN woven_sentence_source TEXT")
        conn.commit()
        return backup
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    backup = migrate(Path(args.db))
    if backup:
        print(f"Backup: {backup}")
        print("Added: link_recommendations.woven_sentence, "
              "link_recommendations.woven_sentence_source")
    else:
        print("Schema already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
