"""Repair the four content_nodes rows whose market field is the literal
string "nan Market".

Ken's own source data carries a pandas NaN for these four pages (their LIVE
page titles literally say "nan Market Size..." - already flagged to the web
team), and ingestion recorded the string. It leaked into two recommendation
anchors ("Philippines nan Market") via the anchor builder. This script sets
the market from each page's URL slug; titles are left as-is because they
honestly record what the live site shows today.

Backs up the database first (project safety rule). Idempotent.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

# slug -> correct market (matching the inventory's "<Subject> Market" style)
FIXES = {
    "philippines-ulcerative-colitis-market": "Ulcerative Colitis Market",
    "middle-east-smart-card-materials-market": "Smart Card Materials Market",
    "philippines-apac-micro-led-market": "Micro LED Market",
    "oman-business-process-outsourcing-bpo-market":
        "Business Process Outsourcing Market",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    db_path = Path(args.db)

    conn = sqlite3.connect(db_path)
    broken = conn.execute(
        "SELECT url FROM content_nodes WHERE LOWER(market) IN "
        "('nan', 'nan market')").fetchall()
    if not broken:
        print("No 'nan Market' rows left; nothing to do.")
        conn.close()
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(f"{db_path.stem}_backup_nan_market_{stamp}.db")
    shutil.copy2(db_path, backup)
    print(f"Backup: {backup}")

    fixed = 0
    for slug, market in FIXES.items():
        n = conn.execute(
            "UPDATE content_nodes SET market = ? WHERE url LIKE ? "
            "AND LOWER(market) IN ('nan', 'nan market')",
            (market, f"%{slug}%")).rowcount
        if n:
            print(f"  {slug} -> market '{market}'")
            fixed += n
    conn.commit()
    leftover = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE LOWER(market) IN "
        "('nan', 'nan market')").fetchone()[0]
    conn.close()
    print(f"Fixed {fixed} rows; remaining 'nan Market' rows: {leftover}")
    return 0 if leftover == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
