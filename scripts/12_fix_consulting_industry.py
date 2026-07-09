"""One-off fix: 4 pages had industry='Consulting', which is not one of the
14 canonical Ken Research industries. Reclassified by reading each page's
title/H1 (Shrey-reported bug, 2026-07-09).

Follows the existing precedent (scripts/fix_case_study_industry.py) of a
direct content_nodes.industry correction for bad Phase 1 source data.
"""

import sqlite3

RECLASSIFICATION = {
    "qatar-nordic-regulatory-affairs-market": "Healthcare",
    "oman-business-process-outsourcing-bpo-market": "Technology & Telecom",
    "vietnam-customer-experience-business-process-outsourcing-market": "Technology & Telecom",
    "mexico-facility-management-and-ifm-market": "Manufacturing & Construction",
}

conn = sqlite3.connect("ken_links.db")
total = 0
for slug, industry in RECLASSIFICATION.items():
    cursor = conn.execute(
        "UPDATE content_nodes SET industry = ? WHERE url LIKE ?",
        (industry, f"%/{slug}"),
    )
    print(f"{slug} -> {industry}: {cursor.rowcount} row(s) updated")
    total += cursor.rowcount
conn.commit()
remaining = conn.execute(
    "SELECT COUNT(*) FROM content_nodes WHERE industry = 'Consulting'"
).fetchone()[0]
conn.close()
print(f"\nTotal updated: {total}")
print(f"Remaining 'Consulting' rows: {remaining}")
