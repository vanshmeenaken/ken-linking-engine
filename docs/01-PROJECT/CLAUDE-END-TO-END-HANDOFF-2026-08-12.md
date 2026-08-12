# Claude End-to-End Project Handoff

**Project:** Ken Intelligence Linking Engine  
**Workspace:** `Interlinking`  
**Owner:** Shrey  
**Handoff date:** August 12, 2026  
**Primary database:** `ken_links.db` (SQLite)  
**Current phase:** Phase 3 - recommendations, editorial review, and manual deployment handoff  
**Git state:** latest committed code is `cfbb0e7`; the newest bidirectional planning work described below is still uncommitted

## 1. Purpose of This Document

This is the complete continuation brief for another coding agent, especially Claude. It records:

- what Shrey asked for during the last several work sessions;
- what was discovered in the PRD and existing implementation;
- what was changed and why;
- the current behavior, database state, generated outputs, and limitations;
- the tests and visual checks already completed;
- what must not be overwritten;
- the exact remaining work.

Read this document before changing the recommendation engine. Then read the primary PRD and the files listed in Section 14.

## 2. Product Goal

The project inventories Ken Research content, maps entities and relationships, identifies SEO/internal-link opportunities, and produces human-reviewable link instructions.

The system does **not** directly edit the live website. Phase 3 produces:

1. a source page;
2. a target page;
3. an anchor;
4. a placement type/section or exact sentence;
5. relevance and safety scores;
6. a plain-English editorial explanation;
7. an approve/reject decision;
8. a CSV that the web team can implement manually.

The primary PRD requires report pages to work toward **10-25 outgoing internal links** and the new-report workflow to surface **10-30 qualified incoming and outgoing opportunities**. These are quality-controlled ranges, not quotas that permit irrelevant padding.

## 3. What Shrey Asked For

The requests evolved in this order:

1. Read the project directories and understand the entire system.
2. Determine the day's TODO from the PRD, not from assumptions.
3. Finish and save the earlier safety-checker correction.
4. Review the original 42 recommendations.
5. Approve good recommendations and retain rejected decisions.
6. Create a spreadsheet handoff for the web team because Shrey cannot edit the live site.
7. Add a short human-readable explanation for every approved link.
8. Test everything twice and eventually push to GitHub using Shrey's own authenticated terminal.
9. Explain a GitHub account-selection popup. It was an authentication/account chooser, not a project error. Closing it only cancelled that authentication attempt.
10. Investigate why the recommendation queue appeared dominated by regional reports.
11. Explain what “adjacent reports” means before changing the logic.
12. Improve recommendations so reports can interlink both:
    - **regional reports:** the same market/topic across different geographies;
    - **adjacent reports:** distinct but closely related markets/technologies that are useful to the same reader.
13. Explain how the system decides where to link and where not to link.
14. Read the main PRD and confirm how many links/opportunities each report should have.
15. Implement the required regional + adjacent changes end to end.
16. Explain the new `report_link_plans` dashboard section.
17. Produce this complete handoff so Claude can continue with full context.

Important clarification: Shrey never asked to replace adjacent recommendations with regional-only recommendations. The required behavior is to include **both** categories.

## 4. Meaning of Regional and Adjacent

### Regional report

A regional relationship is normally the same market/technology subject across a different geography.

Example:

- Global Cold Storage Market
- India Cold Storage Market

The subject is materially the same; geography differs.

In the implementation, these usually come from `same_market` or `global_local` relationship edges and are classified as `regional_report` for planning.

### Adjacent report

An adjacent report is not simply another country version of the same report. It is a different but closely related market or technology that gives the reader a useful next step.

Example:

- Freight Software Market
- Freight Automation Market

The relationship must pass the market/technology relevance gate. Geography does not create an adjacent relationship; it only labels an accepted adjacent relationship as `adjacent` or `adjacent_regional`.

In planning, report-to-report `adjacent_market` recommendations are categorized as `adjacent_report`.

### Why both are necessary

Regional links create geographic depth around the same subject. Adjacent links create topical breadth and reader discovery across closely related subjects. A useful report page should not be limited to only one pattern.

## 5. How Recommendations Are Decided

The engine does not recommend every possible pair.

### Candidate creation

Agent 3 creates typed relationship edges such as:

- `same_market`
- `global_local`
- `adjacent_market`
- `country_region`
- `report_article_support`
- `case_study_support`

Adjacent report candidates must:

- belong to a compatible industry;
- represent different markets;
- pass market/technology subject analysis;
- pass the configured market score threshold;
- pass the configured technology score threshold;
- pass the optional final subject judge when available.

