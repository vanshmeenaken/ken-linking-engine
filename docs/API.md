# API Documentation — Ken Intelligence Linking Engine

**Phase 1: Foundation & Data Layer**
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
  "avg_authority_score": 11.53,
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
