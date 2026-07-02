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
`http://localhost:8000/docs` to try every endpoint from the browser.

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
  "active_pages": 500,
  "orphan_pages": 493,
  "avg_links_in": 1.01,
  "avg_authority_score": 19.25,
  "response_time_ms": 18.4
}
```

| Field | Meaning |
|-------|---------|
| `total_pages` | Total rows in `content_nodes` |
| `active_pages` | Pages with `status = 'active'` |
| `orphan_pages` | Pages with `orphan_status = 'orphan'` (0 incoming links) |
| `avg_links_in` | Average `internal_links_in` across all pages |
| `avg_authority_score` | Average `page_authority_score` (0–100) |
| `response_time_ms` | Server-side query time |

> **Note:** `orphan_pages` is high (493) because the Phase 1 link graph is scoped
> only to the 500 sampled URLs. Most pages' real incoming links come from pages
> outside the sample. This is a data-scope characteristic of Agent 1, not an API defect.

---

### 3. `GET /api/pages` — List Pages (Paginated)

Returns pages for dashboard tables. Supports pagination and optional filters.

**Parameters (query string)**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `skip` | int | `0` | Records to skip (offset). Must be ≥ 0. |
| `limit` | int | `50` | Records to return. 1–500. |
| `industry` | string | — | Optional exact-match filter. |
| `country` | string | — | Optional exact-match filter. |
| `content_type` | string | — | Optional exact-match filter (`report`, `article`, `case_study`…). |

Results are ordered by `page_authority_score` descending.

**Example requests**
```bash
curl "http://localhost:8000/api/pages?skip=0&limit=10"
curl "http://localhost:8000/api/pages?limit=100"
curl "http://localhost:8000/api/pages?industry=Healthcare&country=india"
```

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
      "orphan_status": "orphan",
      "internal_links_in": 0,
      "internal_links_out": 45,
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

### 4. `GET /api/pages/orphans` — Orphan Pages

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
      "internal_links_out": 42,
      "page_authority_score": 55.0
    }
  ]
}
```

---

### 5. `GET /api/pages/{node_id}` — Get Specific Page

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

### 6. `GET /api/taxonomy/industries` — Industry List

Unique industries with page counts. Used to populate dashboard filter dropdowns.

**Parameters:** none

**Example request**
```bash
curl http://localhost:8000/api/taxonomy/industries
```

**Example response** — `200 OK`
```json
{
  "count": 21,
  "industries": [
    { "name": "Articles", "page_count": 99 },
    { "name": "Healthcare", "page_count": 64 },
    { "name": "Automotive, Transportation & Logistics", "page_count": 55 },
    { "name": "Technology & Telecom", "page_count": 47 }
  ]
}
```

Blank/NULL industries are excluded. Ordered by `page_count` descending.

---

### 7. `GET /api/taxonomy/countries` — Country List

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

### 8. `GET /docs` — Swagger UI

Interactive API documentation, generated automatically by FastAPI. Open it in a
browser to try every endpoint live. A raw OpenAPI schema is also available at
`GET /openapi.json`.

---

## Status & Error Codes

| Code | When |
|------|------|
| `200 OK` | Successful request |
| `404 Not Found` | `/api/pages/{node_id}` with no matching page |
| `422 Unprocessable Entity` | Invalid query params (e.g. `limit` out of the 1–500 range) |

---

## Verified Test Results (Day 6)

All endpoints tested locally against the 500-URL database:

| Endpoint | Status | Response time |
|----------|--------|---------------|
| `GET /` | 200 | ~28 ms |
| `GET /api/stats` | 200 | ~30 ms |
| `GET /api/pages` | 200 (50 pages) | ~57 ms |
| `GET /api/pages?limit=100` | 200 (100 pages) | — |
| `GET /api/pages/{node_id}` | 200 | ~33 ms |
| `GET /api/pages/orphans` | 200 | ~71 ms |
| `GET /api/taxonomy/industries` | 200 (21 items) | ~28 ms |
| `GET /api/taxonomy/countries` | 200 (43 items) | ~29 ms |
| `GET /docs` | 200 | ~27 ms |
| `GET /api/pages/{bad-id}` | 404 (expected) | — |

All response times are well under the 500 ms target.
