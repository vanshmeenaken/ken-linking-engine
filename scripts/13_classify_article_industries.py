"""Classify the 99 'Articles' industry values into the real 14 industries.

'Articles' is a content-type label that leaked into content_nodes.industry
(same bug class as the already-fixed 'Case Studies' issue). Reuses Agent 1's
existing NVIDIA AI industry classifier (the same one used for case study
pages) against each article's title/H1.

Two-step by design (Shrey's direction, 2026-07-09): this script only WRITES
A REVIEW FILE, never the database. A human reviews the CSV, then
scripts/14_apply_article_industries.py (run separately) applies it.

Usage:
    python scripts/13_classify_article_industries.py
"""

import csv
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agent_1_content_inventory import _classify_industry_with_ai

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"


def main() -> int:
    conn = sqlite3.connect(ROOT / "ken_links.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT node_id, url, title, h1 FROM content_nodes WHERE industry='Articles'"
    ).fetchall()
    conn.close()

    print(f"Classifying {len(rows)} article pages via NVIDIA AI classifier...")
    results = []
    for i, row in enumerate(rows, 1):
        title = row["h1"] or row["title"] or ""
        industry = _classify_industry_with_ai([], title=title)
        results.append({
            "node_id": row["node_id"],
            "url": row["url"],
            "title": row["title"],
            "h1": row["h1"],
            "proposed_industry": industry or "(no confident match)",
        })
        print(f"  {i}/{len(rows)}: {row['url'].split('/')[-1][:50]:<50} -> {industry or '???'}")

    REPORT_DIR.mkdir(exist_ok=True)
    out_path = REPORT_DIR / f"article_industry_review_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["node_id", "url", "title", "h1", "proposed_industry"])
        writer.writeheader()
        writer.writerows(results)

    unmatched = sum(1 for r in results if r["proposed_industry"] == "(no confident match)")
    print(f"\nReview file: {out_path}")
    print(f"Classified: {len(results) - unmatched}/{len(results)}")
    print(f"No confident match: {unmatched}")
    print("\nNothing written to the database yet. Review the CSV, then run "
          "scripts/14_apply_article_industries.py to apply it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
