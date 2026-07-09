# API Documentation — Ken Intelligence Linking Engine

**Phase 1: Foundation & Data Layer · Phase 2: Intelligence Layer (entities)**
**Base URL:** `http://localhost:8000`
**Interactive docs (Swagger UI):** `http://localhost:8000/docs`

---

## Overview

A read-only REST API over the Phase 1 content inventory database (`ken_links.db`).
It exposes the 500 crawled Ken Research pages, their metrics, and taxonomy lists
so a dashboard (or the future Content Inventory MCP server) can query the data.

All responses are JSON. No authentication is required — the server is intended to
run locally on `localhost` during Phase 1.

### How to start the server

```bash
# From the project root, with the venv active:
python api/main.py

# or explicitly with uvicorn:
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Open
`http://localhost:8000/docs` to try every endpoint from the browser, or open
`http://localhost:8000/dashboard` for the human-readable visual dashboard
(summary cards, industry/country charts, searchable page table — no raw JSON).

---

## Endpoints

### 1. `GET /` — Health Check

Confirms the server is running.

**Parameters:** none

**Example request**
```bash
curl http://localhost:8000/
```

**Example response** — `200 OK`
```json
{
  "status": "ok",
  "message": "Ken Intelligence Linking Engine Phase 1"
}
```

---

### 2. `GET /api/stats` — Database Statistics

Overall metrics for the dashboard summary cards.

**Parameters:** none

**Example request**
```bash
curl http://localhost:8000/api/stats
```

**Example response** — `200 OK`
```json
{
  "total_pages": 500,
  "active_pages": 498,
  "orphan_pages": 354,
  "avg_links_in": 2.0,
  "avg_authority_score": 14.21,
  "response_time_ms": 8.3
}
```

| Field | Meaning |
|-------|---------|
| `total_pages` | Total rows in `content_nodes` |
| `active_pages` | Pages with `status = 'active'` (498 — 2 pages marked `removed`, see below) |
| `orphan_pages` | Pages with `orphan_status = 'orphan'` (0 incoming links) |
| `avg_links_in` | Average `internal_links_in` across all pages |
| `avg_authority_score` | Average `page_authority_score` (0–100) |
| `response_time_ms` | Server-side query time |

> **Data methodology (updated Day 7):**
> `internal_links_in` is measured against evidence from the full kenresearch.com
> sitemap crawl (~36,500 source pages, 86% coverage — snapshot in
> `data/sitewide_incoming_snapshot_v3.json`), not just the 500 sampled URLs.
> `internal_links_out` counts only in-body editorial/related-report links —
> sitewide header, nav and footer links are excluded, and so are template CTA
> and utility links repeated on every report page (`/sample-report/*`,
> `/custom-form/*`, `/talk-to-us`, `/book-a-discovery-call`, `/contact-us`,
> `/about-us`, `/careers`, `/terms-and-conditions`, `/privacy-policy`). Verified
> against a manual count on `qatar-nordic-regulatory-affairs-market` (5 real
> related-report links, script and human agree).
> **Removed-page fix:** 2 report URLs (`middle-east-medical-display-monitors-market`,
> `middle-east-radiation-cured-market`) 301-redirect twice on the live site and
> land on `/report-store`, a page linked from every menu (4,804 incoming links).
> The crawler was inheriting that count onto the dead URLs, which inflated
> `avg_links_in` roughly 10x (21.21 → 2.0 after the fix) and gave them a fake
> "well linked" status. Both are now marked `status='removed'`,
> `orphan_status='removed'`, `internal_links_in=0`, `page_authority_score=0` and
> excluded from `active_pages`. The current top real incoming-link page is
> `uae-digital-advertising-market` with 181.

---

### 3. `GET /api/metrics` — Detailed Metrics

Full database health breakdown in one call — the data source for a metrics/analytics dashboard tab.

**Parameters:** none

**Example request**
```bash
curl http://localhost:8000/api/metrics
```

**Example response** — `200 OK`
```json
{
  "total_pages": 500,
  "active_pages": 498,
  "content_types": { "report": 300, "case_study": 101, "article": 99 },
  "industries": { "Articles": 99, "Healthcare": 65, "...": "..." },
  "countries": { "india": 82, "global": 62, "...": "..." },
  "link_distribution": {
    "internal_links_in": { "avg": 2.0, "min": 0, "max": 181 },
    "internal_links_out": { "avg": 3.05, "min": 0, "max": 16 }
  },
  "orphan_analysis": {
    "orphan": 354, "under_linked": 68, "well_linked": 48, "normal": 28,
    "removed": 2, "orphan_percent": 70.8
  }
}
```

