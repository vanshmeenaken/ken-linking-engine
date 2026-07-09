# PRD: Ken Intelligence Linking Engine — Phase 2 FINAL
## The Complete System, Delivered by July 19, 2026

**Product:** Ken Intelligence Linking Engine
**Document:** Phase 2 Final PRD — absorbs the ENTIRE master PRD ("Intelligent
MCP, LLM and Agentic Internal Linking System for Ken Research", June 2026).
There is no Phase 3/4/5/6. Everything ships in Phase 2.
**Duration:** July 9 – July 19, 2026 (11 days) · Daily deadline 6:00 PM IST
**Owner:** Shrey (solo build, validation, documentation, handoff)
**Supersedes:** `PHASE_2_PROFESSIONAL_PROJECT_PLAN.md` (Days 1–5 outputs carried
forward; all its "defer to later phase" decisions are cancelled)

---

## 1. Executive Summary

The master PRD describes an MCP-powered, LLM-assisted, agentic internal
linking and content-intelligence system: every page a node, every market/
country/industry an entity, every relationship an edge, every link
recommendation scored, validated, human-approved, deployed and measured.

This document maps 100% of that vision onto an 11-day build. Baseline
already in place (July 7–8): the content inventory (Agent 1, 500 enriched
pages), the entity layer (Agent 2 — 424 entities, 1,893 page-entity mappings,
zero duplicates, correction workflow, independent review passed), the Phase 2
schema, and the read API.

Remaining to build: Agents 3–14, all 12 MCP servers, 5 data-model tables,
the link score formula, the SEO validation engine, the recommendation +
approval + deployment pipeline, 4 dashboards, GSC/GA4 integration,
measurement and decay auditing, and the 5 operating workflows.

## 2. Ground Rules (from the master PRD, still binding)

- **No auto-publish.** Every content change requires human approval (master
  PRD §26.2). Deployment produces approved drafts + rollback logs.
- **Canonical only.** No recommendation may target a non-canonical, noindex,
  redirected, or faceted URL (§18.2) — enforced by a validation gate, not by
  convention.
- **No invention.** No agent may invent URLs, report names, or market numbers
  (§12.3 / §36). Deterministic logic first; LLM reasoning only over fetched
  data.
- **Explainability.** Every score, edge, and recommendation carries its
  reason and inputs (§8, §19).
- **Precision over padding** (project quality bar): a short correct result
  list always beats a padded one. When unsure, leave it out.

## 3. Credential-Gated Scope — the "Credential-Ready" Standard

Three integrations require external access that code cannot create:

| Dependency | What's missing | What ships anyway |
|---|---|---|
| GSC (Search Console) | Google service-account + property access | Full connector, schema, MCP server, agents consuming it — tested on realistic fixtures in `data/fixtures/`; `.env` slots + activation checklist |
| GA4 | Same | Same standard |
| CMS / Jira | No API endpoint/token for Ken CMS, GhostCMS, Django Admin, Jira | Full deployment/ticket code writing to a local mock store + export files; switch flag for live mode |

**Credential-ready means:** 100% of the code exists and is tested in mock
mode; going live is pasting credentials and flipping a flag — minutes, not
development. If credentials arrive before July 17, the affected connector
goes live the same day. Everything else in this PRD runs fully live against
the real 500-page database.

## 4. The 14 Agents — Complete Specifications

### Agent 1: Content Inventory — DONE (Phase 1)
Crawls pages; extracts title/H1/meta/canonical/content-type/industry, link
counts, orphan status, authority score → `content_nodes`. Re-runnable.

### Agent 2: Entity Extraction — DONE (July 8)
Deterministic extraction from metadata → `content_entities`, `node_entities`
(with per-mapping confidence + provenance), backfills market/region on
`content_nodes`. Correction workflow: approve/reject/correct/merge with full
audit. Coverage: 100% any-entity, 100% geography, 92.8% industry-or-market.
Body-content entity types (company, product, technology, regulation, claim,
evidence) are extracted by Agent 8's body pass (July 13), completing the
master PRD §13.2 entity list.

### Agent 3: Relationship Mapping (July 9–10)
Creates typed, scored, directed edges in `relationship_edges` from entities +
metadata + similarity.
- **Edge types (deterministic, July 9):** same_market, same_industry,
  industry_market, market_segment (where segment evidence exists),
  country_region, global_local, report_article_support, case_study_support,
  parent_child (where hierarchy evidence exists)
- **Edge types (similarity-driven, July 10):** adjacent_market — TF-IDF
  similarity + same-industry guard + exact-subject precision rule
- **Deferred-input edge types** (upstream/downstream, competitor, substitute,
  emerging/mature/high-growth/declining, survey_support, consulting/
  procurement/expert-panel intent, freshness_update, authority_redistribution,
  conversion_path): the edge *vocabulary* and storage support all of them
  (master PRD §15 in full); population activates when their inputs exist —
  supply-chain taxonomy, service pages in inventory, published dates, GA4.
  Documented per type in the relationship coverage matrix.
- Fields per edge: type, direction, confidence, semantic_similarity_score,
  entity_overlap_score, geo_match_score, market_match_score,
  business_value_score, seo_value_score, created_by, status (default
  `pending`). Duplicate-edge prevention at DB level.

### Agent 4: SEO Opportunity (July 11)
Finds: orphan pages, underlinked pages, high-priority-underlinked,
missing-market-entity, missing-geo-entity, missing-relationships,
global_local_gap, entity_low_confidence, stale_metadata → `seo_opportunities`
+ `content_nodes.search_opportunity_score`. GSC-dependent finds (position
4–20, high-impression-low-CTR) run on fixtures until credentials arrive.

### Agent 5: Business Priority (July 11)
Master PRD §23 scoring: content-type, industry priority, country priority,
authority/orphan signals live now; revenue potential, sales demand, search
demand, conversion potential as configurable placeholder weights (plug real
values without model rework). Output: `business_priority` High/Medium/Low on
every active node per §23.2 semantics.

### Agent 6: Link Recommendation (July 12)
For qualifying (source, target) pairs from the relationship graph +
opportunity queue: generates the full §19 record — source URL, target URL,
target canonical URL, anchor text + variants (from Agent 7), placement type,
placement section, suggested sentence, relationship type, link score (§17
formula), seo/business/ai-readiness/confidence scores, reason, risk flag,
approval status — into `link_recommendations`. Every candidate passes the
Agent 10 validation gate BEFORE storage. Target: 500+ recommendations.

### Agent 7: Anchor Text (July 12)
Anchor bank per target page → `anchor_banks`: primary, secondary, long-tail,
country-specific, market-specific, commercial anchors; restricted list
(§18.3 avoid-list: "click here", "read more", generic country-only, etc.);
usage counts + overuse flag (§18.4 diversity). Format: country+market,
region+market, market+segment, market+intent, service+outcome.

### Agent 8: Paragraph Evidence (July 13)
One cached body-crawl of the 500 pages (Agent 1 fetch machinery, 5 workers,
HTML cached to disk). Splits paragraphs; classifies claim types
(CAGR/market-size/growth/share/forecast via deterministic patterns); extracts
body entities (company, product, technology, regulation); builds knowledge
hash per §21.2 (`KH_[MARKET]_[COUNTRY]_[SEGMENT]_[CLAIM_TYPE]_[YEAR]_
[SOURCE_TYPE]_[CONFIDENCE]`); flags unsupported + duplicate claims; suggests
supporting reports/case studies → `paragraph_evidence_map`.

### Agent 9: Section Purpose (July 13)
From the same cached HTML: detects TOC/headings; maps each section's purpose
and intent stage; recommends section-specific links and CTA by section
intent; flags purposeless sections and missing section links →
`section_purpose_map`.

### Agent 10: SEO Validation (July 11)
The §18 rule engine, used as a gate by Agent 6 and exposed via API + MCP:
canonical target, indexability, crawlable href, anchor descriptive/not
overused, placement relevance, not blocked/redirected/faceted, page link-count
ranges by type (§18.5), cannibalization risk. Output: approved-for-review /
needs-revision / rejected.

### Agent 11: Editorial Review (July 14)
Human-readable review note per recommendation: why, where, which anchor,
which relationship, SEO value, business value, risk. Never publishes.

### Agent 12: Deployment (July 14, credential-ready)
Approved recommendation → CMS draft export (exact insertion instruction +
suggested sentence + old/new content snapshot) → `deployment_logs` with
rollback support. Mock CMS store locally; live CMS push activates with access.

### Agent 13: Measurement (July 17, credential-ready)
Pre/post per deployed link: clicks, impressions, position (GSC), sessions,
engagement, enquiries (GA4), crawl frequency. Runs end-to-end on fixtures;
switches to live with credentials. Output: performance report per
recommendation + learning inputs for future scoring.

### Agent 14: Link Decay (July 17)
Live monthly-hygiene audit: broken links, redirect chains, links to
removed/archived pages, non-canonical targets, noindex targets, repeated
anchors, pages missing links to new reports → hygiene report + re-queue into
`seo_opportunities`.

## 5. The 12 MCP Servers (July 15–16)

Python `mcp` SDK, stdio transport, one server per file in `mcp_servers/`.
Read-only by default; write tools require `ALLOW_WRITE=1` (§27.2). Every tool
call logged. Tool lists follow master PRD §11 exactly.

| Server | Mode | Tools (per master PRD §11) |
|---|---|---|
| Content Inventory | LIVE | get_page_by_url/id, search_pages, list_by_industry/country/market/node_type, get_canonical_url, get_page_status, get_internal_links_in/out, get_orphan_pages, get_recently_published_pages |
| Knowledge Graph | LIVE | get_related_entities, get_relationships_for_page, parent_child, global_local, country_region, case_study, evidence relationships, create_relationship_edge*, update_relationship_confidence*, reject_relationship*, get_relationship_explanation |
| Embedding Search | LIVE | semantic_search_pages, find_similar_reports/articles/case_studies, get_embedding_similarity_score; paragraph tools live once Agent 8 data exists (July 13): semantic_search_paragraphs, find_duplicate_paragraphs, find_claim_similarity |
| Crawler | LIVE | crawl_url, crawl_section, get_broken_links, get_redirect_chains, get_non_canonical_internal_links, get_pages_deeper_than_depth, get_pages_without_breadcrumbs/toc, excessive_links, js_only_links, blocked_urls, faceted_url_patterns |
| SEO Rules | LIVE | validate_anchor_text, crawlable_href, canonical_target, indexable_target, link_placement, anchor_diversity, link_count, faceted_url_risk, internal_nofollow_risk, redirect_risk, schema_breadcrumb |
| Report Store | LIVE | report-subset queries over content_nodes + link_recommendations |
| Evidence Library | LIVE (after Jul 13) | search_evidence, get_evidence_by_id, search_case_studies/charts/tables/product_images, map_paragraph_to_evidence*, get_evidence_confidence_score, flag_unsupported_claim* |
| CMS | CREDENTIAL-READY | fetch_cms_content, create_link_insertion_draft*, update_related_reports/articles/toc/breadcrumb blocks*, submit_for_editorial_review*, publish_approved_change*, rollback_change* — mock store until CMS access |
| Search Console | CREDENTIAL-READY | get_page_queries/impressions/clicks/ctr/average_position, high_impressions_low_ctr, positions_4_to_20, indexing_status, crawl_errors — fixtures until credentials |
| GA4 | CREDENTIAL-READY | get_page_sessions/engagement/scroll_depth, internal_link_clicks, conversion_events, report_enquiries, sample_requests, lead_sources, assisted_conversions — fixtures until credentials |
| Jira | CREDENTIAL-READY | create_epic/story/task*, update_task_status*, assign_owner*, attach_recommendation_export*, create_monthly_audit_task* — local ticket queue until Jira access |
| Deployment | CREDENTIAL-READY | deploy/rollback/log tools over deployment_logs — mock CMS until access |

(*) = write tool, gated.

## 6. Data Model — All Master PRD §14 Tables

**Exists and populated:** content_nodes (500), content_entities (424),
node_entities (1,893), relationship_edges (fills July 9–10), crawl_logs,
entity_extraction_logs, semantic_embeddings (fills July 10),
seo_opportunities (fills July 11), integration_placeholders (fixture-fed
July 16).

**Migration #2 (July 12), same additive/idempotent/backup standard:**
- `link_recommendations` — full §14.4 field list
- `anchor_banks` — full §14.5 field list
- `paragraph_evidence_map` — full §14.6 field list
- `section_purpose_map` — full §14.7 field list
- `deployment_logs` — full §14.8 field list

## 7. Link Score Formula (§17, exact)

```
Final Internal Link Score =
  16% Semantic Similarity + 12% Entity Overlap + 10% Market/Segment
+  8% Geography Match     +  8% Search Intent  +  8% Business Value
+  8% Authority Transfer  +  6% Freshness      +  5% Crawl Priority
+  5% Anchor Text Quality +  5% Evidence/Case-Study Support
+  4% Conversion Path     +  3% AI Readiness   +  2% Sentiment/External
```
Decision bands: 90–100 priority · 80–89 strong (editor review) · 65–79
secondary · 50–64 hold · <50 do not recommend.
Factors without a live data source yet (freshness — no published dates;
conversion path — GA4; sentiment) run as configurable weights with neutral
defaults and transparent re-normalization, logged per recommendation.

## 8. SEO Validation Rules (§18 — all enforced by Agent 10)

Crawlability (standard href, no JS-only, no blocked/search-result targets) ·
Canonical (canonical URLs only; never tracking/duplicate/old-slug/redirected/
filtered/HTTP/session URLs) · Anchor text (descriptive; §18.3 avoid-list;
country+market / market+intent formats) · Anchor diversity (anchor bank, no
dominant exact-match, §18.4) · Link quantity by page type (§18.5 ranges) ·
Placement priority (body paragraph > section block > related module >
evidence block > TOC > sidebar > footer, §18.6) · Faceted navigation control
(§18.7 non-indexable patterns).

## 9. Recommendation Output (§19) & Ken-Specific Rules (§38)

Every recommendation carries all §19 fields (see Agent 6). The §38 rules are
implemented as coverage checks in the SEO dashboard: every new report's
required incoming links (industry hub, country hub, related articles/reports/
case studies), every article's 3–5 contextual + 1 report + 1 market + 1
related-article + CTA links, market-page and case-study link requirements,
and §38.5 paragraph-claim mapping via Agent 8.

## 10. Workflows (§20) — `scripts/run_workflow.py` (July 17)

new-report · new-article · page-refresh · monthly-audit · report-editing —
each chains the relevant agents and ends in the editorial queue.

## 11. Knowledge Hash (§21), AI Readiness (§22), Business Priority (§23)

- Knowledge hash: §21.2 format, generated by Agent 8 per market claim.
- AI readiness: computable factors (market definition, geo context, metadata
  completeness, entity richness, relationship connectivity) July 10; body
  factors (TOC, FAQ, methodology, structured data, attribution) added
  July 13 from the Agent 8/9 crawl → full §22.1 factor list, High/Medium/Low.
- Business priority: §23 (Agent 5, July 11).

## 12. Dashboards (§24) — July 14 (editorial) & 17 (rest)

- **SEO:** total pages/links, avg links per page, orphans, broken/redirected/
  non-canonical links, deep pages, high-value underlinked, anchor diversity,
  deployment status
- **Business:** link clicks, enquiries, sample requests, top converting
  source/target pages, assisted conversions (fixture-fed until GA4)
- **Intelligence:** entity coverage, relationship coverage, global/local
  mapping, paragraph evidence coverage, case-study linkage, unsupported/
  duplicate claims, pages missing TOC, sections without purpose,
  AI-readiness by industry
- **Editorial:** recommendation queue — approve, reject, edit anchor, edit
  placement, view reason/risk/previews, bulk-approve low-risk, assign owner,
  export (CSV + Jira-format)

## 13. Access Control (§25) & Approval Rules (§26)

Local single-user prototype: role model (Admin/SEO Manager/Content Editor/
Research Reviewer/Tech Developer/Leadership Viewer) implemented as a
permission config consulted by write endpoints + MCP write gating; real
multi-user RBAC documented as deployment-time work (no multi-user runtime
exists locally). §26 approval matrix enforced: contextual body links,
commercial CTAs, consulting links, market-number links, canonical changes,
bulk >50 pages — always human-approved; auto-approve-eligible classes are
marked in data but still routed through the queue in this build.

## 14. Security & Risk Controls (§27)

MCP permission scoping · read-only default · write behind ALLOW_WRITE +
approval status checks · structured output schemas · validation before
approval · audit logs for every action (extraction, correction, edge,
recommendation, approval, deployment) · rollback for every deployment ·
rate-limited crawling · no direct publishing.

## 15. APIs (§29)

- `POST /api/internal-linking/recommend` (Jul 12) — §29.1 inputs/outputs
- `POST /api/internal-linking/validate` (Jul 11) — §29.2
- `POST /api/internal-linking/approve` (Jul 14) — §29.3
- `POST /api/internal-linking/deploy` (Jul 14, draft-mode) — §29.4
- Plus all entity/relationship/intelligence/opportunity GET endpoints
  (entity set live July 9).

## 16. Day-by-Day Schedule

| Day | Date | Deliverables |
|---|---|---|
| 1 | Jul 9 | Entity API verified + tested + documented; entity coverage report; **Agent 3** deterministic edges live |
| 2 | Jul 10 | TF-IDF similarity + semantic_embeddings; full edge scoring; adjacent_market; intent_stage + AI-readiness (computable set) |
| 3 | Jul 11 | **Agents 4, 5, 10**; search_opportunity_score; validate API |
| 4 | Jul 12 | Migration #2 (5 tables); **Agents 6, 7**; recommend API; 500+ scored recommendations |
| 5 | Jul 13 | Body crawl cache; **Agents 8, 9**; knowledge hashes; body entities; AI-readiness body factors |
| 6 | Jul 14 | **Agents 11, 12**; approve + deploy APIs; Editorial Dashboard; deployment_logs + rollback |
| 7 | Jul 15 | MCP batch 1 live: Content Inventory, Knowledge Graph, Embedding Search, Crawler, SEO Rules |
| 8 | Jul 16 | MCP batch 2: Report Store, Evidence Library (live) + CMS, GSC, GA4, Jira, Deployment (credential-ready); fixtures + activation checklist |
| 9 | Jul 17 | **Agents 13, 14**; SEO/Business/Intelligence dashboards; workflow orchestrator |
| 10 | Jul 18 | Full end-to-end pipeline run on real 500 pages; full test suite; independent review + fixes; Shrey recommendation-quality review session |
| 11 | Jul 19 | Final validation vs §30/§34/§35; complete handoff (live vs credential-gated + activation steps); cleanup, commit, tag `v2.0-full-prd`, push |

Cut order under time pressure (never the reverse): doc polish → dashboard
visuals (API/Swagger remains) → mock-data richness → test breadth on
low-risk utilities. Agent correctness and the validation gate are never cut.

## 17. Acceptance Criteria (master PRD §34, honest deltas)

| Master PRD criterion | This build |
|---|---|
| 5,000 priority URLs inventoried | 500 (the sanctioned inventory since Phase 1; every pipeline is re-runnable on a larger URL list — scale is data volume, not code) |
| ≥80% pages correct entity extraction | ✅ already exceeded |
| ≥500 link recommendations | Jul 12 target |
| ≥70% recommendations judged useful | Shrey URL-by-URL review Jul 18 (project quality bar) |
| ≥100 approved links deployed | Approved-draft form + deployment_logs (CMS access absent; auto-publish forbidden by §26 anyway) |
| No recommendation → non-canonical/noindex | Agent 10 gate, enforced |
| Dashboards show SEO/business/intelligence | Jul 14 + 17 |

Success metrics (§30) and quality evaluation (§35 — relevance, anchor
quality, editorial acceptance rate, tool-call accuracy, hallucination rate,
cost per recommendation) are computed in the Jul 19 final validation report;
SEO-outcome metrics (rankings, crawl stats) become measurable only after
deployment + GSC access and are listed as post-activation measurements.

## 18. Risks

| Risk | Mitigation |
|---|---|
| 11-day density | Fixed cut order (above); daily 6 PM checkpoint; agents ship dry-run-first |
| Ken server rate-limits body crawl | One cached crawl (July 13), reused by Agents 8/9/14 |
| MCP SDK friction | Servers are thin wrappers over already-tested modules; REST-mirror fallback documented |
| Recommendation noise | Agent 10 gate + pending-by-default + Jul 18 human review |
| Credentials arrive mid-build | Mode-switchable connectors; same-day activation |
| Scope creep inside 11 days | This PRD is the contract; anything not in it goes to the handoff's "post-activation" list |

## 19. Definition of Done (July 19)

1. All 14 agents exist, tested, with dry-run modes and JSON run reports.
2. All 12 MCP servers exist; 7 fully live, 5 credential-ready with fixtures.
3. All §14 tables exist and are populated (or fixture-populated where gated).
4. ≥500 validated, scored, explainable link recommendations in the editorial
   queue; approval → draft-deployment → rollback path demonstrated.
5. All four dashboards render their §24 metric sets.
6. §29 APIs respond correctly; full test suite green.
7. Final validation report scores the build against §30/§34/§35.
8. Handoff document: everything live, everything credential-gated with exact
   activation steps, every command, every report location.
9. Repo tagged `v2.0-full-prd`.
