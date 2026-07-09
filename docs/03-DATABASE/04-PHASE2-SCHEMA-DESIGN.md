# Phase 2 Schema Design

**Date:** July 7, 2026 (Day 1 of Phase 2)
**Status:** Design locked — implementation is Day 2 (`scripts/09_phase2_migration.py`)
**Baseline:** see `reports/PHASE2_DAY1_BASELINE_AUDIT.md`

---

## Design Principles

1. **Additive only.** No existing Phase 1 table or column is altered or dropped. All Phase 2 work is new tables + populating already-existing empty columns.
2. **Idempotent migration.** `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` throughout — the migration script is safe to re-run.
3. **Backup before write.** The migration script copies `ken_links.db` to `ken_links_backup_phase2_<timestamp>.db` before touching anything. Rollback = restore the copy.
4. **Score convention.** All *new* confidence/score columns are `REAL` in **0.0–1.0**. The existing `page_authority_score` (0–100) is grandfathered and stays as-is; anything derived from it normalizes to 0–1 at read time.
5. **SQLAlchemy kept in sync.** Every new table gets a model class in `database/models.py` in the same Day 2 commit (Phase 2 technical requirement). Runtime writes still use raw `sqlite3` like Agent 1, models are schema documentation + test fixtures.
6. **UUID string PKs** for new entity-layer tables (matches `content_nodes.node_id` / `content_entities.entity_id` convention). Log tables use `INTEGER AUTOINCREMENT` (matches `crawl_logs`).
7. **ISO-8601 UTC strings** for all timestamps (existing convention).

---

## New Tables (5)

### 1. `node_entities` — page-to-entity mapping (the core Phase 2 join table)

```sql
CREATE TABLE IF NOT EXISTS node_entities (
    node_entity_id   TEXT PRIMARY KEY,                -- uuid4
    node_id          TEXT NOT NULL REFERENCES content_nodes(node_id),
    entity_id        TEXT NOT NULL REFERENCES content_entities(entity_id),
    entity_role      TEXT NOT NULL,                   -- see roles below
    source_field     TEXT,                            -- url_slug | title | h1 | meta_description | db_industry | db_country
    extracted_value  TEXT,                            -- raw text as found (preserved for corrections)
    normalized_value TEXT,                            -- post-normalization value
    confidence_score REAL DEFAULT 0.0,                -- 0.0-1.0
    extraction_method TEXT,                           -- exact_field | pattern | alias | inferred
    status           TEXT DEFAULT 'extracted',        -- extracted | approved | corrected | rejected
    created_at       TEXT,
    updated_at       TEXT,
    UNIQUE (node_id, entity_id, entity_role)          -- duplicate-mapping prevention
);
```

Entity roles (from plan): `primary_industry`, `secondary_industry`, `primary_market`, `secondary_market`, `country`, `region`, `segment`, `product`, `technology`, `service_intent`, `buyer_persona`, `time_period`.

Indexes: `node_id`, `entity_id`, `status`, `confidence_score`.

### 2. `entity_extraction_logs` — Agent 2 run audit

```sql
CREATE TABLE IF NOT EXISTS entity_extraction_logs (
    log_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id               TEXT NOT NULL,               -- one uuid per agent run
    node_id              TEXT REFERENCES content_nodes(node_id),
    operation            TEXT,                        -- entity_extraction | normalization | correction
    status               TEXT,                        -- success | failed | skipped
    entities_found       INTEGER DEFAULT 0,
    low_confidence_count INTEGER DEFAULT 0,
    error                TEXT,
    notes                TEXT,
    created_at           TEXT
);
```

Indexes: `run_id`, `node_id`, `status`.

### 3. `semantic_embeddings` — similarity layer storage (TF-IDF MVP)

```sql
CREATE TABLE IF NOT EXISTS semantic_embeddings (
    embedding_id    TEXT PRIMARY KEY,                 -- uuid4
    node_id         TEXT NOT NULL UNIQUE REFERENCES content_nodes(node_id),
    text_hash       TEXT NOT NULL,                    -- sha256 of source_text; skip recompute when unchanged
    source_text     TEXT,                             -- title + h1 + meta + entity names
    embedding_model TEXT,                             -- 'tfidf-v1' for MVP; model name if upgraded later
    embedding_vector TEXT,                            -- JSON: sparse {term_index: weight} for TF-IDF
    created_at      TEXT,
    updated_at      TEXT
);
```

Per the execution discipline rules: TF-IDF first, model upgrade only if time allows. Sparse-JSON storage keeps this table valid for either backend.

Indexes: `node_id` (unique), `text_hash`.

### 4. `seo_opportunities` — Agent 4 foundation output

