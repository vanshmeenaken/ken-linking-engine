# Google Search Console Integration

## Status

Live. Connected on 15 July 2026 against the property
`https://www.kenresearch.com/`. First sync matched 194 of the 500 inventory
pages and found 11,065 site-wide pages in striking distance.

## Purpose

Search Console tells us how each page performs in Google: its ranking, how often
it appears, and how often it is clicked. This turns `search_opportunity_score`
from an inferred structural estimate into fact. A page ranking at position 8 for
a real query with real impressions is a page where one internal link genuinely
moves revenue (master PRD section 11.3: push internal links to pages ranking
between position 4 and 20).

Read-only. The integration uses the `webmasters.readonly` scope and never writes
to Google.

## Metrics pulled

Per page, over a lookback window (default 28 days, ending yesterday because the
current day is incomplete):

- clicks
- impressions
- CTR
- average position

The top queries per page are also available (`fetch_queries_for_page`), the raw
material for anchor-text suggestions in Phase 3.

## Striking distance

Pages ranking between position 4 and 20 (configurable via
`STRIKING_DISTANCE_MIN` and `STRIKING_DISTANCE_MAX`). These gain the most from
internal links: close enough to page 1 that a push moves them, far enough that
the traffic gain is large. Served at `GET /api/opportunities/striking-distance`,
highest impressions first.

## URL to node mapping

Search Console reports absolute URLs; the database keys pages by node_id. Both
sides are reduced to a bare lowercase path by `normalise_url` in
`integrations/common.py`, so trailing slashes, scheme, www, query strings, and
fragments never split one page into several. A GSC absolute URL and a GA4 bare
path for the same page resolve to the same node.

Rows that do not match any inventory page are stored with `status = 'unmatched'`
rather than dropped, so the gap between Google's view of the whole site
(about 42,000 pages) and our 500-page inventory stays visible instead of hidden.

## Credentials

One credentials file drives both GSC and GA4, set by `GOOGLE_CREDENTIALS_PATH`
in `.env`. Two kinds are auto-detected (see `config/settings.py`):

- OAuth client (Desktop app): a one-time browser login as an account that
  already has access; the token is cached in `credentials/token.json` and
  refreshes silently on every run after. This is what is in use.
- Service account: a robot identity whose email an admin grants access to the
  property.

The property is set by `GSC_SITE_URL`.

## The property-form gotcha

The first attempt used `sc-domain:kenresearch.com` (a domain property) and got a
403 "insufficient permission". The account actually has access to the
URL-prefix property `https://www.kenresearch.com/`, not the domain form. To
resolve which properties an account can see, list them directly:

```powershell
python -c "from integrations.common import load_credentials; from googleapiclient.discovery import build; svc=build('searchconsole','v1',credentials=load_credentials(),cache_discovery=False); print([s['siteUrl'] for s in svc.sites().list().execute().get('siteEntry',[])])"
```

Then set `GSC_SITE_URL` to exactly what it returns.

## Commands

Dry run (fetch and report, no writes):

```powershell
python scripts/19_sync_gsc.py --dry-run
```

Live sync:

```powershell
python scripts/19_sync_gsc.py
```

Custom window:

```powershell
python scripts/19_sync_gsc.py --days 90
```

Data lands in `integration_placeholders` with `source = 'gsc'`. Re-running
replaces that source's rows for the same window rather than duplicating.

## Limitations

- The inventory is 500 pages while GSC covers the whole site, so most returned
  rows are unmatched (stored, not dropped). Match rate rises as the inventory
  grows.
- GSC data lags real time by about 2 to 3 days.
- Position and impression driven opportunity types in Agent 4
  (position_4_to_20, high_impression_low_ctr) are the natural next build now
  that this data exists.

## Verification

```powershell
python -m pytest tests/test_integrations.py -q
```

Check the connection and data through the API:

- `GET /api/integrations/status` connection state and pages matched
- `GET /api/pages/{node_id}/search-performance` one page's ranking data
- `GET /api/opportunities/striking-distance` the position 4-20 list
