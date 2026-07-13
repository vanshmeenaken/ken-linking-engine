"""Pull Google Search Console performance and store it against content_nodes.

Writes clicks / impressions / ctr / position per page into
integration_placeholders (source='gsc'), matched to node_id where possible.

Safe to re-run: replaces this source's rows for the same date window rather
than accumulating duplicates. Exits cleanly (code 0) when credentials are not
yet configured, so it can sit in a pipeline before access is granted.

Usage:
    python scripts/19_sync_gsc.py --dry-run
    python scripts/19_sync_gsc.py
    python scripts/19_sync_gsc.py --days 90
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.common import (CredentialsMissing, date_range, normalise_url,
                                 open_db, store_metrics, url_to_node_map)
from integrations.gsc_client import GSCClient

METRICS = ("clicks", "impressions", "ctr", "position")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="lookback window (default: GSC_LOOKBACK_DAYS)")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and report; write nothing")
    args = parser.parse_args(argv)

    from config.settings import GSC_LOOKBACK_DAYS, GSC_SITE_URL
    days = args.days or GSC_LOOKBACK_DAYS
    start, end = date_range(days)
    window = f"{start}..{end}"

    print(f"Search Console sync")
    print(f"  property : {GSC_SITE_URL}")
    print(f"  window   : {window} ({days} days)")

    try:
        rows = GSCClient().fetch_page_performance(lookback_days=days)
    except CredentialsMissing as exc:
        print(f"\nSKIPPED - credentials not configured.\n{exc}")
        return 0  # not an error: expected before access is granted

    if not rows:
        print("\nNo rows returned. Either the property has no data in this "
              "window, or the service account lacks access to it.")
        return 0

    conn = open_db()
    node_map = url_to_node_map(conn)

    striking, matched_rows, unmatched_urls = 0, [], []
    for r in rows:
        node_id = node_map.get(normalise_url(r.url))
        if node_id is None:
            unmatched_urls.append(r.url)
        if r.in_striking_distance:
            striking += 1
        for metric in METRICS:
            matched_rows.append({
                "url": r.url,
                "node_id": node_id,
                "metric_name": metric,
                "metric_value": float(getattr(r, metric)),
                "notes": None,
            })

    in_inventory = sum(1 for r in rows if normalise_url(r.url) in node_map)
    print(f"\n  pages returned by GSC     : {len(rows)}")
    print(f"  matched to our inventory  : {in_inventory}")
    print(f"  not in our 500-page set   : {len(rows) - in_inventory}")
    print(f"  in striking distance (4-20): {striking}")

    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        for r in sorted(rows, key=lambda x: -x.impressions)[:5]:
            mark = "*" if r.in_striking_distance else " "
            print(f"  {mark} pos {r.position:5.1f} | {r.impressions:6d} impr | {r.url}")
        conn.close()
        return 0

    try:
        conn.execute("BEGIN IMMEDIATE")
        m, u = store_metrics(conn, "gsc", matched_rows, window)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    conn.close()

    print(f"\n  metric rows written       : {m + u} ({m} matched, {u} unmatched)")
    print("OK - Search Console data stored (source='gsc').")
    if unmatched_urls:
        print(f"\nNote: {len(set(unmatched_urls))} GSC URLs are not in content_nodes. "
              "Expected — GSC covers the whole site (~42k pages), our inventory "
              "holds 500. They are stored with status='unmatched' rather than "
              "dropped, so the gap stays visible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
