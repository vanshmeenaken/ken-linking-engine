"""
Module 2.3 — URL Loading into Database
Ken Intelligence Linking Engine

Loads URLs from a CSV (columns: url, title, content_type, industry, country)
into content_nodes. Generates a UUID node_id per row, normalizes URLs, and
de-duplicates (url is UNIQUE -> existing rows are skipped). Logs the operation
to crawl_logs. Safe to re-run.

Run:   python scripts/02_load_urls.py scripts/sample_urls.csv
"""

import csv
import os
import sqlite3
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "ken_links.db")
DEFAULT_CSV = os.path.join(ROOT, "scripts", "sample_urls.csv")


def normalize_url(u):
    """Drop query/fragment, strip trailing slash, lowercase host."""
    s = urlsplit((u or "").strip())
    path = s.path.rstrip("/") or "/"
    return urlunsplit((s.scheme, s.netloc.lower(), path, "", ""))


def global_or_local(country):
    """Classify a country string as 'global' (region/global-level) or 'local'
    (a specific country), or '' if country is blank."""
    c = (country or "").strip().lower()
    region_like = {"global", "apac", "asia pacific", "europe", "north america",
                   "latin america", "middle east", "mea", "mena", "gcc", "africa"}
    if not c:
        return ""
    return "global" if c in region_like else "local"


def main():
    """Load URLs from a CSV into content_nodes, skipping duplicates and bad
    rows. Exits with an error if the CSV or database file doesn't exist, or
    if the load leaves any duplicate URLs behind."""
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"DB not found: {DB_PATH} (run scripts/01_setup_db.py first)")

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"read {len(rows)} rows from {csv_path}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    before = cur.execute("SELECT COUNT(*) FROM content_nodes").fetchone()[0]
    inserted = skipped_dupe = skipped_bad = 0
    seen_in_file = set()

    for r in rows:
        url = normalize_url(r.get("url", ""))
        if not url or url == "/":
            skipped_bad += 1
            continue
        if url in seen_in_file:
            skipped_dupe += 1
            continue
        seen_in_file.add(url)

        node_id = str(uuid.uuid4())
        country = (r.get("country") or "").strip().lower()
        cur.execute(
            "INSERT OR IGNORE INTO content_nodes "
            "(node_id, url, canonical_url, title, content_type, industry, "
            " country, global_or_local, status) "
            "VALUES (?,?,?,?,?,?,?,?, 'active')",
            (node_id, url, url, (r.get("title") or "").strip(),
             (r.get("content_type") or "").strip().lower(),
             (r.get("industry") or "").strip().lower(),
             country, global_or_local(country)),
        )
        if cur.rowcount == 1:
            inserted += 1
            cur.execute(
                "INSERT INTO crawl_logs (url, node_id, operation, status, notes) "
                "VALUES (?,?, 'load', 'success', ?)",
                (url, node_id, f"loaded from {os.path.basename(csv_path)}"),
            )
        else:
            skipped_dupe += 1   # already in DB

    conn.commit()

    # ---- verify ----
    after = cur.execute("SELECT COUNT(*) FROM content_nodes").fetchone()[0]
    dupes = cur.execute(
        "SELECT url, COUNT(*) c FROM content_nodes GROUP BY url HAVING c > 1"
    ).fetchall()

    print(f"inserted       : {inserted}")
    print(f"skipped (dupe) : {skipped_dupe}")
    print(f"skipped (bad)  : {skipped_bad}")
    print(f"content_nodes  : {before} -> {after}")
    print(f"duplicate urls : {len(dupes)}")
    print("\nsample rows:")
    for row in cur.execute(
        "SELECT url, title, content_type, industry, country FROM content_nodes LIMIT 5"
    ):
        print(f"  {row[0]} | {(row[1] or '')[:38]} | {row[2]} | {row[3]} | {row[4]}")

    conn.close()
    if dupes:
        print("\nWARNING: duplicate URLs found in DB")
        raise SystemExit(1)
    print(f"\nOK - {after} URLs in content_nodes, no duplicates.")


if __name__ == "__main__":
    main()
