"""Add the manual-interlinking workbench tables.

sitemap_urls caches Ken's public sitemap (the index at /sitemap.xml plus its
child sitemaps) so the workbench can suggest related pages that are NOT in
the 500-page local inventory - the whole point of the sitemap fallback.

manual_link_plans stores what a human decides in the workbench: which page
links to which, with what anchor, in which section/paragraph, plus their own
note. It is deliberately SEPARATE from link_recommendations: those are
machine-generated suggestions awaiting review, these are human-authored
instructions. Mixing them would make it impossible to tell which decisions
the machine proposed and which a person wrote by hand.

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

SITEMAP_TABLE = """
CREATE TABLE IF NOT EXISTS sitemap_urls (
    url TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    content_type TEXT,
    sitemap_source TEXT,
    lastmod TEXT,
    fetched_at TEXT
)
"""

MANUAL_TABLE = """
CREATE TABLE IF NOT EXISTS manual_link_plans (
    plan_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    anchor_text TEXT NOT NULL,
    section_heading TEXT,
    paragraph_index INTEGER,
    paragraph_excerpt TEXT,
    placement_note TEXT,
    relation_label TEXT,
    found_via TEXT,
    created_by TEXT,
    status TEXT DEFAULT 'planned',
    created_at TEXT,
    updated_at TEXT
)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_sitemap_urls_slug ON sitemap_urls(slug)",
    "CREATE INDEX IF NOT EXISTS ix_sitemap_urls_type ON sitemap_urls(content_type)",
    "CREATE INDEX IF NOT EXISTS ix_manual_plans_source "
    "ON manual_link_plans(source_url)",
]


def migrate(db_path: Path) -> tuple[Path | None, list[str]]:
    conn = sqlite3.connect(db_path)
    changes: list[str] = []
    try:
        existing = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        needed = [n for n in ("sitemap_urls", "manual_link_plans")
                  if n not in existing]
        if not needed:
            for stmt in INDEXES:
                conn.execute(stmt)
            conn.commit()
            return None, []

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(
            f"{db_path.stem}_backup_manual_linking_{stamp}.db")
        shutil.copy2(db_path, backup)

        if "sitemap_urls" in needed:
            conn.execute(SITEMAP_TABLE)
            changes.append("sitemap_urls")
        if "manual_link_plans" in needed:
            conn.execute(MANUAL_TABLE)
            changes.append("manual_link_plans")
        for stmt in INDEXES:
            conn.execute(stmt)
        conn.commit()
        return backup, changes
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    backup, changes = migrate(Path(args.db))
    if changes:
        print(f"Backup: {backup}")
        print("Added: " + ", ".join(changes))
    else:
        print("Schema already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