```sql
CREATE TABLE IF NOT EXISTS seo_opportunities (
    opportunity_id  TEXT PRIMARY KEY,                 -- uuid4
    node_id         TEXT NOT NULL REFERENCES content_nodes(node_id),
    opportunity_type TEXT NOT NULL,                   -- see types below
    priority        TEXT,                             -- high | medium | low
    reason          TEXT,                             -- human-readable explanation
    evidence        TEXT,                             -- JSON: the numbers behind the reason
    seo_score       REAL DEFAULT 0.0,                 -- 0.0-1.0
    business_score  REAL DEFAULT 0.0,                 -- 0.0-1.0
    status          TEXT DEFAULT 'open',              -- open | in_review | actioned | dismissed
    created_at      TEXT,
    updated_at      TEXT,
    UNIQUE (node_id, opportunity_type)                -- one open row per page per type; re-runs update in place
);
```

Opportunity types (from plan): `orphan_page`, `underlinked_page`, `high_priority_underlinked`, `missing_market_entity`, `missing_geo_entity`, `missing_relationships`, `global_local_gap`, `entity_low_confidence`, `stale_metadata`.

Indexes: `node_id`, `opportunity_type`, `priority`, `status`.

### 5. `integration_placeholders` — GSC/GA4 schema-readiness

```sql
CREATE TABLE IF NOT EXISTS integration_placeholders (
    integration_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,                    -- gsc | ga4
    node_id         TEXT REFERENCES content_nodes(node_id),
    url             TEXT,                             -- raw URL/path as the external system reports it
    metric_name     TEXT,                             -- clicks | impressions | ctr | avg_position | sessions | ...
    metric_value    REAL,
    date_range      TEXT,                             -- e.g. '2026-06-01..2026-06-30'
    status          TEXT DEFAULT 'placeholder',       -- placeholder | synced
    notes           TEXT,
    created_at      TEXT
);
```

Indexes: `source`, `node_id`, `metric_name`.

---

## Existing Tables — Phase 2 Write Plan (no schema change)

| Table | Columns Phase 2 populates | Written by |
|---|---|---|
| `content_nodes` | `market`, `segment`, `region`, `sub_industry` (where evidence) | Agent 2 (Day 3-4) |
| `content_nodes` | `intent_stage`, `business_priority` | Day 7 Module 7.3 |
| `content_nodes` | `ai_readiness_score` | Day 7 Module 7.4 |
| `content_nodes` | `search_opportunity_score` | Day 8 Module 8.1 |
| `content_entities` | all fields | Agent 2 (Day 3-4) |
| `relationship_edges` | all fields; `status` defaults `pending` | Agent 3 (Day 6-7) |

Score-scale note: `content_entities.confidence_score` and every score column in `relationship_edges` use 0.0–1.0.

---

## Migration Approach (Day 2 implementation)

`scripts/09_phase2_migration.py` (global python, raw `sqlite3` — same interpreter as other scripts):

1. Resolve DB path (same `ken_links.db` default + `--db` override pattern as Agent 1).
2. **Copy DB file** → `ken_links_backup_phase2_<YYYYMMDD_HHMMSS>.db`. Abort if copy fails.
3. Open connection, `PRAGMA foreign_keys=ON`, single transaction.
4. Execute all `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` statements.
5. Verify: query `sqlite_master` for the 5 new table names + all index names; print a verification table.
6. Print row counts of all 9 tables (4 old + 5 new) as post-migration evidence.
7. `--verify-only` flag: run steps 5-6 without creating anything (for Day 10 validation).

Same-commit companion change: add the 5 model classes to `database/models.py` so `01_setup_db.py` creates the full Phase 2 schema on a fresh rebuild too (keeps the Day 8 fresh-rebuild guarantee from Phase 1 alive).

### Rollback plan

- Migration is additive → worst case is dropping the 5 new tables.
- Primary rollback: restore the timestamped backup copy.
- `git` never contains a broken DB state: the DB file is committed only after verification passes.

---

## Entity Taxonomy Configuration (Day 2 Module 2.2 — file plan)

`config/taxonomy.py` (new, importable by both envs — stdlib only):

- `ENTITY_TYPES` — the 15 master-PRD types (industry, sub_industry, market, segment, country, region, company, product, technology, service, persona, regulation, claim, evidence, time_period).
- `COUNTRY_TO_REGION` — e.g. india→Asia Pacific, saudi arabia→Middle East, uae→Middle East, vietnam→Asia Pacific, usa→North America…
- `COUNTRY_ALIASES` — `uae` = `united arab emirates`, `ksa` = `saudi arabia`, `usa` = `united states`…
- `SCOPE_VALUES` — values currently stored in `content_nodes.country` that are NOT countries: `global`, `gcc`, `mena`, `asia`, `apac`, `europe`, `middle east`… → mapped to region/scope entities instead (audit finding #3).
- `INDUSTRY_CANONICAL` — the 14 Ken industries (reuse list from Agent 1).
- `MARKET_SUFFIX_RULES` — strip `Market Share, Companies & Trends Report YYYY-YYYY`, `| YYYY-YYYY | Ken Research`, `Market Outlook to YYYY`, mojibake dashes, etc., to isolate the market name from titles.
