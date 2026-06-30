"""Generate a manager-ready Agent 1 verification report."""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-report", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--db", default=str(ROOT / "ken_links.db"))
    parser.add_argument(
        "--output", default=str(ROOT / "reports" / "AGENT_1_EXECUTION_REPORT.md")
    )
    args = parser.parse_args()
    execution = json.loads(Path(args.execution_report).read_text(encoding="utf-8"))
    summary = execution["summary"]
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    conn = sqlite3.connect(f"file:{Path(args.db).resolve()}?mode=ro", uri=True)
    try:
        total = conn.execute("SELECT COUNT(*) FROM content_nodes").fetchone()[0]
        types = dict(conn.execute(
            "SELECT content_type,COUNT(*) FROM content_nodes GROUP BY content_type"
        ))
        statuses = dict(conn.execute(
            "SELECT orphan_status,COUNT(*) FROM content_nodes GROUP BY orphan_status"
        ))
        duplicates = conn.execute(
            "SELECT COUNT(*) FROM (SELECT url FROM content_nodes GROUP BY url HAVING COUNT(*)>1)"
        ).fetchone()[0]
        enriched = conn.execute(
            """SELECT COUNT(*) FROM content_nodes
            WHERE crawl_depth IS NOT NULL AND internal_links_in IS NOT NULL
              AND internal_links_out IS NOT NULL AND orphan_status IS NOT NULL
              AND page_authority_score IS NOT NULL"""
        ).fetchone()[0]
        metadata = {}
        for field in ("canonical_url", "meta_title", "meta_description", "h1", "indexability_status"):
            metadata[field] = conn.execute(
                f"SELECT COUNT(*) FROM content_nodes WHERE {field} IS NOT NULL AND {field} != ''"
            ).fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()

    checks = {
        "All 500 inventory rows retained": total == 500,
        "All 500 pages enriched": enriched == 500,
        "No duplicate URLs": duplicates == 0,
        "Database integrity": integrity == "ok",
        "Agent fetched all pages": summary.get("successful") == 500 and summary.get("failed") == 0,
        "Agent analysis completed under 60 seconds": summary.get("elapsed_seconds", 999) < 60,
        "Site-wide coverage at least 99 percent": snapshot.get("coverage_percent", 0) >= 99,
    }
    overall = "PASS" if all(checks.values()) else "REVIEW REQUIRED"
    lines = [
        "# Agent 1 - Content Inventory Execution Report",
        "",
        f"**Generated:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"**Overall status:** {overall}",
        "",
        "## Executive result",
        "",
        f"Agent 1 processed **{summary.get('successful', 0)} of 500 pages** in "
        f"**{summary.get('elapsed_seconds')} seconds**. The database contains "
        f"**{total} pages**, with **{enriched} enriched records**, **{duplicates} "
        f"duplicate URLs**, and SQLite integrity **{integrity}**.",
        "",
        "## Content inventory",
        "",
        "| Content type | Pages |",
        "|---|---:|",
    ]
    lines.extend(f"| {key} | {value} |" for key, value in sorted(types.items()))
    lines += ["", "## Link-status results", "", "| Status | Pages |", "|---|---:|"]
    lines.extend(f"| {key} | {value} |" for key, value in sorted(statuses.items()))
    lines += [
        "",
        "## Evidence coverage",
        "",
        f"- Official sitemap pages discovered: {snapshot.get('sources_total')}",
        f"- Successfully crawled source pages: {snapshot.get('sources_successful')}",
        f"- Failed source pages: {snapshot.get('sources_failed')}",
        f"- Site-wide coverage: {snapshot.get('coverage_percent')}%",
        f"- Canonical URLs populated: {metadata['canonical_url']}/500",
        f"- Meta titles populated: {metadata['meta_title']}/500",
        f"- Meta descriptions populated: {metadata['meta_description']}/500",
        f"- H1 populated: {metadata['h1']}/500",
        f"- Indexability populated: {metadata['indexability_status']}/500",
        "",
        "## Acceptance checks",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    lines.extend(
        f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in checks.items()
    )
    lines += [
        "",
        "## Methodology note",
        "",
        "Incoming links count unique source pages found through the official Ken "
        "Research sitemap inventory. Outgoing links count unique Ken Research URLs "
        "present in each selected page's live HTML. Crawl depth is structural URL "
        "path depth, matching the Day 4 task definition.",
        "",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {output}")
    print(f"Overall status: {overall}")
    return 0 if overall == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
