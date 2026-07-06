# Deployment Guide — Scaling Beyond Phase 1

Phase 1 was deliberately built as a local, single-file, no-infrastructure
system: SQLite, no auth, `localhost` only. This document covers what changes
before this goes anywhere beyond one developer's laptop.

---

## 1. Database: SQLite → PostgreSQL

**Why it matters now:** SQLite locks the whole database file for writes,
which is fine for one agent run at a time but will not hold up once multiple
agents (Phase 2's Entity Extraction, Relationship Mapping, etc.) need to
write concurrently, or once the API needs to serve traffic while an agent is
mid-run.

**Migration approach:**
1. Keep `database/models.py` as the schema source of truth — the SQLAlchemy
   models are already database-agnostic; only `DATABASE_URL` needs to change
   (`config/settings.py` already reads it from an environment variable):
   ```
   DATABASE_URL=postgresql://user:password@host:5432/ken_links
   ```
2. `api/main.py` currently uses raw `sqlite3` directly, not SQLAlchemy — this
   will need to be rewritten to use SQLAlchemy sessions (or `psycopg2`
   directly) before it can point at PostgreSQL. This is the single biggest
   code change required for this migration.
3. `agents/agent_1_content_inventory.py` also uses raw `sqlite3` for its
   `update_database()` method — same rewrite needed.
4. Export existing data first: `sqlite3 ken_links.db .dump > backup.sql`,
   then adapt for PostgreSQL syntax (types, `AUTOINCREMENT` vs `SERIAL`, etc.)
   or simply re-run the pipeline fresh against the new database (Day 8
   proved this is fully reproducible).

---

## 2. Environment Variables for Production

Current `.env` variables (see `.env.example`):

```
NVIDIA_API_KEY=...          # used by Agent 1 for case-study industry classification
DATABASE_URL=...            # sqlite:///ken_links.db by default; override for Postgres
API_HOST=0.0.0.0
API_PORT=8000
```

**For production:**
- Never commit `.env` — already gitignored, confirm this stays true
- `NVIDIA_API_KEY` is a paid/rate-limited credential — a production deployment
  running many agents concurrently will need to either request a higher rate
  limit or add request queuing (Agent 1 already has a 2-second inter-call
  lock and exponential backoff for this reason — see
  `_AI_CLASSIFY_LOCK` / `_AI_MIN_INTERVAL` in `agent_1_content_inventory.py`)
- `API_HOST=0.0.0.0` means the server listens on all interfaces — fine behind
  a reverse proxy / firewall, not fine exposed directly to the internet
  without authentication (see Security section below)

---

## 3. Security Before Any Non-Local Deployment

Phase 1 has **no authentication** — this was an explicit, acceptable
trade-off only because the server only ever ran on `localhost`. Before
deploying anywhere reachable by anyone other than the developer:

- Add an authentication layer (API key header, at minimum) to `api/main.py`
- Put the API behind a reverse proxy (nginx, Caddy) with TLS — do not serve
  raw HTTP from uvicorn directly to the internet
- Rate-limit the API itself, not just the outbound crawl — the current API
  has no request throttling
- Review CORS — none is currently configured, meaning the dashboard only
  works because it's served from the same origin as the API; a separately
  hosted frontend would need explicit CORS configuration

---

## 4. Performance Tuning Notes

From Day 8 load testing (see `docs/PERFORMANCE_REPORT.md`):

- Current API handles 50 concurrent requests at ~225ms average with zero
  failures — this is comfortable headroom for a single-user local tool, but
  has not been tested beyond 50 concurrent, and SQLite's single-writer lock
  will become the real ceiling once write volume increases
- Agent 1 at 5 workers takes ~4.7 minutes for 500 URLs. Ken's server
  rate-limits above roughly 5–8 concurrent connections — this is an external
  constraint, not something more application code can fix. Do not raise
  worker count expecting proportional speedup; it produces failures instead
- The sitewide incoming-link collector
  (`scripts/05_collect_sitewide_links.py`) is the expensive operation —
  crawling ~40,000 pages takes hours even at 25–40 workers, and needs
  `--retry-from` passes to reach high coverage. Budget for this to run as an
  overnight/scheduled job, not on-demand

---

## 5. Monitoring & Logging

**Currently exists:**
- `crawl_logs` table — records every load/enrichment operation with
  timestamp, status, and notes
- Console output from each script (progress percentages, error messages)
- JSON reports written to `reports/content_inventory_<timestamp>.json` per
  Agent 1 run

**Missing for production:**
- No centralized log aggregation (all logging is print statements /
  in-memory `logging` module output to console)
- No alerting on agent failure or data quality regression
- No dashboard for the `crawl_logs` history itself (only the content data has
  a dashboard)

Recommendation: before scaling to more agents, route logging through a
structured logger (e.g. `structlog`) writing to a file or log aggregation
service, and add a simple check (cron + script) that fails loudly if
`scripts/03_validate_data.py`'s quality score drops below 80%.

---

## 6. What's Next: Phase 2 and Beyond

Phase 1 delivered the foundation (`content_nodes` populated, classified, and
scored). The full system described in the source-of-truth PRD calls for 14
agents and 12 MCP servers total. Only Agent 1 (Content Inventory) is built.

**Phase 2 — Intelligence Layer (not started):**
- Agent 2: Entity Extraction → populates `content_entities`
- Agent 3: Relationship Mapping → populates `relationship_edges`
- Agent 4: SEO Opportunity Agent
- Agent 5: Business Priority Agent
- Semantic embeddings (vector DB — Supabase/pgvector per the original plan)

**Phases 3–6** (Recommendation Engine, Deployment Workflow, Evidence &
Report Intelligence, Learning Loop) depend on Phase 2's knowledge graph
existing first — see `source_of_truth/Ken_Intelligence_Linking_PRD_Summary.md`
for the full roadmap.

**Immediate technical debt to resolve before Phase 2 starts:**
1. Consolidate the two Python environments into one `requirements.txt`
2. Migrate `api/main.py` and `agent_1_content_inventory.py` off raw
   `sqlite3` if/when the Postgres migration happens
3. Decide on the vector database approach for Phase 2 embeddings before
   Agent 2 is built, since entity extraction and semantic search are tightly
   coupled in the original design