| Field | Meaning |
|-------|---------|
| `content_types` | Row count per `content_type` |
| `industries` | Row count per industry (blank/NULL excluded) |
| `countries` | Row count per country (blank/NULL excluded) |
| `link_distribution` | Avg/min/max for `internal_links_in` and `internal_links_out` |
| `orphan_analysis` | Row count per `orphan_status` (`orphan`, `under_linked`, `normal`, `well_linked`, `removed`), plus `orphan_percent` of total |

---

### 4. `GET /api/pages` — List Pages (Paginated)

Returns pages for dashboard tables. Supports pagination and optional filters.

**Parameters (query string)**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `skip` | int | `0` | Records to skip (offset). Must be ≥ 0. |
| `limit` | int | `50` | Records to return. 1–500. |
| `industry` | string | — | Optional filter, case-insensitive exact match. |
| `country` | string | — | Optional filter, case-insensitive exact match. |
| `content_type` | string | — | Optional filter, case-insensitive exact match (`report`, `article`, `case_study`…). |
| `search` | string | — | Optional substring match against URL and title. |

Results are ordered by `page_authority_score` descending.

**Example requests**
```bash
curl "http://localhost:8000/api/pages?skip=0&limit=10"
curl "http://localhost:8000/api/pages?limit=100"
curl "http://localhost:8000/api/pages?industry=Healthcare&country=india"
curl "http://localhost:8000/api/pages?industry=healthcare&country=India"
curl "http://localhost:8000/api/pages?search=lubricants"
```

> `industry`, `country` and `content_type` are matched case-insensitively — `India`
> and `india` return identical results.

