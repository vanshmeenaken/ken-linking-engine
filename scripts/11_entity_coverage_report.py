"""Entity coverage report (Phase 2, Day 5 Module 5.2).

Reads the live database (not the API — this must work even if the server
isn't running) and produces the same coverage numbers as
GET /api/intelligence/entity-coverage, plus the lists of pages missing
market/geography entities that the API summary doesn't include.

Usage:
    python scripts/11_entity_coverage_report.py
    python scripts/11_entity_coverage_report.py --db path/to/other.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
REPORT_DIR = ROOT / "reports"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _covered_node_ids(conn, entity_types: tuple[str, ...]) -> set[str]:
    placeholders = ",".join("?" * len(entity_types))
    return {
        row["node_id"]
        for row in conn.execute(
            f"""SELECT DISTINCT ne.node_id FROM node_entities ne
                JOIN content_entities ce ON ce.entity_id = ne.entity_id
                JOIN content_nodes n ON n.node_id = ne.node_id
                WHERE ce.entity_type IN ({placeholders})
                  AND ne.status != 'rejected' AND n.status = 'active'""",
            entity_types,
        )
    }


def build_report(db_path: Path) -> dict:
    conn = _connect(db_path)
    try:
        active_nodes = {
            row["node_id"]: row["url"]
            for row in conn.execute(
                "SELECT node_id, url FROM content_nodes WHERE status='active'"
            )
        }
        active = len(active_nodes)

        any_entity = _covered_node_ids(conn, ("industry", "sub_industry", "market",
                                              "segment", "country", "region",
                                              "time_period"))
        geo = _covered_node_ids(conn, ("country", "region"))
        ind_market = _covered_node_ids(conn, ("industry", "market"))
        market = _covered_node_ids(conn, ("market",))

        pct = lambda s: round(100.0 * len(s) / active, 1) if active else 0.0

        missing_market = sorted(
            active_nodes[nid] for nid in (set(active_nodes) - market)
        )
        missing_geo = sorted(
            active_nodes[nid] for nid in (set(active_nodes) - geo)
        )
        missing_any = sorted(
            active_nodes[nid] for nid in (set(active_nodes) - any_entity)
        )

        confidence_bands = {
            row["band"]: row["n"]
            for row in conn.execute(
                """SELECT CASE WHEN confidence_score>=0.9 THEN 'high_0.9_plus'
                               WHEN confidence_score>=0.7 THEN 'good_0.7_to_0.9'
                               WHEN confidence_score>=0.5 THEN 'review_0.5_to_0.7'
                               ELSE 'low_below_0.5' END AS band, COUNT(*) AS n
                   FROM node_entities GROUP BY band"""
            )
        }
        low_confidence_count = sum(
            n for band, n in confidence_bands.items()
            if band in ("review_0.5_to_0.7", "low_below_0.5")
        )
        statuses = {
            row["status"]: row["n"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS n FROM node_entities GROUP BY status"
            )
        }
        entity_totals = {
            row["entity_type"]: row["n"]
            for row in conn.execute(
                "SELECT entity_type, COUNT(*) AS n FROM content_entities "
                "GROUP BY entity_type ORDER BY n DESC"
            )
        }
        duplicate_groups = conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT normalized_name, entity_type FROM content_entities
                   GROUP BY normalized_name, entity_type HAVING COUNT(*) > 1
               )"""
        ).fetchone()[0]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "active_pages": active,
            "coverage": {
                "pages_with_any_entity": {
                    "count": len(any_entity), "pct": pct(any_entity), "target_pct": 95.0,
                    "meets_target": pct(any_entity) >= 95.0,
                },
                "pages_with_geography": {
                    "count": len(geo), "pct": pct(geo), "target_pct": 90.0,
                    "meets_target": pct(geo) >= 90.0,
                },
                "pages_with_industry_or_market": {
                    "count": len(ind_market), "pct": pct(ind_market), "target_pct": 80.0,
                    "meets_target": pct(ind_market) >= 80.0,
                },
                "pages_with_market": {"count": len(market), "pct": pct(market)},
            },
            "unique_entities_by_type": entity_totals,
            "duplicate_entity_groups": duplicate_groups,
            "mapping_confidence_bands": confidence_bands,
            "low_confidence_mapping_count": low_confidence_count,
            "mapping_statuses": statuses,
            "missing_market_pages": {
                "count": len(missing_market), "urls": missing_market,
            },
            "missing_geography_pages": {
                "count": len(missing_geo), "urls": missing_geo,
            },
            "missing_any_entity_pages": {
                "count": len(missing_any), "urls": missing_any,
            },
        }
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)

    report = build_report(Path(args.db))
    REPORT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"entity_coverage_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Active pages: {report['active_pages']}")
    for key, val in report["coverage"].items():
        if "target_pct" in val:
            mark = "OK" if val["meets_target"] else "BELOW TARGET"
            print(f"  {key}: {val['pct']}% (target {val['target_pct']}%) [{mark}]")
        else:
            print(f"  {key}: {val['pct']}%")
    print(f"Unique entities: {report['unique_entities_by_type']}")
    print(f"Duplicate entity groups: {report['duplicate_entity_groups']}")
    print(f"Low-confidence mappings: {report['low_confidence_mapping_count']}")
    print(f"Pages missing market: {report['missing_market_pages']['count']}")
    print(f"Pages missing geography: {report['missing_geography_pages']['count']}")
    print(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
