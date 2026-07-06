# Architecture — Ken Intelligence Linking Engine (Phase 1)

**Status:** Phase 1: Foundation & Data Layer — complete
**Last updated:** July 6, 2026

---

## System Overview

Phase 1 builds the foundation layer of the Ken Intelligence Linking Engine: a
crawl-and-classify pipeline that turns a flat list of 500 Ken Research URLs
into a structured, queryable content inventory with real link-graph metrics.

```
scripts/sample_urls.csv (500 seed URLs)
        │
        ▼
scripts/01_setup_db.py ──► ken_links.db (SQLite, 4 tables, schema only)
        │
        ▼
scripts/02_load_urls.py ──► content_nodes populated (500 rows, minimal fields)
        │
        ▼
scripts/05_collect_sitewide_links.py ──► data/sitewide_incoming_snapshot_v3.json
  (crawls ~36,500 real kenresearch.com pages to find who really links to our 500)
        │
        ▼
agents/agent_1_content_inventory.py ──► content_nodes enriched
  (title, H1, industry, content_type, canonical_url, crawl_depth,
   internal_links_in/out, orphan_status, page_authority_score)
        │
        ▼
scripts/03_validate_data.py ──► data quality score (currently 95.0%)
        │
        ▼
api/main.py (FastAPI) ──► REST endpoints over ken_links.db
        │
        ├──► /docs        (Swagger UI — technical testing)
        └──► /dashboard   (dashboard/index.html — human-readable view)
```

---

## Components

### 1. Database Layer — SQLite (`ken_links.db`)
Schema defined via SQLAlchemy models in `database/models.py`, created by
`scripts/01_setup_db.py`. Four tables:

- **`content_nodes`** — the core table. One row per Ken Research page. Holds
  URL, canonical URL, title/meta/H1, content type, industry/country,
  crawl depth, link counts, orphan status, authority score, and lifecycle
  `status` (`active` / `removed`).
- **`content_entities`** — extracted entities (market, industry, country,
  company, etc.). Schema exists; population is Phase 2 (Agent 2, not yet
  built).
- **`relationship_edges`** — typed relationships between content nodes
  (parent-child, same-market, case-study-supports-report, etc.). Schema
  exists; population is Phase 2 (Agent 3, not yet built).
- **`crawl_logs`** — audit trail of every load/enrichment operation run
  against a URL.

Both `01_setup_db.py` and the API layer read `DATABASE_URL` from
`config/settings.py` (defaults to `sqlite:///ken_links.db`), so the database
location can be overridden via an environment variable without touching code
— this is how Day 8's fresh-rebuild test was run safely against a throwaway
file instead of the live database.

### 2. Agent Layer — Content Inventory Agent (`agents/agent_1_content_inventory.py`)
A single Python class, `ContentInventoryAgent`, that:

