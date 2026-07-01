import sqlite3
import requests
from bs4 import BeautifulSoup
from agents.agent_1_content_inventory import extract_industry_from_related_tags, _classify_industry_with_ai

# Get 3 empty case study URLs from DB
conn = sqlite3.connect("ken_links.db")
rows = conn.execute(
    "SELECT url, h1, title FROM content_nodes "
    "WHERE content_type='case_study' AND (industry IS NULL OR industry='') LIMIT 3"
).fetchall()
conn.close()

print(f"Found {len(rows)} empty case studies\n")

for url, h1, title in rows:
    print(f"URL: {url}")
    print(f"H1:  {h1}")
    print(f"Title: {title}")
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        industry = extract_industry_from_related_tags(soup, title=h1 or title)
        print(f"Industry extracted: '{industry}'")
    except Exception as e:
        print(f"Error: {e}")
    print()
