"""Apply the reviewed article-industry classifications to content_nodes.

Reads the review CSV produced by scripts/13_classify_article_industries.py,
applies each proposed_industry to content_nodes.industry. Rows marked
'(no confident match)' are handled by MANUAL_OVERRIDES (human decision) —
any still-unmatched row is left as 'Articles' and reported, never guessed.

Usage:
    python scripts/14_apply_article_industries.py <review_csv> [--dry-run]
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Human decisions for rows the AI classifier couldn't confidently place.
# "India API Market: From Dependency to Dominance" — 'API' here = Active
# Pharmaceutical Ingredient (India pharma import-substitution story), not a
# software API. -> Healthcare (Shrey-reviewed, 2026-07-09).
MANUAL_OVERRIDES = {
    "https://www.kenresearch.com/articles/india-api-market-dependency-to-dominance": "Healthcare",
}

CANONICAL_INDUSTRIES = {
    "Agriculture & Animal Care", "Automotive, Transportation & Logistics",
    "BFSI", "Consumer Products & Retail", "Defense & Security",
    "Education & Recruitment", "Energy & Utilities", "Food, Beverage & Tobacco",
    "Healthcare", "Metal, Mining and Chemicals", "Manufacturing & Construction",
    "Media & Entertainment", "Public Sector and Administration",
    "Technology & Telecom",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.review_csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    conn = sqlite3.connect(ROOT / "ken_links.db")
    applied, overridden, left_unmatched = 0, 0, []
    for r in rows:
        industry = r["proposed_industry"]
        if industry == "(no confident match)":
            industry = MANUAL_OVERRIDES.get(r["url"])
            if industry:
                overridden += 1
            else:
                left_unmatched.append(r["url"])
                continue
        if industry not in CANONICAL_INDUSTRIES:
            print(f"SKIP (not canonical): {r['url']} -> {industry}", file=sys.stderr)
            continue
        if not args.dry_run:
            conn.execute(
                "UPDATE content_nodes SET industry = ? WHERE node_id = ?",
                (industry, r["node_id"]),
            )
        applied += 1
    if not args.dry_run:
        conn.commit()
    remaining = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE industry = 'Articles'"
    ).fetchone()[0]
    conn.close()

    print(f"{'[DRY RUN] would apply' if args.dry_run else 'Applied'}: {applied} "
          f"({overridden} via manual override)")
    if left_unmatched:
        print(f"Left as 'Articles' (no decision): {len(left_unmatched)}")
        for u in left_unmatched:
            print(f"  {u}")
    print(f"Remaining 'Articles' industry rows after apply: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
