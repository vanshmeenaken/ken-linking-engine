"""Agent 7 - Anchor Text Agent (master PRD 13.7, 18.4; Phase 3).

Builds an anchor bank for each page that receives recommended links: a set of
diverse, safe anchor-text options so no single exact-match anchor dominates all
inbound links to a page. Over-using one exact anchor is a real over-optimization
risk (master PRD 18.4 anchor diversity); a bank lets the deployment step rotate
anchors instead.

Writes to anchor_banks, one row per target page, with categorised variations:
    primary_anchor           the main descriptive anchor (Country Market)
    secondary_anchors        natural variations (outlook, analysis, size)
    long_tail_anchors        longer descriptive phrases (trends and forecast)
    country_specific_anchors country + market
    market_specific_anchors  market alone / segment framing
    commercial_anchors       report / sample-report intent
    restricted_anchors       the generic phrases that must never be used

All descriptive anchors are built from the page's own market/country/region, so
nothing is invented. Generic anchors are stored only as the restricted list, so
the deployment step knows what to reject.

Usage:
    python agents/agent_7_anchor_text.py --dry-run
    python agents/agent_7_anchor_text.py --limit 20 --dry-run
    python agents/agent_7_anchor_text.py                 # all recommendation targets
    python agents/agent_7_anchor_text.py --all-active     # every active page
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.anchor_text import (GENERIC_ANCHORS, build_primary_anchor,
                                  format_geo, with_market_suffix)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"


@dataclass
class AnchorBank:
    target_node_id: str
    target_url: str
    primary_anchor: str
    secondary_anchors: list = field(default_factory=list)
    long_tail_anchors: list = field(default_factory=list)
    country_specific_anchors: list = field(default_factory=list)
    market_specific_anchors: list = field(default_factory=list)
    commercial_anchors: list = field(default_factory=list)
    restricted_anchors: list = field(default_factory=list)


class AnchorTextAgent:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _bank_for(node: sqlite3.Row) -> AnchorBank:
        market = (node["market"] or "").strip()
        country = (node["country"] or "").strip()
        region = (node["region"] or "").strip()
        primary, _ = build_primary_anchor(market, country, node["title"])
        mkt = with_market_suffix(market)  # "Online Grocery Market" or ""
        geo = format_geo(country)

        secondary, long_tail, country_a, market_a, commercial = [], [], [], [], []
        if mkt:
            base = f"{geo} {mkt}".strip() if geo else mkt
            secondary = [f"{base} Outlook", f"{base} Analysis", f"{base} Size"]
            long_tail = [f"{base} Trends and Forecast",
                         f"{base} Growth and Opportunities"]
            market_a = [mkt]
            commercial = [f"{base} Report", f"{base} Sample Report"]
            if geo:
                country_a = [base]
            if region:
                secondary.append(f"{format_geo(region)} {mkt}")

        # de-duplicate while preserving order, drop anything equal to primary
        def clean(lst):
            seen, out = {primary.lower()}, []
            for a in lst:
                a = a.strip()
                if a and a.lower() not in seen:
                    seen.add(a.lower()); out.append(a)
            return out

        return AnchorBank(
            target_node_id=node["node_id"], target_url=node["url"],
            primary_anchor=primary,
            secondary_anchors=clean(secondary),
            long_tail_anchors=clean(long_tail),
            country_specific_anchors=clean(country_a),
            market_specific_anchors=clean(market_a),
            commercial_anchors=clean(commercial),
            restricted_anchors=sorted(GENERIC_ANCHORS),
        )

    def build(self, limit: int | None = None, all_active: bool = False) -> list[AnchorBank]:
        conn = self._connect()
        try:
            if all_active:
                q = "SELECT * FROM content_nodes WHERE status='active'"
            else:
                # only pages that actually receive a recommended link need a bank
                q = """SELECT n.* FROM content_nodes n
                       WHERE n.status='active' AND n.node_id IN (
                           SELECT DISTINCT target_node_id FROM link_recommendations)"""
            if limit:
                q += f" LIMIT {int(limit)}"
            nodes = conn.execute(q).fetchall()
            return [self._bank_for(n) for n in nodes]
        finally:
            conn.close()

    def write(self, banks: list[AnchorBank]) -> int:
        if not banks:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            for b in banks:
                conn.execute(
                    """INSERT INTO anchor_banks
                       (anchor_id, target_node_id, target_url, primary_anchor,
                        secondary_anchors, long_tail_anchors,
                        country_specific_anchors, market_specific_anchors,
                        commercial_anchors, restricted_anchors,
                        anchor_usage_count, overuse_flag, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,0,0,?,?)
                       ON CONFLICT (target_node_id) DO UPDATE SET
                           primary_anchor=excluded.primary_anchor,
                           secondary_anchors=excluded.secondary_anchors,
                           long_tail_anchors=excluded.long_tail_anchors,
                           country_specific_anchors=excluded.country_specific_anchors,
                           market_specific_anchors=excluded.market_specific_anchors,
                           commercial_anchors=excluded.commercial_anchors,
                           restricted_anchors=excluded.restricted_anchors,
                           updated_at=excluded.updated_at""",
                    (str(uuid.uuid4()), b.target_node_id, b.target_url,
                     b.primary_anchor,
                     json.dumps(b.secondary_anchors), json.dumps(b.long_tail_anchors),
                     json.dumps(b.country_specific_anchors),
                     json.dumps(b.market_specific_anchors),
                     json.dumps(b.commercial_anchors),
                     json.dumps(b.restricted_anchors), now, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return len(banks)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all-active", action="store_true",
                        help="build a bank for every active page, not just "
                             "recommendation targets")
    args = parser.parse_args(argv)

    agent = AnchorTextAgent(args.db)
    banks = agent.build(args.limit, args.all_active)
    total_variants = sum(
        len(b.secondary_anchors) + len(b.long_tail_anchors)
        + len(b.country_specific_anchors) + len(b.market_specific_anchors)
        + len(b.commercial_anchors) for b in banks)
    print(f"Anchor banks built: {len(banks)}")
    print(f"Total anchor variants (excl. primary + restricted): {total_variants}")

    if args.dry_run:
        print("Database update: skipped (dry run)")
        for b in banks[:5]:
            print(f"  {b.primary_anchor}")
            print(f"     secondary : {b.secondary_anchors}")
            print(f"     commercial: {b.commercial_anchors}")
    else:
        n = agent.write(banks)
        print(f"Database update: committed ({n} banks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
