# Content Inventory Agent

## Purpose

Agent 1 enriches the 500-page `content_nodes` inventory from live Ken Research
HTML and official sitemap evidence. It does not invent page metadata or link
counts. Network collection completes before the database transaction begins.

## Collected fields

- Canonical URL, final URL and HTTP status
- Page title, meta description and H1
- Content type
- Indexability status
- Structural URL depth
- Unique outgoing Ken Research links
- Unique incoming source pages
- Link-status band
- Page-authority score

## Metric definitions

`crawl_depth` is the number of URL path segments, matching the Day 4 task
example. It is not a homepage breadth-first-search distance.

`internal_links_out` counts unique Ken Research URLs found in the page's live
HTML. Query parameters and fragments are removed before counting.

`internal_links_in` uses unique source pages across the official Ken Research
sitemaps when a site-wide snapshot is supplied. Without a snapshot, it is
scoped to the pages in the current Agent 1 run.

`orphan_status` uses these bands:

- `orphan`: 0 incoming links
- `under_linked`: 1-2 incoming links
- `normal`: 3-5 incoming links
- `well_linked`: 6 or more incoming links

`page_authority_score` is a reproducible 0-100 score. Incoming links contribute
80 percent and outgoing links contribute 20 percent. Both components are
log-normalized against the current batch maximum.

## Safety

- `--dry-run` performs collection and calculation without database writes.
- Only successful pages are eligible for updates.
- Updates and audit-log inserts use one SQLite transaction.
- Any SQL failure rolls back the entire transaction.
- Failed pages remain unchanged and are listed in the JSON report.

## Commands

Install dependencies:

```powershell
pip install -r requirements.txt
```

Required 50-page QA run:

```powershell
python agents/agent_1_content_inventory.py --limit 50 --dry-run
```

Collect reusable site-wide incoming-link evidence:

```powershell
python scripts/05_collect_sitewide_links.py --workers 50
```

Run all 500 pages with the verified snapshot:

```powershell
python agents/agent_1_content_inventory.py `
  --workers 50 `
  --incoming-snapshot data/sitewide_incoming_snapshot.json
```

Apply an already verified 500-page evidence report in under 60 seconds without
repeating network collection:

```powershell
python agents/agent_1_content_inventory.py `
  --apply-report reports/content_inventory_500_dry_run.json `
  --incoming-snapshot data/sitewide_incoming_snapshot.json
```

The cached path still performs all classifications, status assignments,
authority calculations and database updates in a single transaction. Only the
slow network evidence collection is reused.

## Verification

Run the automated logic tests:

```powershell
python -m pytest tests/test_content_inventory_agent.py -q
```

Run the existing data-quality report after enrichment:

```powershell
python scripts/03_validate_data.py
```

The JSON execution report records methodology, coverage, failures, runtime and
page-level evidence for independent QA.
