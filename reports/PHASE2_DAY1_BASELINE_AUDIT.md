# Phase 2 — Day 1 Baseline Audit

**Date:** July 7, 2026 (Day 1 of Phase 2)
**Owner:** Shrey
**Purpose:** Verify the Phase 1 baseline before any Phase 2 schema or code change (Module 1.1 of the Phase 2 plan).

---

## 1. Table Counts (ken_links.db)

| Table | Rows | Status |
|---|---:|---|
| `content_nodes` | 500 | 498 active, 2 removed (hub redirects) |
| `content_entities` | 0 | Empty — Phase 2 Agent 2 target |
| `relationship_edges` | 0 | Empty — Phase 2 Agent 3 target |
| `crawl_logs` | 9,807 | Audit trail healthy |

## 2. content_nodes Field Completeness (500 rows)

### Fully populated (Phase 1 output — trusted evidence for Agent 2)

| Field | Fill | Notes |
|---|---:|---|
| url, canonical_url, title, meta_title, h1 | 500/500 | |
| meta_description | 495/500 | 5 pages had no meta description on live crawl |
| content_type | 500/500 | 300 report / 101 case_study / 99 article |
| industry | 499/500 | 1 blank (known Phase 1 residual) |
| country | 500/500 | Lowercase values; top: india 82, global 62, saudi arabia 54, vietnam 26, usa 25, uae 24. Note: "global" and "gcc" appear as country values — Agent 2 normalization must reclassify these as scope/region, not country |
| global_or_local | 500/500 | 120 global / 380 local — **already populated**, direct input for Agent 3 global-local edges |
| indexability_status | 500/500 | 496 indexable, 2 noindex, 2 redirected_removed |
| crawl_depth, internal_links_in/out, orphan_status, page_authority_score, status | 500/500 | Orphans: 354 (70.8%), under_linked 68, normal 28, well_linked 48, removed 2 |

### Empty (Phase 2 must populate)

| Field | Fill | Populated by |
|---|---:|---|
| market | 0/500 | Agent 2 (extract from title/H1/slug) |
| segment | 0/500 | Agent 2 (where evidence exists) |
| region | 0/500 | Agent 2 (country→region map) |
| sub_industry | 0/500 | Agent 2 (where evidence exists) |
| intent_stage | 0/500 | Day 7 Module 7.3 (content-type mapping) |
| business_priority | 0/500 | Day 7 Module 7.3 |
| search_opportunity_score | 0/500 | Day 8 Module 8.1 |
| ai_readiness_score | 0/500 | Day 7 Module 7.4 |
| published_date, updated_date | 0/500 | NOT in Phase 2 scope (freshness deferred to Phase 3/6 per relationship coverage matrix) |

## 3. Extraction Feasibility Check

Report titles are highly structured — deterministic market extraction is viable:

```
Qatar Nordic Regulatory Affairs Market | 2019-2030 | Ken Research
Bahrain Pectin Market Share, Companies & Trends Report 2025-2031
United Arab Emirates Low GWP Refrigerants Market Share, Companies & Trends Report 2025-2031
```

Pattern: `{Geography} {Market Name} Market [Share...] | {years} | Ken Research`.
One encoding artifact found (`2019 � 2030` — mojibake dash) — title normalization must strip non-UTF8 punctuation.

## 4. Test Suite Status

| Suite | Interpreter | Result |
|---|---|---|
| tests/test_content_inventory_agent.py (7 tests) | global `python` | 7/7 PASS |
| tests/test_database.py (1 test) | `venv\Scripts\python.exe` | 1/1 PASS |

**Dependency gap confirmed (documented Phase 1 tech debt):** the suite cannot run under one interpreter.
- venv lacks `openai` → collection error on the agent test.
- global python lacked `pytest` → installed during this audit (July 8); now both suites runnable, still split across two envs.
- Consolidation remains open tech debt; not blocking Phase 2 (new Phase 2 code will target the **global python** env for agents/scripts and **venv** for API, same as Phase 1).

## 5. API Baseline

9 endpoints live (health, stats, metrics, pages list, orphans, page detail, industries, countries taxonomy, dashboard) — verified in Phase 1 Day 8 testing, unchanged since commit 3deaeec.

## 6. Data Gaps Carried Into Phase 2 (confirmed)

1. `content_entities`, `relationship_edges` empty — the core Phase 2 work.
2. No `node_entities` join table — must be created (Day 2 migration).
3. `country` column conflates country/region/scope values (`global`, `gcc`, `mena`, `asia`) — Agent 2 normalization layer must split these into proper entity types.
4. 354/500 orphans is the dominant SEO signal — feeds Day 8 opportunity scoring.
5. 60 `/industry-reports/*` URLs were 500-ing on Ken's live server at Phase 1 close (external outage) — their stored metadata is from earlier successful crawls and is usable; re-crawl not needed for Phase 2 (metadata-only extraction).
6. No published/updated dates — freshness-based factors excluded from AI-readiness computable subset (already documented in plan Module 7.4).

## 7. Verdict

Phase 2 starts from a clean, known baseline. No blockers. Schema design (Module 1.2) can proceed — see `docs/03-DATABASE/04-PHASE2-SCHEMA-DESIGN.md`.