**Example response** — `200 OK`
```json
{
  "total": 500,
  "skip": 0,
  "limit": 50,
  "pages": [
    {
      "node_id": "b85182b1-c8f2-41b7-99b7-0df9c8353259",
      "url": "https://www.kenresearch.com/middle-east-radiation-cured-market",
      "title": "Middle East Radiation Cured Market ...",
      "content_type": "report",
      "industry": "",
      "country": "middle east",
      "region": "mea",
      "orphan_status": "under_linked",
      "internal_links_in": 2,
      "internal_links_out": 5,
      "page_authority_score": 60.0,
      "status": "active"
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `total` | Total matching rows (before pagination) |
| `skip` / `limit` | Echo of the pagination params used |
| `pages[]` | Array of page objects with core metadata |

---

### 5. `GET /api/pages/orphans` — Orphan Pages

Pages with zero incoming internal links — the primary SEO fix list.

> **Important:** This route is registered **before** `/api/pages/{node_id}` so that
> the literal path `orphans` is not mistaken for a page ID.

**Parameters (query string)**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `limit` | int | `100` | Max orphans to return. 1–500. |

**Example request**
```bash
curl "http://localhost:8000/api/pages/orphans?limit=5"
```

**Example response** — `200 OK`
```json
{
  "count": 5,
  "orphans": [
    {
      "node_id": "e6c6a5fd-d243-4534-b56d-26b3e6e59c32",
      "url": "https://www.kenresearch.com/bahrain-gene-synthesis-research-use-market",
      "title": "Bahrain Gene Synthesis Research Use Market Share, Companies & Trends Report 2025-2031",
      "content_type": "report",
      "industry": "Technology & Telecom",
      "country": "bahrain",
      "internal_links_in": 0,
      "internal_links_out": 5,
      "page_authority_score": 55.0
    }
  ]
}
```

---

### 6. `GET /api/pages/{node_id}` — Get Specific Page

Full metadata for a single page. Looks up by `node_id`; if none matches, it falls
back to a partial URL match (so you can pass a URL fragment/slug).

**Parameters (path)**

| Name | Type | Notes |
|------|------|-------|
| `node_id` | string | The `node_id` (UUID) or a URL fragment. |

**Example request**
```bash
curl http://localhost:8000/api/pages/e6c6a5fd-d243-4534-b56d-26b3e6e59c32
```

**Example response** — `200 OK`
Returns the complete `content_nodes` row (all 30 columns) as a JSON object.

**Error response** — `404 Not Found`
```json
{
  "detail": "Page 'zzz-not-a-real-id' not found"
}
```

---

### 7. `GET /api/taxonomy/industries` — Industry List

Unique industries with page counts. Used to populate dashboard filter dropdowns.

**Parameters:** none

**Example request**
```bash
curl http://localhost:8000/api/taxonomy/industries
```

**Example response** — `200 OK`
```json
{
  "count": 19,
  "industries": [
    { "name": "Articles", "page_count": 99 },
    { "name": "Healthcare", "page_count": 65 },
    { "name": "Automotive, Transportation & Logistics", "page_count": 55 },
    { "name": "Technology & Telecom", "page_count": 47 }
  ]
}
```

Blank/NULL industries are excluded. Ordered by `page_count` descending.

---

### 8. `GET /api/taxonomy/countries` — Country List

Unique countries with page counts. Used to populate dashboard filter dropdowns.

**Parameters:** none

**Example request**
```bash
curl http://localhost:8000/api/taxonomy/countries
```

**Example response** — `200 OK`
```json
{
  "count": 43,
  "countries": [
    { "name": "india", "page_count": 82 },
    { "name": "global", "page_count": 62 },
    { "name": "saudi arabia", "page_count": 54 },
    { "name": "vietnam", "page_count": 26 }
  ]
}
```

Blank/NULL countries are excluded. Ordered by `page_count` descending.

---

### 9. `GET /docs` — Swagger UI

Interactive API documentation, generated automatically by FastAPI. Open it in a
browser to try every endpoint live. A raw OpenAPI schema is also available at
`GET /openapi.json`.

---

### 10. `GET /dashboard` — Visual Dashboard

Serves `dashboard/index.html` — a self-contained, no-build human-readable view
of the same data, built for non-technical reviewers (managers, SEO/content
team) who should never need to read raw JSON.

**Sections:**
- Summary cards — total pages, pages needing links, avg incoming/outgoing links, avg authority score
- Pages by Industry / Pages by Country — bar charts (top 10 each)
- Link Health strip — plain-English counts: "No Links Found", "Few Links", "Good", "Well Linked"
- Searchable, filterable, paginated page table (industry, country, content type, link status, free-text search)

Calls `/api/stats`, `/api/metrics`, `/api/taxonomy/industries`, `/api/taxonomy/countries`
and `/api/pages` from the browser — no server-side templating, so it always reflects
whatever is currently in `ken_links.db`.

---

---

## Phase 2 — Entity Intelligence Endpoints

Added Day 5 (July 9, 2026). All read-only, same `ken_links.db`. These expose
the entities Agent 2 extracted (market, country, region, industry, time
period) and the page-to-entity mappings, including confidence scores and the
manual-correction status (`extracted` / `approved` / `corrected` / `rejected`
— see `docs/09-AGENTS/02-ENTITY-CORRECTION-WORKFLOW.md`).

> **Note:** browse/list/taxonomy endpoints only return entities with at least
> one non-rejected page mapping (`page_count > 0`). An entity whose every
> mapping has been rejected (e.g. a bad extraction fully corrected away)
> still exists in the database for audit purposes and is still reachable by
> direct ID via `GET /api/entities/{entity_id}` — it just won't clutter
> browsing/search results.

### 11. `GET /api/entities` — List Entities (Paginated, Filterable)

**Parameters (query string)**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `skip` | int | `0` | Records to skip |
| `limit` | int | `50` | Records to return, 1–500 |
| `entity_type` | string | — | `industry` \| `country` \| `region` \| `market` \| `time_period` |
| `search` | string | — | Substring match against entity name |

Ordered by `page_count` descending (most-referenced entities first).

**Example request**
```bash
curl "http://localhost:8000/api/entities?entity_type=market&limit=5"
```

**Example response** — `200 OK`
```json
{
  "total": 373,
  "skip": 0,
  "limit": 5,
  "entities": [
    {
      "entity_id": "97456175-afd2-42a2-8678-88d9683aa3bc",
      "entity_name": "Lubricants Market",
      "entity_type": "market",
      "normalized_name": "lubricant market",
      "industry": "Automotive, Transportation & Logistics",
      "country": "nigeria",
      "region": "Africa",
      "confidence_score": 0.9,
      "page_count": 4
    }
  ]
}
```

---

### 12. `GET /api/entities/low-confidence` — Manual Review Queue

Mappings below a confidence threshold that still await review
(`status = 'extracted'`), least confident first. This is the same list
`scripts/10_entity_corrections.py list-low-confidence` exports to CSV.

> **Registered before `/api/entities/{entity_id}`** so the literal path
> `low-confidence` is never mistaken for an entity ID.

**Parameters (query string)**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `threshold` | float | `0.70` | Confidence cutoff, 0.0–1.0 |
| `limit` | int | `200` | Max mappings to return, 1–1000 |

**Example request**
```bash
curl "http://localhost:8000/api/entities/low-confidence?threshold=0.7"
```

**Example response** — `200 OK`
```json
{
  "threshold": 0.7,
  "count": 42,
  "mappings": [
    {
      "node_entity_id": "6e4f48c2-...",
      "url": "https://www.kenresearch.com/...",
      "entity_type": "market",
      "entity_name": "...",
      "entity_role": "primary_market",
      "source_field": "title",
      "extracted_value": "...",
      "normalized_value": "...",
      "confidence_score": 0.65,
      "extraction_method": "pattern",
      "status": "extracted"
    }
  ]
}
```

---

### 13. `GET /api/entities/{entity_id}` — Entity Detail

One entity plus every page mapped to it, most confident match first.

**Example request**
```bash
curl http://localhost:8000/api/entities/97456175-afd2-42a2-8678-88d9683aa3bc
```

**Example response** — `200 OK`
```json
{
  "entity_id": "97456175-...", "entity_name": "Lubricants Market",
  "entity_type": "market", "confidence_score": 0.9,
  "pages": [
    { "node_id": "...", "url": "...", "title": "...", "content_type": "report",
      "entity_role": "primary_market", "confidence_score": 0.9, "status": "extracted" }
  ],
  "page_count": 4
}
```

**Error response** — `404 Not Found` if the entity_id doesn't exist.

---

### 14. `GET /api/pages/{node_id}/entities` — Entities of One Page

Every entity extracted for a page, most confident first.

**Example request**
```bash
curl http://localhost:8000/api/pages/{node_id}/entities
```

**Example response** — `200 OK`
```json
{
  "node_id": "...", "url": "https://www.kenresearch.com/bahrain-pectin-market",
  "title": "Bahrain Pectin Market Share, Companies & Trends Report 2025-2031",
  "entities": [
    { "entity_id": "...", "entity_name": "Metal, Mining and Chemicals", "entity_type": "industry",
      "entity_role": "primary_industry", "source_field": "db_industry",
      "confidence_score": 0.95, "extraction_method": "exact_field", "status": "extracted" },
    { "entity_name": "Bahrain", "entity_type": "country", "confidence_score": 0.95, "...": "..." },
    { "entity_name": "Middle East", "entity_type": "region", "confidence_score": 0.9, "...": "..." },
    { "entity_name": "Pectin Market", "entity_type": "market", "confidence_score": 0.9, "...": "..." },
    { "entity_name": "2025-2031", "entity_type": "time_period", "confidence_score": 0.85, "...": "..." }
  ],
  "entity_count": 5
}
```

**Error response** — `404 Not Found` if the node_id doesn't exist.

---

### 15. `GET /api/taxonomy/markets` — Market List

Every distinct market entity with its page count. Same shape as the Phase 1
industry/country taxonomy endpoints.

```bash
curl http://localhost:8000/api/taxonomy/markets
```
```json
{ "count": 373, "markets": [
  { "name": "Lubricants Market", "entity_id": "97456175-...", "page_count": 4 }
] }
```

---

### 16. `GET /api/taxonomy/regions` — Region List

```bash
curl http://localhost:8000/api/taxonomy/regions
```
```json
{ "count": 7, "regions": [
  { "name": "Asia Pacific", "entity_id": "fbead603-...", "page_count": 200 },
  { "name": "Middle East", "entity_id": "22cebe82-...", "page_count": 182 },
  { "name": "Global", "entity_id": "e913dddb-...", "page_count": 54 },
  { "name": "North America", "entity_id": "5bfe56e6-...", "page_count": 35 },
  { "name": "Europe", "entity_id": "8af1c3e7-...", "page_count": 18 },
  { "name": "Africa", "entity_id": "a8833686-...", "page_count": 6 },
  { "name": "Latin America", "entity_id": "774e30c2-...", "page_count": 3 }
] }
```

---

### 17. `GET /api/intelligence/entity-coverage` — Coverage Summary

The single call that answers "how good is our entity data?" — backs the
Phase 2 coverage report and the future Intelligence Dashboard.

```bash
curl http://localhost:8000/api/intelligence/entity-coverage
```
```json
{
  "active_pages": 498,
  "coverage": {
    "pages_with_any_entity": { "count": 498, "pct": 100.0, "target_pct": 95.0 },
    "pages_with_geography": { "count": 498, "pct": 100.0, "target_pct": 90.0 },
    "pages_with_industry_or_market": { "count": 465, "pct": 93.4, "target_pct": 80.0 },
    "pages_with_market": { "count": 397, "pct": 79.7 }
  },
  "unique_entities_by_type": { "market": 374, "country": 34, "industry": 14, "region": 7, "time_period": 6 },
  "mapping_confidence_bands": { "high_0.9_plus": 1509, "good_0.7_to_0.9": 349, "review_0.5_to_0.7": 46 },
  "mapping_statuses": { "extracted": 1900, "rejected": 4 }
}
```

---

## Status & Error Codes

| Code | When |
|------|------|
| `200 OK` | Successful request |
| `404 Not Found` | `/api/pages/{node_id}` with no matching page |
| `422 Unprocessable Entity` | Invalid query params (e.g. `limit` out of the 1–500 range) |

---

## Verified Test Results (Day 7)

All endpoints re-tested locally after the Day 7 fixes (case-insensitive filters,
`search` filter, `/api/metrics`, corrected link-count data):

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /` | 200 | Health check |
| `GET /api/stats` | 200 | `orphan_pages: 354`, `avg_links_in: 2.0` |
| `GET /api/metrics` | 200 | New — full breakdown, includes `link_distribution` and `orphan_analysis` |
| `GET /dashboard` | 200 | New — visual HTML dashboard, no raw JSON |
| `GET /api/pages` | 200 (50 pages) | |
| `GET /api/pages?industry=Healthcare&country=India` | 200 | Same result as lowercase `healthcare`/`india` |
| `GET /api/pages?search=lubricants` | 200 | Substring match against URL and title |
| `GET /api/pages/{node_id}` | 200 | |
| `GET /api/pages/orphans` | 200 | |
| `GET /api/taxonomy/industries` | 200 (19 items) | Was 21 — 2 duplicate/non-standard values normalized |
| `GET /api/taxonomy/countries` | 200 (43 items) | |
| `GET /docs` | 200 | |
| `GET /api/pages/{bad-id}` | 404 (expected) | |

