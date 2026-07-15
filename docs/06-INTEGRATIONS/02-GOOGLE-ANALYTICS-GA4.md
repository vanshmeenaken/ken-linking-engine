# Google Analytics 4 Integration

## Status

Live. Connected on 15 July 2026 against property `307716462`. First sync matched
368 of the 500 inventory pages; 612 site-wide pages carry conversions.

## Purpose

GA4 tells us how each page actually behaves: traffic, engagement, and
conversions (sample requests, enquiries). This turns `business_priority` from an
inferred proxy into measurement. Today buyer intent is guessed from page type
(report over case study over article). GA4 replaces the guess with real
behaviour, so a high-converting article can be recognised as valuable even
though its type would suggest otherwise (master PRD section 11.4 names exactly
these signals).

Read-only. The integration uses the `analytics.readonly` scope and never writes
to Google.

## Metrics pulled

Per page path, over a lookback window (default 28 days, ending yesterday):

- sessions
- users
- engaged sessions
- average engagement seconds (total engagement divided by sessions, so pages of
  different traffic compare fairly)
- key events (the property's conversion count)

## Key events must be discovered, not assumed

GA4 has no universal "enquiry" metric; conversions depend on how Ken configured
key events. The connector does not guess names like `sample_request`, which
would silently return zero if the real name differs. Instead, list the actual
key-event names the property reports and map them to business meaning
afterwards:

```powershell
python scripts/20_sync_ga4.py --events
```

This prints each key-event name with its total, so the conversion-to-business
mapping (report enquiry, sample request, consulting enquiry) is built from real
names.

## Path to node mapping

GA4 reports a bare page path; the database keys pages by node_id. The shared
`normalise_url` in `integrations/common.py` reduces both to the same lowercase
path, so a GA4 path and a GSC absolute URL for the same page resolve to one
node. Unmatched rows are stored with `status = 'unmatched'`, not dropped, so the
coverage gap between the full site and the 500-page inventory stays visible.

## Credentials

Shared with Search Console: one file set by `GOOGLE_CREDENTIALS_PATH`, plus
`GA4_PROPERTY_ID` for the numeric property. The property ID is found in GA4
under Admin, Property Settings, and is also visible in the GA4 URL
(`.../aXXXXXXpNNNNNNNNN/...`, the number after `p`). The one-time OAuth login
covers both APIs at once; the token then refreshes silently. See
`config/settings.py` and the Search Console doc for the full credential model.

## Commands

Dry run (fetch and report, no writes):

```powershell
python scripts/20_sync_ga4.py --dry-run
```

List real key-event names:

```powershell
python scripts/20_sync_ga4.py --events
```

Live sync:

```powershell
python scripts/20_sync_ga4.py
```

Data lands in `integration_placeholders` with `source = 'ga4'`. Re-running
replaces that source's rows for the same window.

## Limitations

- The inventory is 500 pages while GA4 covers the whole site, so most returned
  rows are unmatched (stored, not dropped).
- The conversion-to-business-value mapping is not built yet; it needs the real
  key-event names from `--events` and a decision on which events count as a lead.
- Full attribution modelling is out of scope.

## Verification

```powershell
python -m pytest tests/test_integrations.py -q
```

Through the API: `GET /api/integrations/status` shows the connection state and
the number of pages matched.
