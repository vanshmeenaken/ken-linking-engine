"""Pull Google Analytics 4 behaviour/conversion data and store it against
content_nodes.

Writes sessions / users / engagement / key events per page into
integration_placeholders (source='ga4'), matched to node_id where possible.

Safe to re-run: replaces this source's rows for the same date window rather
than accumulating duplicates. Exits cleanly (code 0) when credentials are not
yet configured.

Usage:
    python scripts/20_sync_ga4.py --dry-run
    python scripts/20_sync_ga4.py
    python scripts/20_sync_ga4.py --events      # list the property's real key-event names
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.common import (CredentialsMissing, date_range, normalise_url,
                                 open_db, store_metrics, url_to_node_map)
from integrations.ga4_client import GA4Client

METRICS = ("sessions", "users", "engaged_sessions",
           "avg_engagement_seconds", "key_events")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="lookback window (default: GA4_LOOKBACK_DAYS)")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and report; write nothing")
    parser.add_argument("--events", action="store_true",
                        help="list the property's actual key-event names and exit")
    args = parser.parse_args(argv)

    from config.settings import GA4_LOOKBACK_DAYS, GA4_PROPERTY_ID
    days = args.days or GA4_LOOKBACK_DAYS
    start, end = date_range(days)
    window = f"{start}..{end}"

    print("GA4 sync")
    print(f"  property : {GA4_PROPERTY_ID or '(unset)'}")
    print(f"  window   : {window} ({days} days)")

    client = GA4Client()

    # --events: discover what Ken actually tracks before mapping to business
    # meaning. Guessing event names ('sample_request') would silently produce
    # zeros if the real name differs.
    if args.events:
        try:
            events = client.fetch_key_events(lookback_days=days)
        except CredentialsMissing as exc:
            print(f"\nSKIPPED - credentials not configured.\n{exc}")
            return 0
        names: dict[str, float] = {}
        for e in events:
            names[e["event_name"]] = names.get(e["event_name"], 0) + e["key_events"]
        print("\n  Key events reported by this property:")
        for name, total in sorted(names.items(), key=lambda kv: -kv[1]):
            print(f"    {total:10.0f}  {name}")
        print("\nUse these real names to define the conversion mapping "
              "(report enquiry / sample request / consulting enquiry).")
        return 0

    try:
        rows = client.fetch_page_metrics(lookback_days=days)
    except CredentialsMissing as exc:
        print(f"\nSKIPPED - credentials not configured.\n{exc}")
        return 0

    if not rows:
        print("\nNo rows returned. Either the property has no data in this "
              "window, or the service account lacks access to it.")
        return 0

    conn = open_db()
    node_map = url_to_node_map(conn)

    metric_rows, unmatched = [], []
    converting = 0
    for r in rows:
        node_id = node_map.get(normalise_url(r.path))
        if node_id is None:
            unmatched.append(r.path)
        if r.key_events > 0:
            converting += 1
        for metric in METRICS:
            metric_rows.append({
                "url": r.path,
                "node_id": node_id,
                "metric_name": metric,
                "metric_value": float(getattr(r, metric)),
                "notes": None,
            })

    in_inventory = sum(1 for r in rows if normalise_url(r.path) in node_map)
    print(f"\n  pages returned by GA4     : {len(rows)}")
    print(f"  matched to our inventory  : {in_inventory}")
    print(f"  not in our 500-page set   : {len(rows) - in_inventory}")
    print(f"  pages with conversions    : {converting}")

    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        for r in sorted(rows, key=lambda x: -x.sessions)[:5]:
            print(f"  {r.sessions:6d} sessions | {r.key_events:5.0f} conversions | {r.path}")
        conn.close()
        return 0

    try:
        conn.execute("BEGIN IMMEDIATE")
        m, u = store_metrics(conn, "ga4", metric_rows, window)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    conn.close()

    print(f"\n  metric rows written       : {m + u} ({m} matched, {u} unmatched)")
    print("OK - GA4 data stored (source='ga4').")
    if unmatched:
        print(f"\nNote: {len(set(unmatched))} GA4 paths are not in content_nodes "
              "(GA4 covers the whole site; our inventory holds 500). Stored with "
              "status='unmatched' rather than dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
