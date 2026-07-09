"""One-off fix: 6 pages had industry='Consumer Services', not one of the 14
canonical Ken Research industries. Reclassified by reading each title
(Shrey-reported bug, 2026-07-09). Same precedent as the 'Consulting' fix
(scripts/12_fix_consulting_industry.py).
"""

import sqlite3

RECLASSIFICATION = {
    "bahrain-commercial-cleaning-products-market": "Consumer Products & Retail",
    "uae-pet-boarding-services-market": "Consumer Products & Retail",
    "thailand-coin-operated-commercial-laundry-market": "Consumer Products & Retail",
    "germany-facility-management-and-smart-services-market": "Manufacturing & Construction",
    "uae-digital-fitness-wellness-market": "Consumer Products & Retail",
    "indonesia-coin-operated-commercial-laundry-market": "Consumer Products & Retail",
}

conn = sqlite3.connect("ken_links.db")
total = 0
for slug, industry in RECLASSIFICATION.items():
    cursor = conn.execute(
        "UPDATE content_nodes SET industry = ? WHERE url LIKE ?",
        (industry, f"%/{slug}"),
    )
    print(f"{slug} -> {industry}: {cursor.rowcount} row(s)")
    total += cursor.rowcount
conn.commit()
remaining = conn.execute(
    "SELECT COUNT(*) FROM content_nodes WHERE industry = 'Consumer Services'"
).fetchone()[0]
conn.close()
print(f"\nTotal updated: {total}")
print(f"Remaining 'Consumer Services' rows: {remaining}")
