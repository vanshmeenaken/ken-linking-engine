# Performance & Integration Test Report — Day 8

**Date:** July 6, 2026
**Tester:** Shrey
**Scope:** Full end-to-end pipeline test, from a clean rebuild through load testing

---

## Summary

The pipeline was tested from a clean database rebuild through to concurrent API
load. All steps passed. One real bug was found and permanently fixed during
this test (see "Bug Found" below) — this is exactly what an integration test
is supposed to catch.

**Overall result: PASSED**

---

## 1. Fresh Rebuild Test

Rather than deleting the live `ken_links.db` (which holds hours of crawl and
manual-fix history), the rebuild was verified safely in a throwaway
`ken_links_test.db`, using the exact same `01_setup_db.py` and
`02_load_urls.py` logic pointed at the test file.

| Step | Result |
|------|--------|
| Fresh schema created | 4 tables: `content_nodes`, `content_entities`, `relationship_edges`, `crawl_logs` |
| Load `scripts/sample_urls.csv` | 500 → 500 rows inserted |
| Duplicates | 0 |
| Bad/skipped rows | 0 |

**Bug found during prep:** `scripts/sample_urls.csv` only contained 499 unique
URLs — one case study
(`case-studies/latam-apac-lubricant-market-entry-strategy`) existed in the live
database but was never in the source CSV, meaning it must have been inserted
directly at some point outside the normal pipeline. A fresh rebuild from the
CSV would have silently produced 499 rows instead of 500. Fixed by adding the
missing row to the CSV with its known field values.

---

## 2. Agent 1 Full Run (against real `ken_links.db`)

| Metric | Result |
|--------|--------|
| URLs processed | 500 |
| Successful | 500 |
| Failed | 0 |
| Execution time | 279 seconds (~4.7 min) at 5 workers |
| Workers | 5 (deliberately conservative — Ken's server rate-limits aggressive crawling) |

**Bug found and permanently fixed:** two report URLs
(`middle-east-medical-display-monitors-market`,
`middle-east-radiation-cured-market`) 301-redirect twice on the live site and
land on `/report-store`, a page linked from every menu (thousands of incoming
links). Agent 1 was inheriting the hub's own incoming-link count onto these
dead URLs. This had previously been "fixed" with a one-off manual SQL patch —
but since the patch only touched the `status` column, and Agent 1's `UPDATE`
statement never wrote `status` at all, a routine re-run silently undid every
other part of the fix (`internal_links_in` and `page_authority_score` reverted
to the fake inflated values) while leaving `status='removed'` behind as a
stale, misleading leftover.

Root-caused and fixed in `agents/agent_1_content_inventory.py`:
- Detect when a crawled URL's final destination path is a generic hub page
  (`/report-store`, `/`) different from the URL it was asked to crawl
- When detected: keep the page's `canonical_url` alias scoped to itself (never
  inherit the hub's sitewide link count), mark `indexability_status =
  "redirected_removed"`, and force `status`, `orphan_status`,
  `internal_links_in`, and `page_authority_score` to reflect a removed page
- Added `status` to the database `UPDATE` statement, which had never written
  that column before

**Verified after fix — re-ran Agent 1 from scratch, no manual patching:**

| Field | Before fix (recurring bug) | After fix (permanent) |
|-------|---------------------------|------------------------|
| Avg `internal_links_in` | 21.21 (inflated) | **2.0** |
| Max `internal_links_in` | 4,804 (fake) | **181** (real top page) |
| `removed` status count | 0 (silently lost every re-run) | **2** (correctly detected every run) |
| Qatar test page `internal_links_out` | — | **5** (matches manual browser count exactly) |

---

## 3. Data Validation

```
python scripts/03_validate_data.py
```

| Metric | Result |
|--------|--------|
| Critical fields avg | 100.0% |
| Optional fields avg | 74.8% |
| Duplicate penalty | 0 |
| **Final score** | **95.0% — EXCELLENT** |
| Target | ≥ 80% |
| Status | **PASS** |

---

## 4. API Endpoint Testing

Server started fresh (`uvicorn api.main:app`). All endpoints tested:

| Endpoint | Status | Time |
|----------|--------|------|
| `GET /` | 200 | 0.21s |
| `GET /api/stats` | 200 | 0.22s |
| `GET /api/metrics` | 200 | 0.22s |
| `GET /api/pages?limit=50` | 200 | 0.23s |
| `GET /api/pages?limit=100` | 200 | 0.23s |
| `GET /api/pages?industry=Healthcare&country=india` | 200 | 0.22s |
| `GET /api/pages?industry=healthcare&country=India` | 200 | 0.22s |
| `GET /api/pages?search=lubricants` | 200 | 0.22s |
| `GET /api/pages?skip=500&limit=10` (beyond data size) | 200 | 0.23s |
| `GET /api/pages?industry=NotARealIndustry` | 200 | 0.22s |
| `GET /api/pages/orphans` | 200 | 0.23s |
| `GET /api/pages/orphans?limit=5` | 200 | 0.21s |
| `GET /api/taxonomy/industries` | 200 | 0.22s |
| `GET /api/taxonomy/countries` | 200 | 0.22s |
| `GET /docs` | 200 | 0.23s |
| `GET /dashboard` | 200 | 0.23s |
| `GET /api/pages/{bad-id}` | 404 (expected) | 0.22s |

**Data accuracy checks:**
- Case-insensitive filters: `Healthcare/India` and `healthcare/India` both return `total: 3` — identical ✓
- Pagination beyond data size (`skip=500` of 500 total): returns `total: 500, pages: []` — no crash ✓
- Invalid filter value: returns `total: 0, pages: []` — no crash ✓
- Search substring match: `lubricants` → 3 correct results ✓

**Security testing:**
- SQL injection via `search=' OR '1'='1'`: returned `total: 0`, no data leak, `content_nodes` table intact with 500 rows after ✓
- SQL injection via `industry='; DROP TABLE content_nodes; --`: returned `200`, table survived intact ✓
- XSS payload in search (`<script>alert(1)</script>`): returned `200`, no execution risk (JSON API, not rendered as HTML server-side) ✓
- All queries use parameterized SQL (`?` placeholders) — confirmed no string-concatenated SQL anywhere in `api/main.py`

All endpoints responded in well under the 500ms target (actual range: 210–253ms).

---

## 5. Load Testing

| Test | Result |
|------|--------|
| 10 concurrent requests | All completed in 1.24s wall time, no errors |
| 50 concurrent requests | All completed in 3.06s wall time, no errors |
| 50-request status codes | 50× `200`, 0 failures |
| 50-request avg response time | 224.9ms |
| 50-request max response time | 253.4ms |

No timeouts, no degradation, no connection errors under concurrent load.

---

## 6. Memory Check

The API server process was observed at ~18MB resident memory after the load
test — lightweight, as expected for a stateless FastAPI app doing per-request
SQLite reads with no in-memory caching. No growth was observed across the
endpoint and load tests, consistent with no leak.

---

## Conclusion

**PASSED.** The pipeline is reproducible from a clean state, Agent 1
consistently produces correct link-count data (verified against manual
counts), the API layer is fast, stable under concurrent load, and resistant
to injection attempts. One recurring data-quality bug (report-store link
inheritance) was found and permanently fixed at the code level during this
test — exactly the kind of defect integration testing exists to catch.