Current adjacent safety thresholds:

- market relevance >= 0.30;
- technology relevance >= 0.50;
- combined relevance weights: market 65%, technology 35%.

### Direction

An edge is not automatically a usable page instruction. A recommendation is directional: “source should link to target.”

Before the latest work, a bidirectional relationship edge commonly produced only its stored source-to-target orientation. This underrepresented valid links and contributed to reports showing only one recommendation.

Agent 6 now expands every `relationship_direction='bidirectional'` edge into both orientations and independently calculates:

- target anchor;
- SEO/business score;
- validation result;
- placement;
- plan category;
- source-page capacity.

### Scoring and selection

Recommendations are ranked by semantic, entity, market, technology, SEO, business, AI-readiness, and confidence signals already established by Agent 6. Deferred factors remain documented instead of being silently treated as zero.

The planner:

- preserves the strongest qualified candidate;
- introduces category diversity when possible;
- preserves approved human decisions;
- excludes rejected pairs from the active plan;
- prevents duplicate active source-target pairs;
- respects the source content type's outgoing-link maximum;
- limits each report to at most 30 combined incoming/outgoing opportunities;
- never invents weak candidates to meet a numeric minimum.

### Placement

Contextual placement is used only when the target genuinely fits a source sentence. If no genuine sentence exists after a successful crawl, a related-reports block can be appropriate.

If the source crawl fails, the system now marks the placement `unresolved`. It does **not** infer that the link belongs in a Related Reports block merely because the page could not be fetched.

### Human control

Nothing is automatically deployed. Recommendations remain pending until an editor approves or rejects them. Existing approval/rejection decisions are authoritative and must survive machine rebuilds.

## 6. Earlier Completed and Committed Phase 3 Work

These changes are already represented in Git history:

- `92b0526`: initial Agent 6 recommendation engine.
- `82fdc06`: anchor banks and editorial approve/reject workflow.
- `fde090a`: dashboard review queue.
- `3192edc`: source-target deduplication.
- `3ef18ce`: contextual placement and anchor rotation.
- `fbdd737`: vector-search foundation, GA4 endpoint, and placement precision corrections.
- `8498016`: fixed Agent 10 rejecting 38 of 42 recommendations because of a placement-name mismatch.
- `e25d2e1`: editorial review notes and TOC placement correction.
- `8d6d5bf`: review explanations in API/dashboard and approved-link CSV support.
- `a52b425`: reviewed the first 42 recommendations and exported approved links.
- `cfbb0e7`: market/technology gating and regional/adjacent classification.

### First editorial batch

The original batch contained 42 recommendations:

- 26 approved;
- 16 rejected;
- all 42 pass the safety validator after the placement vocabulary correction.

The approved handoff is:

`reports/approved_links_handover_phase3.csv`

It contains 26 rows and includes source, target, anchor, placement, suggested sentence, scores, rationale, and plain-English editorial note.

## 7. Latest Bidirectional Planning Work

The following work is present in the workspace but is not yet committed.

### 7.1 New planning module

Added `analysis/report_link_planner.py`.

It defines:

- report outgoing range: 10-25;
- report opportunity range: 10-30;
- content-type link capacities;
- mapping from relationship types to planning categories;
- category-diverse candidate ordering;
- balanced selection with source and report caps;
- regeneration of one `report_link_plans` row per active report;
- honest gap reasons when inventory cannot supply qualified links.

### 7.2 Bidirectional Agent 6 recommendations

Updated `agents/agent_6_link_recommendation.py`.

Changes:

- expands bidirectional edges into both source-target orientations;
- scores and validates each direction independently;
- carries source/target content types;
- stores `placement_status`, `plan_category`, and `source_plan_rank`;
- protects approved anchors;
- protects confirmed/unresolved placements;
- excludes rejected source-target pairs;
- ensures an approved pair cannot also reappear as a pending copy under another relationship type;
- preserves reviewed rows while deleting stale pending machine rows;
- validates the complete source batch, not only one hypothetical added link;
- refreshes report plans after writes, including a zero-candidate rebuild.

### 7.3 Relationship candidate breadth

Updated `agents/agent_3_relationship_mapping.py`.

`MAX_ADJACENT_PER_PAGE` was increased from 5 to 10. This increases candidate breadth only. It does not bypass relevance gates, Agent 6 scoring, diversity rules, or PRD limits.

### 7.4 Batch-aware safety validation

Updated `agents/agent_10_seo_validation.py`.

`validate(..., additional_links=N)` now checks:

`current outgoing links + the complete proposed source batch`

against the content type's maximum. Previously it checked only one added link at a time, which could approve each item individually even when the combined plan exceeded the maximum.

