"""Google Analytics 4 connector.

Pulls per-page behaviour and conversion data (sessions, users, engagement,
key events) and stores it against content_nodes.

Why this matters to the linking engine: `business_priority` currently INFERS
buyer intent from page type (report > case study > article). That is a proxy.
GA4 replaces the proxy with measurement — which pages actually produce sample
requests and enquiries. Master PRD 11.4 names exactly these signals
(get_report_enquiries, get_sample_requests, get_assisted_conversions).

Read-only: uses the analytics.readonly scope and never writes to Google.

Note on conversions: GA4 has no universal "enquiry" metric — it depends on how
Ken configured key events. `fetch_key_events()` returns whatever key events the
property actually reports, rather than guessing at event names that may not
exist. Map them to business meaning once we can see the real names.

Usage:
    from integrations.ga4_client import GA4Client
    rows = GA4Client().fetch_page_metrics()
"""
from __future__ import annotations

from dataclasses import dataclass

from integrations.common import (GA4_SCOPES, CredentialsMissing, date_range,
                                 load_credentials)


@dataclass
class PageMetrics:
    path: str            # GA4 reports a page path, not an absolute URL
    sessions: int
    users: int
    engaged_sessions: int
    avg_engagement_seconds: float
    key_events: float    # total key-event (conversion) count for the page

    @property
    def engagement_rate(self) -> float:
        return self.engaged_sessions / self.sessions if self.sessions else 0.0


class GA4Client:
    """Thin, read-only wrapper over the GA4 Data API."""

    def __init__(self, property_id: str | None = None):
        from config.settings import GA4_PROPERTY_ID
        self.property_id = property_id or GA4_PROPERTY_ID
        self._client = None

    def _connect(self):
        if self._client is None:
            if not self.property_id:
                raise CredentialsMissing(
                    "GA4_PROPERTY_ID is not set. Find it in GA4 under\n"
                    "  Admin -> Property Settings -> PROPERTY ID (a number),\n"
                    "then set GA4_PROPERTY_ID in .env."
                )
            try:
                from google.analytics.data_v1beta import BetaAnalyticsDataClient
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise CredentialsMissing(
                    "google-analytics-data is not installed. Run:\n"
                    "  pip install -r requirements.txt"
                ) from exc
            creds = load_credentials(GA4_SCOPES)
            self._client = BetaAnalyticsDataClient(credentials=creds)
        return self._client

    def fetch_page_metrics(self, lookback_days: int | None = None,
                           limit: int = 100000) -> list[PageMetrics]:
        """Per-page behaviour + conversion totals over the window."""
        from config.settings import GA4_LOOKBACK_DAYS
        from google.analytics.data_v1beta.types import (DateRange, Dimension,
                                                        Metric, RunReportRequest)

        start, end = date_range(lookback_days or GA4_LOOKBACK_DAYS)
        client = self._connect()

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="engagedSessions"),
                Metric(name="userEngagementDuration"),
                Metric(name="keyEvents"),
            ],
            limit=limit,
        )
        resp = client.run_report(request)

        out: list[PageMetrics] = []
        for row in resp.rows:
            sessions = _int(row.metric_values[0].value)
            engagement_seconds = _float(row.metric_values[3].value)
            out.append(PageMetrics(
                path=row.dimension_values[0].value,
                sessions=sessions,
                users=_int(row.metric_values[1].value),
                engaged_sessions=_int(row.metric_values[2].value),
                # GA4 returns TOTAL engagement seconds; per-session average is
                # the comparable figure across pages with different traffic.
                avg_engagement_seconds=(
                    round(engagement_seconds / sessions, 1) if sessions else 0.0
                ),
                key_events=_float(row.metric_values[4].value),
            ))
        return out

    def fetch_key_events(self, lookback_days: int | None = None) -> list[dict]:
        """Key-event names and counts per page.

        Returns the property's ACTUAL event names rather than assuming
        Ken-specific ones ('sample_request', 'enquiry', ...) that may not
        exist. Use the output to decide the business mapping.
        """
        from config.settings import GA4_LOOKBACK_DAYS
        from google.analytics.data_v1beta.types import (DateRange, Dimension,
                                                        Metric, RunReportRequest)

        start, end = date_range(lookback_days or GA4_LOOKBACK_DAYS)
        client = self._connect()
        resp = client.run_report(RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name="pagePath"), Dimension(name="eventName")],
            metrics=[Metric(name="eventCount"), Metric(name="keyEvents")],
            limit=100000,
        ))
        return [
            {
                "path": r.dimension_values[0].value,
                "event_name": r.dimension_values[1].value,
                "event_count": _int(r.metric_values[0].value),
                "key_events": _float(r.metric_values[1].value),
            }
            for r in resp.rows
        ]


def _int(v: str) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _float(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