1. Loads all rows from `content_nodes`
2. Crawls each live URL (5 concurrent workers by default — deliberately
   conservative, since Ken's server rate-limits aggressive crawling)
3. Extracts title, meta description, H1, canonical URL, content type,
   industry (via breadcrumb parsing for reports, AI classification via
   NVIDIA NIM for case studies)
4. Counts **outgoing** links — real editorial/related-report links only.
   Sitewide chrome (header, nav, footer) and template CTA/utility links
   (`/sample-report/*`, `/talk-to-us`, `/contact-us`, etc.) are explicitly
   excluded so the count reflects genuine contextual linking, not template
   noise
5. Detects **hub redirects** — a report that's been discontinued and now
   301-redirects to a generic hub page (e.g. `/report-store`) is flagged
   `status='removed'` so it never inherits that hub's own huge sitewide
   incoming-link count
6. Computes **incoming** links two ways:
   - Scoped to the 500-page sample (always computed)
   - From a sitewide evidence snapshot (`--incoming-snapshot`), built by
     crawling the real kenresearch.com sitemap (~36,500 pages,
     `scripts/05_collect_sitewide_links.py`) — this is what's actually used,
     since scoping to only 500 pages made almost everything look like a
     false orphan
7. Calculates `page_authority_score` (0–100): 80% weight on incoming links,
   20% on outgoing, using log-scaled normalization against the batch maximum
8. Writes everything back to `content_nodes` in a single transaction

Run via CLI: `python agents/agent_1_content_inventory.py --workers N
--incoming-snapshot data/sitewide_incoming_snapshot_v3.json`

### 3. API Layer — FastAPI (`api/main.py`)
A read-only REST API, raw `sqlite3` (no ORM at the API layer — SQLAlchemy is
only used for schema creation). All filters use parameterized queries and
case-insensitive matching (`LOWER(col) = LOWER(?)`).

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Health check |
| `GET /api/stats` | Summary metrics |
| `GET /api/metrics` | Full breakdown: content types, industries, countries, link distribution, orphan analysis |
| `GET /api/pages` | Paginated, filterable page list (`industry`, `country`, `content_type`, `search`) |
| `GET /api/pages/orphans` | Pages with zero incoming links |
| `GET /api/pages/{node_id}` | Single page detail, by ID or URL fragment |
| `GET /api/taxonomy/industries` | Industry list + counts |
| `GET /api/taxonomy/countries` | Country list + counts |
| `GET /docs` | Swagger UI (auto-generated) |
| `GET /dashboard` | Visual dashboard |

Full request/response examples: `docs/API.md`.

### 4. Dashboard Layer (`dashboard/index.html`)
A single self-contained HTML file (no build step, no framework) served at
`/dashboard`. Fetches from the same API endpoints via browser `fetch()` and
renders: summary cards, industry/country bar charts, a link-health status
strip in plain English, and a searchable/filterable/paginated page table.
Built specifically so non-technical reviewers never need to read raw JSON.

### 5. CLI Interface
All scripts are plain `python script.py` invocations — no packaging, no
orchestration framework at this stage. Two Python environments are in use:

- **Global Python** (`python`) — has `openai`, `beautifulsoup4`, `requests`,
  `python-dotenv` for the crawling/classification agent
- **venv Python** (`venv\Scripts\python.exe`) — has `sqlalchemy`, `fastapi`,
  `uvicorn` for schema setup and the API server

See `docs/TROUBLESHOOTING.md` if a script fails with `ModuleNotFoundError` —
it is very likely being run with the wrong interpreter.

---

## Data Flow (End-to-End)

```
1. scripts/sample_urls.csv          → 500 seed URLs, minimal metadata
2. 01_setup_db.py                    → empty ken_links.db, schema only
3. 02_load_urls.py                   → 500 rows in content_nodes (title/type/industry/country only)
4. 05_collect_sitewide_links.py      → sitewide_incoming_snapshot_v3.json (real incoming-link evidence)
5. agent_1_content_inventory.py      → content_nodes enriched (title, H1, industry, links, scores)
6. 03_validate_data.py               → data quality report (95.0%)
7. api/main.py (FastAPI)             → REST layer over the enriched database
8. dashboard/index.html              → human-readable view over the REST layer
```

Steps 1–3 only need to run once (or when the seed URL list changes). Step 4
(sitewide crawl) is expensive (~40k pages) and is re-run periodically, not
per-agent-run. Step 5 (Agent 1) is safe to re-run any time — it only updates
existing rows, never deletes, and is idempotent (verified in Day 8 testing:
re-running it twice produced identical results).

---

## Module Dependencies

```
agents/agent_1_content_inventory.py
  ├── requires: requests, beautifulsoup4, openai (NVIDIA NIM client), python-dotenv
  └── writes to: ken_links.db (via sqlite3, no ORM)

api/main.py
  ├── requires: fastapi, uvicorn
  ├── reads from: ken_links.db (via sqlite3, no ORM)
  └── serves: dashboard/index.html (static file)

database/db.py, database/models.py
  ├── requires: sqlalchemy
  └── used only by: scripts/01_setup_db.py (schema creation)

scripts/02_load_urls.py
  └── reads: scripts/sample_urls.csv → writes: ken_links.db (via sqlite3)

scripts/03_validate_data.py
  └── reads: ken_links.db → produces: console quality report

scripts/05_collect_sitewide_links.py
  ├── requires: requests, beautifulsoup4
  ├── reads: ken_links.db (target URL list only)
  └── writes: data/sitewide_incoming_snapshot_v*.json (does not modify the DB)
```

---

## Known Architectural Limitations (Phase 1 scope)

- **SQLite, single file** — fine for 500 rows and one developer; Phase 2+
  should move to PostgreSQL per the original roadmap once concurrent
  writes/agents are introduced.
- **No `content_entities` / `relationship_edges` population yet** — schema
  exists, but Agents 2 (Entity Extraction) and 3 (Relationship Mapping) are
  Phase 2 work, not built in Phase 1.
- **Two Python environments** — a consequence of incremental setup, not a
  deliberate design choice. A production handoff should consolidate into one
  `requirements.txt` / one venv.
- **No authentication** — acceptable for a `localhost`-only Phase 1 tool; not
  acceptable if ever exposed beyond localhost.