### 7.5 Report planning schema

Added `scripts/27_report_link_planning_migration.py`.

It:

- adds `placement_status`, `plan_category`, and `source_plan_rank` to `link_recommendations`;
- creates `report_link_plans`;
- creates status indexes;
- is additive and idempotent;
- creates a database backup before schema changes.

`scripts/21_phase3_migration.py` was also updated so a fresh Phase 3 recommendation table includes the three new recommendation fields.

### 7.6 Placement repair and protection

Added `scripts/28_repair_failed_placement_run.py`.

Why: an earlier failed live-page crawl had changed 87 of 88 recommendations to a related-reports placement. Network failure was incorrectly treated as evidence that no contextual sentence existed.

The repair script restores known-good contextual placement fields from a backup while preserving current editorial decisions.

Updated `scripts/22_place_contextual_links.py`:

- accepts `--db`;
- processes pending planned/unresolved rows only;
- never touches confirmed rows;
- marks failed/empty source pages `unresolved`;
- does not rotate anchors or revalidate unresolved rows;
- marks successfully evaluated placements `confirmed`.

### 7.7 Anchor preservation

Updated `scripts/26_rotate_recommendation_anchors.py`.

It now:

- rotates pending anchors only;
- leaves approved/deployed anchors unchanged;
- avoids using anchors already committed to approved/deployed recommendations where possible.

Agent 7 rebuilt 101 anchor banks with 891 variants. The active pending set has no duplicate source-target pairs and no pending anchor duplication groups requiring cleanup.

### 7.8 Editorial-title cleanup

Updated `agents/agent_11_editorial_review.py` so human-readable notes remove the leading “Ken Research” title prefix where present.

### 7.9 API additions

Updated `api/main.py`.

Added:

- `GET /api/report-link-plans/stats`
- `GET /api/report-link-plans`

The plan list supports:

- `plan_status`;
- `opportunity_status`;
- search;
- pagination.

Recommendation APIs now expose:

- placement status;
- plan category;
- source plan rank;
- suggested sentence;
- review status.

The page recommendations endpoint now returns `link_plan`. Editorial decisions refresh planning summaries in the same transaction.

Actionable reports with available opportunities are sorted ahead of equally underlinked reports with no candidates.

### 7.10 Dashboard additions

Updated `dashboard/index.html`.

Added:

- report-plan summary cards;
- report plan search and filters;
- existing/proposed/projected/incoming/opportunity/mix/status columns;
- recommendation filters by review state and relationship class;
- placement-state messaging;
- horizontal scrolling for wide tables on mobile.

The dashboard no longer claims “Related Reports” when placement is only planned or unresolved. It displays “Placement awaiting source-page verification.”

## 8. Meaning of the Report Link Plans Dashboard

Each row is one active report.

- **Existing:** currently detected outgoing internal links.
- **Proposed Out:** active approved + pending outgoing recommendations from this report.
- **Projected:** `Existing + Proposed Out`; the PRD report range is 10-25.
- **Incoming:** recommendations from other pages to this report.
- **Opportunities:** outgoing + incoming candidates involving this report; workflow range is 10-30.
- **Mix:** regional reports, adjacent reports, supporting content/evidence, and hubs.
- **Plan Status:** whether the projected outgoing total is below, within, or above range.
- **Gap reason:** why the report remains short. Missing qualified inventory is reported rather than hidden.

Example:

```text
Existing 4 + Proposed Out 3 = Projected 7
Incoming 2
Total opportunities = 3 outgoing + 2 incoming = 5
```

That report still needs at least three additional qualified outgoing links. The planner will not fabricate them.

The “10-30 opportunities” value does not mean 10-30 links will automatically be published. It is the candidate pool for editorial review.

## 9. Current Data State

Database integrity was checked after the final rebuild:

- SQLite integrity: `ok`;
- foreign-key violations: 0;
- inventory pages: 500;
- active pages: 498;
- active reports with plans: 298;
- trusted relationship edges: 108;
- recommendation records: 151;
- active recommendations: 135;
- approved: 26;
- pending: 109;
- rejected: 16;
- reciprocal pairs: 55;
- active duplicate source-target pairs: 0.

Active planning categories:

- adjacent report: 46;
- regional report: 8;
- supporting content: 2;
- evidence: 1;
- hub: 3;
- other: 75.

Report plan results:

- plans in 10-25 projected range: 48;
- plans below 10: 250;
- plans above 25: 0;
- plans above 30 combined opportunities: 0;
- remaining qualified outgoing-link gap across reports: 1,717.

Placement state:

- 26 approved contextual placements: confirmed;
- 16 rejected contextual placements: confirmed and retained for audit;
- 19 pending contextual placements: unresolved due to crawl/network failure;
- 89 pending related-report placements: confirmed;
- 1 pending hub placement: confirmed.

All active recommendations currently pass Agent 10 as `approved_for_review`. That status means safe to present to a human, not editorially approved.

## 10. Why Most Reports Still Do Not Reach the PRD Minimum

The system deliberately did not pad plans.

Current inventory content types are dominated by:

- 298 reports;
- 99 articles;
- 101 case studies.

The sample has no actual industry, country, region, or service page content types available for the expected hub/source mix. Therefore:

- no report currently has 10 qualified combined opportunities;
- 250 reports remain below 10 projected outgoing links;
- the dashboard records shortages honestly in `gap_reason`.

This is an inventory-coverage limitation, not a reason to lower the relevance gate.

## 11. Live Crawl Limitation

The placement crawl could not access 18 source pages in the execution environment because of network/proxy restrictions. This affected 19 pending contextual recommendations.

Correct current behavior:

- retain contextual intent;
- mark `placement_status='unresolved'`;
- retry later when live-site access works;
- do not automatically move those links to Related Reports.

Do not treat those 19 rows as implementation-ready until the placement is confirmed.

## 12. Tests and Verification Already Completed

The complete suite was run repeatedly during implementation. The final code state passed twice:

```powershell
python -m pytest -q --basetemp=C:\tmp\pytest-interlink-final-c-20260812
python -m pytest -q --basetemp=C:\tmp\pytest-interlink-final-d-20260812
```

Both results:

```text
262 passed, 1 warning
```

The warning is the existing Starlette/httpx TestClient deprecation warning.

Additional checks:

- Python compilation passed for changed agents, planner, API, and migration/repair scripts.
- `git diff --check` passed; only expected Git LF-to-CRLF notices were shown.
- database integrity and foreign keys passed;
- active duplicate pair count is zero;
- no plan exceeds PRD maxima;
- approved-link CSV has 26 rows;
- Agent 6 final dry run generated 135 recommendations;
- desktop dashboard checked at 1440px;
- mobile dashboard checked at a true 390px viewport;
- document width remained 390px; wide tables scroll inside their panels;
- report-plan API and dashboard returned HTTP 200.

Pytest under the restricted Windows token cannot inspect its normal temp directories. Use an explicit `C:\tmp\...` basetemp and approved/unrestricted execution when required. The resulting test errors were environment permission errors, not product failures.

## 13. Backups and Recovery Points

Relevant backups:

- `ken_links_backup_before_phase3_review_20260810_162943.db`
- `ken_links_backup_before_adjacent_recs_20260810_171711.db`
- `ken_links_backup_market_technology_20260810_180352.db`
- `ken_links_backup_before_market_technology_recommendations_20260810_180815.db`
- `ken_links_backup_report_planning_20260812_131742.db`
- `ken_links_backup_before_placement_repair_20260812_131753.db`
- `ken_links_backup_before_bidirectional_plans_20260812_132436.db`

The known-good source used to restore the original reviewed contextual placements was:

`ken_links_backup_before_adjacent_recs_20260810_171711.db`

Never delete these backups until the current work is committed, reviewed, and pushed.

## 14. Files Claude Should Read First

Read in this order:

1. `source_of_truth/Intelligent MCP Linking System PRD.pdf`
2. `source_of_truth/Ken_Intelligence_Linking_PRD_Summary.md`
3. `source_of_truth/PHASE_2_FINAL_PRD.md`
4. this document
5. `docs/05-PHASES/PHASE-3/01-HANDOFF.md`
6. `README.md`
7. `analysis/report_link_planner.py`
8. `agents/agent_3_relationship_mapping.py`
9. `agents/agent_6_link_recommendation.py`
10. `agents/agent_10_seo_validation.py`
11. `agents/agent_11_editorial_review.py`
12. `scripts/22_place_contextual_links.py`
13. `scripts/26_rotate_recommendation_anchors.py`
14. `scripts/27_report_link_planning_migration.py`
15. `scripts/28_repair_failed_placement_run.py`
16. `api/main.py`
17. `dashboard/index.html`
18. `source_of_truth/SCHEMA.md`
19. the changed tests.

## 15. Operational Commands

### Apply schema to another Phase 3 database

```powershell
python scripts/21_phase3_migration.py
python scripts/27_report_link_planning_migration.py
```

### Rebuild relationships and opportunities

Use the project agents' documented CLI options and take a backup before a live write. The latest final generated reports are:

- `reports/relationship_mapping_report_planner_final.json`
- `reports/seo_opportunity_report_planner_final.json`
- `reports/link_recommendations_20260812_132934.json`

### Regenerate recommendations

```powershell
python agents/agent_6_link_recommendation.py --dry-run
python agents/agent_6_link_recommendation.py
```

Dry-run still writes a JSON report but does not update the database.

### Retry placements

Only retry when live source pages are accessible:

```powershell
python scripts/22_place_contextual_links.py --dry-run
python scripts/22_place_contextual_links.py
```

### Export approved links

```powershell
python scripts/24_export_approved_links.py --out reports/approved_links_handover_phase3.csv
```

### Run tests

```powershell
python -m pytest -q --basetemp=C:\tmp\pytest-interlink-next
```

### Run dashboard

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Dashboard:

`http://127.0.0.1:8001/dashboard`

Port 8000 previously had an older process, so port 8001 was used for final verification.

## 16. Safety Rules for Continuing

Claude must preserve these invariants:

1. Do not modify or delete approved/rejected decisions during a machine rebuild.
2. Do not rotate approved/deployed anchors.
3. Do not overwrite confirmed placements.
4. Do not classify a crawl failure as a Related Reports placement.
5. Do not generate both approved and pending active copies of the same source-target pair.
6. Do not exceed 25 projected outgoing links for a report.
7. Do not exceed 30 combined report opportunities.
8. Do not lower quality thresholds merely to reach 10.
9. Do not deploy anything automatically to the live website.
10. Do not remove user-created/untracked files.
11. Take a database backup before migrations or live regeneration.
12. Treat `.env`, Google credentials, tokens, and API keys as secrets. Never include them in docs, commits, reports, or chat output.

## 17. Git and Authentication State

The newest work is not committed or pushed.

Latest commit:

`cfbb0e7 feat(recommendations): gate by market and tech`

The workspace also contains older untracked screenshots/reports that predate the latest implementation. Do not remove them simply to clean `git status`.

GitHub authentication previously displayed a Windows “Select an account” chooser. Closing it cancelled that authentication attempt only. A push must be done with Shrey's intended GitHub account in Shrey's own terminal/session.

Before committing:

1. inspect `git status --short`;
2. separate relevant implementation files from pre-existing untracked artifacts;
3. rerun the full tests;
4. review the database diff and generated reports;
5. commit the code, schema, tests, docs, final DB state, and intended final reports only;
6. let Shrey authenticate and push.

## 18. Remaining Work

Required editorial/operational work:

1. Review all 109 pending recommendations.
2. Approve/reject them without altering the first 42 decisions unintentionally.
3. Retry the 19 unresolved placements when live-page access is available.
4. Re-export the approved CSV after new approvals.
5. Have Shrey/content reviewer sanity-check approved rows.
6. Send the CSV to the web/content team for manual implementation.

Required inventory work:

1. Add or correctly classify industry pages.
2. Add or correctly classify country and region hubs.
3. Add service pages.
4. Expand beyond the 500-page sample.
5. Rebuild relationships, recommendations, and plans after inventory expansion.

Later roadmap:

- stronger GSC/GA4 prioritization;
- conversion mapping;
- CMS deployment workflow only after access and approval controls exist.

## 19. Current Definition of Done

The requested recommendation-engine modification is complete because:

- regional and adjacent report relationships are both represented;
- bidirectional edges generate both usable directions;
- recommendations are quality-gated and capped;
- every active report has an honest plan;
- the dashboard explains current links, proposed links, incoming opportunities, mix, and gaps;
- prior editorial decisions and placements are protected;
- data and generated handoff were rebuilt;
- full tests passed twice;
- desktop/mobile UI was verified.

The overall Phase 3 business workflow is **not** fully complete until the 109 pending rows are reviewed, unresolved placements are retried, the CSV is regenerated, and the web team manually implements approved links.

## 20. Short Continuation Summary

The recommendation engine originally produced a small mostly one-directional queue. The first 42 rows were validated and manually reviewed, resulting in 26 approvals and 16 rejections plus a web-team CSV. Shrey then required both regional and adjacent report linking and PRD-aware per-report plans. The system now expands bidirectional edges, balances qualified categories, enforces 10-25 outgoing and 10-30 opportunity maxima, protects human decisions and placements, and exposes plans in the API/dashboard. Current data has 135 active recommendations, including 46 adjacent-report and 8 regional-report rows, with 55 reciprocal pairs. Inventory coverage is insufficient to reach minimums for most reports, so the dashboard reports the gap instead of padding weak links. The latest implementation is tested but still uncommitted and unpushed.
