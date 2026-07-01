"""Fix blank industry fields for case study rows by re-classifying with AI."""
import sys
import sqlite3
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()

from agents.agent_1_content_inventory import (
    extract_industry_from_related_tags,
    _classify_industry_with_ai,
)

DB_PATH = Path(__file__).resolve().parents[1] / "ken_links.db"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT node_id, url, h1, title FROM content_nodes "
    "WHERE content_type='case_study' AND (industry IS NULL OR industry='') "
    "ORDER BY node_id"
).fetchall()
print(f"Found {len(rows)} blank case study rows\n")

updated = 0
for node_id, url, h1, title in rows:
    print(f"  [{node_id}] {url}")
    industry = ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        industry = extract_industry_from_related_tags(soup, title=h1 or title)
    except Exception as e:
        print(f"    Crawl error: {e}")
        # Fall back to title-only AI if crawl fails
        if h1 or title:
            industry = _classify_industry_with_ai([], title=h1 or title)

    if industry:
        conn.execute(
            "UPDATE content_nodes SET industry=?, updated_at=? WHERE node_id=?",
            (industry, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), node_id),
        )
        conn.commit()
        updated += 1
        print(f"    -> '{industry}'")
    else:
        print(f"    -> (still blank — no tags, title too generic for AI)")

print(f"\nDone. Updated {updated}/{len(rows)} rows.")
conn.close()
