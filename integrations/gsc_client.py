"""Google Search Console connector.

Pulls per-page search performance (clicks, impressions, CTR, average position)
and stores it against content_nodes.

Why this matters to the linking engine: `search_opportunity_score` is currently
inferred from structural signals only (orphan, underlinked, missing entities).
GSC replaces inference with fact — a page sitting at position 8 for a real query
with real impressions is a page where one internal link genuinely moves revenue.
Master PRD 11.3: "push internal links to pages ranking between position 4 and 20."

Read-only: uses the webmasters.readonly scope and never writes to Google.

Usage:
    from integrations.gsc_client import GSCClient
    rows = GSCClient().fetch_page_performance()
"""
from __future__ import annotations

from dataclasses import dataclass

from integrations.common import (GSC_SCOPES, CredentialsMissing, date_range,
                                 load_credentials)


@dataclass
class PagePerformance:
    url: str
    clicks: int
    impressions: int
    ctr: float           # 0.0-1.0
    position: float      # average SERP position; 1.0 is best

    @property
    def in_striking_distance(self) -> bool:
        """Ranking where an internal link has the most leverage (PRD 11.3)."""
        from config.settings import STRIKING_DISTANCE_MAX, STRIKING_DISTANCE_MIN
        return STRIKING_DISTANCE_MIN <= self.position <= STRIKING_DISTANCE_MAX


class GSCClient:
    """Thin, read-only wrapper over the Search Console API."""

    def __init__(self, site_url: str | None = None):
        from config.settings import GSC_SITE_URL
        self.site_url = site_url or GSC_SITE_URL
        self._service = None

    def _connect(self):
        if self._service is None:
            try:
                from googleapiclient.discovery import build
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise CredentialsMissing(
                    "google-api-python-client is not installed. Run:\n"
                    "  pip install -r requirements.txt"
                ) from exc
            creds = load_credentials(GSC_SCOPES)
            self._service = build("searchconsole", "v1", credentials=creds,
                                  cache_discovery=False)
        return self._service

    def fetch_page_performance(self, lookback_days: int | None = None,
                               row_limit: int = 25000) -> list[PagePerformance]:
        """Per-page totals over the window. Paginates until exhausted.

        Aggregated by page (not by query): the linking engine acts on pages,
        so per-query rows would need collapsing anyway, and asking GSC to
        aggregate avoids pulling tens of thousands of rows we would discard.
        """
        from config.settings import GSC_LOOKBACK_DAYS
        start, end = date_range(lookback_days or GSC_LOOKBACK_DAYS)
        service = self._connect()

        out: list[PagePerformance] = []
        start_row = 0
        while True:
            body = {
                "startDate": start,
                "endDate": end,
                "dimensions": ["page"],
                "rowLimit": min(row_limit, 25000),  # API hard cap per request
                "startRow": start_row,
            }
            resp = service.searchanalytics().query(
                siteUrl=self.site_url, body=body
            ).execute()
            rows = resp.get("rows", [])
            if not rows:
                break
            for r in rows:
                out.append(PagePerformance(
                    url=r["keys"][0],
                    clicks=int(r.get("clicks", 0)),
                    impressions=int(r.get("impressions", 0)),
                    ctr=float(r.get("ctr", 0.0)),
                    position=float(r.get("position", 0.0)),
                ))
            if len(rows) < body["rowLimit"]:
                break
            start_row += len(rows)
        return out

    def fetch_queries_for_page(self, page_url: str,
                               lookback_days: int | None = None,
                               row_limit: int = 100) -> list[dict]:
        """Top queries a single page ranks for — the raw material for
        anchor-text suggestions in Phase 3."""
        from config.settings import GSC_LOOKBACK_DAYS
        start, end = date_range(lookback_days or GSC_LOOKBACK_DAYS)
        service = self._connect()
        resp = service.searchanalytics().query(
            siteUrl=self.site_url,
            body={
                "startDate": start,
                "endDate": end,
                "dimensions": ["query"],
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "page",
                        "operator": "equals",
                        "expression": page_url,
                    }]
                }],
                "rowLimit": row_limit,
            },
        ).execute()
        return [
            {
                "query": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": float(r.get("ctr", 0.0)),
                "position": float(r.get("position", 0.0)),
            }
            for r in resp.get("rows", [])
        ]