All endpoints responded in well under the 500 ms target throughout testing.

---

## Verified Test Results — Phase 2 Entity Endpoints (Day 5, July 9)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/entities` | 200 | 373 markets found via `entity_type` filter |
| `GET /api/entities?search=...` | 200 | Substring match on name |
| `GET /api/entities/low-confidence` | 200 | Confirmed no path collision with `/api/entities/{id}` |
| `GET /api/entities/{entity_id}` | 200 / 404 | Both cases verified |
| `GET /api/pages/{node_id}/entities` | 200 / 404 | Both cases verified |
| `GET /api/taxonomy/markets` | 200 | 373 items, all `page_count > 0` |
| `GET /api/taxonomy/regions` | 200 | 7 items |
| `GET /api/intelligence/entity-coverage` | 200 | Bug found + fixed during this verification pass (see below) |

**2 real bugs found and fixed during this verification pass** (not fixed by
writing tests after the fact — found *by* running the endpoints against live
data, which is why every agent/endpoint in this project ships with a
live-verification step before being marked done):

1. **`/api/intelligence/entity-coverage` crashed** with `Cannot operate on a
   closed database` — the DB connection was closed one line before three
   queries that still needed it. Fixed by reordering.
2. **4 pages had a corrupted market entity** ("nan Market") traced to a
   Phase 1 data bug: the literal string `"nan"` (a pandas NaN artifact)
   leaked into 4 pages' `title` field. Agent 2 was extracting "nan Market" as
   if "nan" were a real word. Fixed in two places: `extract_market_from_title`
   now rejects a `nan`-prefixed title outright, and Agent 2 now falls back to
   H1 when title extraction fails — recovering the real market name
   (`Ulcerative Colitis Market`, `Smart Card Materials Market`, etc.) instead
   of losing the page's market entirely. The 4 stale wrong mappings were
   marked `rejected` via the correction workflow (not deleted — audit trail
   preserved) and Agent 2 was re-run to create the correct mappings.

9 automated tests added in `tests/test_api_entities.py` lock in both fixes as
regressions.
