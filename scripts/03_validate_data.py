"""
Module 3.1 — Data Validation & Quality Metrics
Ken Intelligence Linking Engine

Produces a comprehensive quality report for all content_nodes:
  - Row counts per table
  - Content type distribution
  - Industry distribution
  - Country distribution
  - Field completeness (% populated per column)
  - Duplicate detection
  - Overall quality score

Run:  python scripts/03_validate_data.py
"""

import os
import sqlite3
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "ken_links.db")

# ── helpers ──────────────────────────────────────────────────────────────────

def pct(count, total):
    """Format count/total as a percentage string, e.g. '95.0%'."""
    return f"{(count / total * 100):.1f}%" if total else "0.0%"

def bar(count, total, width=20):
    """Render count/total as a fixed-width ASCII progress bar."""
    filled = int(count / total * width) if total else 0
    return "#" * filled + "-" * (width - filled)

def top_n(counter, n=10):
    """Return the n most common items from a Counter."""
    return counter.most_common(n)

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    """Run the full data quality report against ken_links.db and print it,
    including the final weighted quality score (critical fields 80%,
    optional fields 20%, minus a duplicate-URL penalty)."""
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"DB not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sep  = "=" * 60
    sep2 = "-" * 60

    # ── 1. Table row counts ───────────────────────────────────────────────────
    tables = ["content_nodes", "content_entities", "relationship_edges", "crawl_logs"]
    counts = {}
    for t in tables:
        counts[t] = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    total = counts["content_nodes"]

    print(f"\n{sep}")
    print("  KEN INTELLIGENCE LINKING ENGINE - VALIDATION REPORT")
    print(sep)

    print("\n[1] TABLE ROW COUNTS")
    print(sep2)
    for t in tables:
        print(f"  {t:<25} {counts[t]:>6} rows")

    if total == 0:
        print("\nWARNING: content_nodes is empty. Run 02_load_urls.py first.")
        conn.close()
        return

    # ── 2. Content type distribution ─────────────────────────────────────────
    print(f"\n[2] CONTENT TYPE DISTRIBUTION  (total: {total})")
    print(sep2)
    rows = cur.execute(
        "SELECT COALESCE(NULLIF(content_type,''),'(empty)') as ct, COUNT(*) c "
        "FROM content_nodes GROUP BY ct ORDER BY c DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r['ct']:<30} {r['c']:>5}  {pct(r['c'], total):>6}  {bar(r['c'], total)}")

    # ── 3. Industry distribution ──────────────────────────────────────────────
    print(f"\n[3] INDUSTRY DISTRIBUTION  (top 15)")
    print(sep2)
    rows = cur.execute(
        "SELECT COALESCE(NULLIF(industry,''),'(empty)') as ind, COUNT(*) c "
        "FROM content_nodes GROUP BY ind ORDER BY c DESC LIMIT 15"
    ).fetchall()
    for r in rows:
        print(f"  {r['ind']:<35} {r['c']:>5}  {pct(r['c'], total):>6}  {bar(r['c'], total)}")

    # ── 4. Country distribution ───────────────────────────────────────────────
    print(f"\n[4] COUNTRY DISTRIBUTION  (top 15)")
    print(sep2)
    rows = cur.execute(
        "SELECT COALESCE(NULLIF(country,''),'(empty)') as co, COUNT(*) c "
        "FROM content_nodes GROUP BY co ORDER BY c DESC LIMIT 15"
    ).fetchall()
    for r in rows:
        print(f"  {r['co']:<30} {r['c']:>5}  {pct(r['c'], total):>6}  {bar(r['c'], total)}")

    # ── 5. Global vs Local ────────────────────────────────────────────────────
    print(f"\n[5] GLOBAL vs LOCAL")
    print(sep2)
    rows = cur.execute(
        "SELECT COALESCE(NULLIF(global_or_local,''),'(empty)') as gl, COUNT(*) c "
        "FROM content_nodes GROUP BY gl ORDER BY c DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r['gl']:<20} {r['c']:>5}  {pct(r['c'], total):>6}  {bar(r['c'], total)}")

    # ── 6. Field completeness ─────────────────────────────────────────────────
    print(f"\n[6] FIELD COMPLETENESS  (% of rows with a value)")
    print(sep2)

    critical_fields = ["url", "title", "content_type", "country", "global_or_local"]
    optional_fields = ["industry", "canonical_url", "meta_title", "meta_description",
                       "h1", "region", "published_date", "status"]

    field_scores = {}

    print("  CRITICAL FIELDS:")
    for f in critical_fields:
        filled = cur.execute(
            f"SELECT COUNT(*) FROM content_nodes WHERE {f} IS NOT NULL AND {f} != ''"
        ).fetchone()[0]
        score = filled / total * 100
        field_scores[f] = score
        flag = "[OK]" if score >= 90 else "[!!]" if score >= 50 else "[X]"
        print(f"    {flag} {f:<25} {filled:>5}/{total}  {pct(filled, total):>6}  {bar(filled, total)}")

    print("  OPTIONAL FIELDS:")
    for f in optional_fields:
        try:
            filled = cur.execute(
                f"SELECT COUNT(*) FROM content_nodes WHERE {f} IS NOT NULL AND {f} != ''"
            ).fetchone()[0]
        except Exception:
            filled = 0
        score = filled / total * 100
        field_scores[f] = score
        flag = "[OK]" if score >= 90 else "[!!]" if score >= 50 else "[X]"
        print(f"    {flag} {f:<25} {filled:>5}/{total}  {pct(filled, total):>6}  {bar(filled, total)}")

    # ── 7. Duplicate detection ────────────────────────────────────────────────
    print(f"\n[7] DUPLICATE DETECTION")
    print(sep2)
    dupes = cur.execute(
        "SELECT url, COUNT(*) c FROM content_nodes GROUP BY url HAVING c > 1"
    ).fetchall()
    if dupes:
        print(f"  [X] {len(dupes)} duplicate URLs found:")
        for d in dupes[:10]:
            print(f"     {d['url']}")
    else:
        print("  [OK] No duplicate URLs found")

    # ── 8. Quality score ──────────────────────────────────────────────────────
    # Critical fields = 80% weight, optional = 20% weight
    critical_avg = sum(field_scores[f] for f in critical_fields) / len(critical_fields)
    optional_avg = sum(field_scores.get(f, 0) for f in optional_fields) / len(optional_fields)
    quality_score = (critical_avg * 0.8) + (optional_avg * 0.2)
    dupe_penalty = len(dupes) * 0.5
    quality_score = max(0, quality_score - dupe_penalty)

    grade = "EXCELLENT" if quality_score >= 90 else \
            "GOOD"      if quality_score >= 80 else \
            "FAIR"      if quality_score >= 60 else \
            "POOR"

    print(f"\n{'=' * 60}")
    print(f"  OVERALL DATA QUALITY SCORE")
    print(f"{'=' * 60}")
    print(f"  Critical fields avg  : {critical_avg:.1f}%  (weight 80%)")
    print(f"  Optional fields avg  : {optional_avg:.1f}%  (weight 20%)")
    print(f"  Duplicate penalty    : -{dupe_penalty:.1f} pts")
    print(f"  {'-'*40}")
    print(f"  FINAL SCORE          : {quality_score:.1f}%  [{grade}]")
    print(f"  TARGET               : >= 80%")
    print(f"  STATUS               : {'PASS' if quality_score >= 80 else 'NEEDS IMPROVEMENT'}")
    print(f"{'=' * 60}\n")

    conn.close()


if __name__ == "__main__":
    main()
