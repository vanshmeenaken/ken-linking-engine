# KEN INTELLIGENCE LINKING ENGINE
## Phase 2: Intelligence Layer
### 10-Day Development Plan

**Project Duration:** July 7 - July 16, 2026  
**Daily Deadline:** 6:00 PM IST  
**Owner:** Shrey  
**Execution Model:** Solo development, validation, documentation and handoff  
**Phase 1 Baseline:** Complete foundation and content inventory with 500 enriched content nodes

---

## EXECUTIVE SUMMARY

Phase 2 converts the Phase 1 content inventory into an intelligence layer. Phase 1 answered: "What pages exist, what metadata do they have, and how linked are they?" Phase 2 must answer: "What is each page about, which entities does it contain, how are pages related, and which pages have SEO or business opportunity?"

The phase focuses on building the first usable knowledge graph foundation for Ken Research. It covers entity extraction, entity normalization, page-to-entity mapping, relationship indexing, semantic similarity foundation, global/local segmentation, business priority scoring, early SEO opportunity detection, and the initial MCP/integration design for GSC, GA4, crawler, knowledge graph, and SEO rules.

Phase 2 does not attempt full link recommendation, editorial approval, CMS deployment, paragraph evidence mapping, or performance learning. Those belong to later phases. However, Phase 2 must prepare the data model and APIs so those later phases can be built without reworking the foundation.

---

## CURRENT PHASE 1 BASELINE

### What Already Exists

- SQLite database: `ken_links.db`
- Core tables:
  - `content_nodes`
  - `content_entities`
  - `relationship_edges`
  - `crawl_logs`
- 500 content nodes enriched by Agent 1
- Content types currently present:
  - reports
  - articles
  - case studies
- Existing page metadata:
  - URL
  - canonical URL
  - title
  - meta title
  - meta description
  - H1
  - content type
  - industry
  - country
  - crawl depth
  - internal links in
  - internal links out
  - orphan status
  - authority score
  - active/removed status
- FastAPI read-only API
- Dashboard-facing endpoints
- Agent 1 content inventory logic
- Data validation and execution reports
- Phase 1 handoff documentation

### Known Limitations Carried Into Phase 2

- `content_entities` exists but is empty.
- `relationship_edges` exists but is empty.
- No page-to-entity join table exists yet.
- No relationship graph exists yet.
- No semantic similarity layer exists yet.
- No GSC or GA4 data is integrated yet.
- No MCP server layer exists yet.
- No manual correction workflow exists yet.
- Link counts are strong enough to move forward, but not guaranteed to be perfect because sitewide crawl coverage was not 100%.

---

## PHASE 2 OBJECTIVE

Build the Intelligence Layer for the Ken Intelligence Linking Engine.

Phase 2 must create a structured, searchable, explainable intelligence graph from the 500 Phase 1 content nodes. Each important page should have extracted entities, confidence scores, normalized taxonomy values, page-to-entity mappings, relationship candidates, semantic similarity signals, global/local segmentation, and early business/SEO priority indicators.

---

## PHASE 2 KEY OBJECTIVES

- Build Agent 2: Entity Extraction Agent
- Populate `content_entities`
- Create page-to-entity mapping table
- Normalize entities and aliases
- Add confidence scoring for extracted entities
- Create manual correction structure for low-confidence entities
- Build Agent 3: Relationship Mapping Agent
- Populate `relationship_edges`
- Add relationship scoring and status fields
- Add semantic similarity foundation
- Add global/local segmentation logic
- Add business priority score foundation
- Add intent stage mapping (`content_nodes.intent_stage`)
- Add AI readiness score foundation (`content_nodes.ai_readiness_score`, computable-subset)
- Add early Agent 4 SEO opportunity foundation (including `content_nodes.search_opportunity_score`)
- Extend API/dashboard endpoints for entities and relationships
- Design GSC and GA4 integration models
- Define MCP server architecture for Phase 2 and later phases
- Build minimal foundations for Content Inventory MCP, Knowledge Graph MCP, Crawler MCP and SEO Rules MCP
- Create validation reports, test coverage and handoff documentation

---

## PHASE 2 SUCCESS CRITERIA

Phase 2 is successful if:

- At least 95% of active pages have one or more extracted entities.
- At least 80% of active pages have a market, industry, geography, or segment entity.
- `content_entities` is populated with normalized, deduplicated entities.
- Page-to-entity mapping exists and is queryable.
- Low-confidence entities are identifiable for manual review.
- Relationship edges are generated for high-confidence page relationships.
- Relationship edges include type, direction, confidence score and status.
- Relationship graph is visible through API/dashboard endpoints.
- Semantic similarity is available as a usable score for relationship mapping.
- Global/local segmentation is available for all active pages where evidence exists.
- Business priority score exists for active content nodes, mapped to the master PRD High/Medium/Low bands.
- Intent stage is populated for active content nodes from content type mapping.
- AI readiness score (computable-subset) exists for active content nodes, with deferred body-content factors documented.
- Early SEO opportunity report identifies orphan, underlinked, high-priority and relationship-gap pages, and populates `search_opportunity_score`.
- GSC and GA4 integration designs are documented and schema-ready.
- MCP server designs are documented, with minimal local callable foundations where practical.
- Tests cover entity extraction, normalization, relationship creation, scoring and API endpoints.
- Phase 2 handoff document is complete.

---

## NON-GOALS FOR PHASE 2

Phase 2 will not fully build:

- Full link recommendation engine
- Anchor text generation agent
- Editorial approval dashboard
- CMS publishing or deployment automation
- Jira export workflow
- Paragraph-level evidence mapping for all reports
- Full GA4/GSC production integration if credentials are not available
- Full enterprise role-based access control
- Full MCP production deployment
- Direct website publishing

These remain planned for later phases.

---

## MASTER PRD ALIGNMENT

### Master PRD Phase 2 Scope

The master PRD defines Phase 2 as:

- Add entity extraction
- Add relationship index
- Add semantic embeddings
- Add global/local segmentation
- Add business priority score

### Agents In Scope For Phase 2

| Agent | Phase 2 Status | Purpose |
|---|---|---|
| Agent 1: Content Inventory Agent | Existing dependency | Provides content nodes and metadata |
| Agent 2: Entity Extraction Agent | Build | Extract and normalize entities |
| Agent 3: Relationship Mapping Agent | Build | Create relationship edges |
| Agent 4: SEO Opportunity Agent | Foundation | Identify early SEO opportunities |
| Agent 5: Business Priority Agent | Foundation | Score strategic/commercial page priority |
| Agent 6: Link Recommendation Agent | Defer | Requires mature relationship graph |
| Agent 7: Anchor Text Agent | Defer | Requires recommendations |
| Agent 8: Paragraph Evidence Agent | Defer | Phase 5 focus |
| Agent 9: Section Purpose Agent | Defer | Later content intelligence layer |
| Agent 10: SEO Validation Agent | Foundation only | Rule design and simple checks |
| Agent 11: Editorial Review Agent | Defer | Phase 3/4 workflow |
| Agent 12: Deployment Agent | Defer | Phase 4 workflow |
| Agent 13: Measurement Agent | Design only | Requires GA4/GSC production data |
| Agent 14: Link Decay Agent | Defer | Phase 6/monthly maintenance |

### MCP Servers In Scope For Phase 2

| MCP Server | Phase 2 Status | Notes |
|---|---|---|
| Content Inventory MCP | Design + minimal foundation | Expose page inventory tools |
| CMS MCP | Defer | Deployment phase |
| Search Console MCP | Design + schema foundation | Requires credentials |
| GA4 MCP | Design + schema foundation | Requires credentials |
| Crawler MCP | Design + minimal foundation | Reuse Agent 1 crawl logic |
| Knowledge Graph MCP | Design + minimal foundation | Expose entity/relationship tools |
| Embedding Search MCP | Foundation | Semantic search/similarity |
| Report Store MCP | Design only | Depends on available report store access |
| Evidence Library MCP | Defer | Phase 5 |
| SEO Rules MCP | Design + basic validation rules | Canonical/indexability/anchor/faceted rules |
| Jira MCP | Defer | Deployment workflow |
| Deployment MCP | Defer | CMS deployment phase |

### Relationship Type Coverage vs Master PRD

The master PRD (Agent 3 spec and Section 15) defines the full relationship
taxonomy. Phase 2 implements the types computable from entities and page
metadata; every other type is explicitly deferred with its blocking dependency
so nothing is silently dropped.

| Master PRD Relationship Type | Phase 2 Status | Reason / Dependency |
|---|---|---|
| Parent-child | Build (where evidence exists) | Entity hierarchy from taxonomy |
| Industry-market | Build | From extracted entities |
| Market-segment | Build (where evidence exists) | From extracted entities |
| Country-region | Build | From country-to-region map |
| Global-local | Build | From global_or_local segmentation |
| Same market | Build | From normalized market entities |
| Case study support | Build | From content type + shared entities |
| Report-article support | Build | From content type + shared entities |
| Adjacent market | Defer (Phase 3) | Needs semantic similarity maturity + market taxonomy curation |
| Substitute market | Defer (Phase 3+) | Needs curated market intelligence input |
| Upstream / Downstream | Defer (Phase 3+) | Needs supply-chain taxonomy not in Phase 2 data |
| Competitor | Defer (Phase 3+) | Needs company entity coverage (body-content extraction) |
| Emerging / Mature / High-growth / Declining market | Defer (Phase 3+) | Needs report content signals |
| Evidence support | Defer (Phase 5) | Paragraph evidence mapping scope |
| Survey support | Defer (Phase 5) | Evidence library scope |
| Consulting / Procurement / Expert panel intent | Defer (Phase 3) | Needs service pages in inventory + intent mapping |
| Freshness update | Defer (Phase 3/6) | Needs published/updated dates populated |
| Authority redistribution | Defer (Phase 3) | Recommendation-engine concern, not a graph fact |
| Conversion path | Defer (Phase 4/6) | Needs GA4 production data |

---

## PHASE 2 DATA MODEL REQUIREMENTS

### Existing Tables To Use

#### `content_nodes`

Continue to use as the primary page table.

Phase 2 may update or populate:

- `market`
- `segment`
- `region`
- `global_or_local`
- `intent_stage`
- `business_priority`
- `search_opportunity_score`
- `ai_readiness_score`
- `updated_at`

#### `content_entities`

Populate this table with normalized entities.

Required fields:

- `entity_id`
- `entity_name`
- `entity_type`
- `normalized_name`
- `aliases`
- `parent_entity_id`
- `industry`
- `country`
- `region`
- `confidence_score`
- `created_at`
- `updated_at`

Entity types:

- industry
- sub_industry
- market
- segment
- country
- region
- company
- product
- technology
- service
- persona
- regulation
- claim
- evidence
- time_period

#### `relationship_edges`

Populate this table with page and entity relationships.

Required fields:

- `edge_id`
- `source_node_id`
- `target_node_id`
- `source_entity_id`
- `target_entity_id`
- `relationship_type`
- `relationship_direction`
- `confidence_score`
- `semantic_similarity_score`
- `entity_overlap_score`
- `geo_match_score`
- `market_match_score`
- `business_value_score`
- `seo_value_score`
- `created_by`
- `reviewed_by`
- `status`
- `created_at`
- `updated_at`

### New Tables Needed In Phase 2

#### `node_entities`

Purpose: map pages to entities.

Recommended fields:

- `node_entity_id`
- `node_id`
- `entity_id`
- `entity_role`
- `source_field`
- `extracted_value`
- `normalized_value`
- `confidence_score`
- `extraction_method`
- `status`
- `created_at`
- `updated_at`

Statuses:

- extracted
- approved
- corrected
- rejected

Entity roles:

- primary_industry
- secondary_industry
- primary_market
- secondary_market
- country
- region
- segment
- product
- technology
- service_intent
- buyer_persona
- time_period

#### `entity_extraction_logs`

Purpose: audit Agent 2 runs.

Recommended fields:

- `log_id`
- `run_id`
- `node_id`
- `operation`
- `status`
- `entities_found`
- `low_confidence_count`
- `error`
- `notes`
- `created_at`

#### `semantic_embeddings`

Purpose: store semantic representation or local similarity inputs.

Recommended fields:

- `embedding_id`
- `node_id`
- `text_hash`
- `source_text`
- `embedding_model`
- `embedding_vector`
- `created_at`
- `updated_at`

If vector storage is too heavy for Phase 2, use TF-IDF similarity as a local MVP and keep the table optional.

#### `seo_opportunities`

Purpose: store early Agent 4 opportunities.

Recommended fields:

- `opportunity_id`
- `node_id`
- `opportunity_type`
- `priority`
- `reason`
- `evidence`
- `seo_score`
- `business_score`
- `status`
- `created_at`
- `updated_at`

Opportunity types:

- orphan_page
- underlinked_page
- high_priority_underlinked
- missing_market_entity
- missing_geo_entity
- missing_relationships
- global_local_gap
- entity_low_confidence
- stale_metadata

#### `integration_placeholders`

Purpose: prepare for GSC and GA4 while credentials/data access are being arranged.

Recommended fields:

- `integration_id`
- `source`
- `node_id`
- `url`
- `metric_name`
- `metric_value`
- `date_range`
- `status`
- `notes`
- `created_at`

Sources:

- gsc
- ga4

---

## API REQUIREMENTS FOR PHASE 2

### Entity Endpoints

- `GET /api/entities`
- `GET /api/entities/{entity_id}`
- `GET /api/entities/low-confidence`
- `GET /api/pages/{node_id}/entities`
- `GET /api/taxonomy/markets`
- `GET /api/taxonomy/regions`
- `GET /api/taxonomy/segments`

### Relationship Endpoints

- `GET /api/relationships`
- `GET /api/pages/{node_id}/relationships`
- `GET /api/entities/{entity_id}/relationships`
- `GET /api/relationships/types`
- `GET /api/relationships/pending`

### Intelligence Metrics Endpoints

- `GET /api/intelligence/stats`
- `GET /api/intelligence/entity-coverage`
- `GET /api/intelligence/relationship-coverage`
- `GET /api/intelligence/global-local`
- `GET /api/intelligence/business-priority`

### SEO Opportunity Endpoints

- `GET /api/opportunities`
- `GET /api/opportunities/orphans`
- `GET /api/opportunities/underlinked`
- `GET /api/opportunities/high-priority`

### Correction Endpoints

Optional if write endpoints are allowed in Phase 2:

- `PATCH /api/entities/{entity_id}`
- `PATCH /api/node-entities/{node_entity_id}`
- `PATCH /api/relationships/{edge_id}`

If write endpoints are deferred, corrections can be done by script and documented as a manual workflow.

---

## DASHBOARD REQUIREMENTS FOR PHASE 2

The dashboard should evolve from inventory-only to intelligence visibility.

Required views:

- Entity coverage summary
- Relationship coverage summary
- Low-confidence entity review list
- Pages missing market/entity values
- Top markets
- Top countries
- Top regions
- Top industries
- Global/local mapping view
- Relationship graph/table view
- SEO opportunity preview
- Business priority score view
- Case study linkage coverage (master PRD Intelligence Dashboard metric -
  computable in Phase 2 from case-study-support edges)
- AI-readiness score by industry (master PRD Intelligence Dashboard metric -
  computable-subset from Module 7.4)

Minimum acceptable dashboard output:

- API endpoints return the data needed for these views.
- Swagger UI can be used if a full visual dashboard cannot be completed inside Phase 2.

---

## GSC INTEGRATION REQUIREMENTS

### Phase 2 Goal

Prepare Search Console integration so future agents can prioritize internal links using real search opportunity data.

### Data To Support

- URL
- query
- clicks
- impressions
- CTR
- average position
- date range
- device
- country
- search type

### Phase 2 Deliverables

- GSC integration design document
- Credential requirements documented
- Schema placeholder or integration table
- Mapping logic from GSC page URL to `content_nodes`
- Definition for "position 4-20 opportunity"
- API placeholder or script stub if credentials are unavailable

### Out Of Scope

- Production GSC sync if credentials are unavailable
- Automated recommendation logic based on GSC

---

## GA4 INTEGRATION REQUIREMENTS

### Phase 2 Goal

Prepare GA4 integration so future agents can connect internal linking to sessions, engagement and conversion value.

### Data To Support

- URL
- sessions
- users
- engagement rate
- average engagement time
- report enquiries
- sample report requests
- consulting enquiries
- assisted conversions
- date range

### Phase 2 Deliverables

- GA4 integration design document
- Credential requirements documented
- Schema placeholder or integration table
- Mapping logic from GA4 page path to `content_nodes`
- Definition for conversion/business value scoring
- API placeholder or script stub if credentials are unavailable

### Out Of Scope

- Production GA4 sync if credentials are unavailable
- Full attribution modeling

---

## MCP REQUIREMENTS FOR PHASE 2

Phase 2 should define the MCP boundary and implement minimal local tool foundations where practical.

### Content Inventory MCP Tools

- `get_page_by_url`
- `get_page_by_id`
- `search_pages`
- `list_pages_by_industry`
- `list_pages_by_country`
- `get_orphan_pages`
- `get_page_entities`
- `get_page_relationships`

### Knowledge Graph MCP Tools

- `get_entity_by_name`
- `search_entities`
- `get_related_entities`
- `get_relationships_for_page`
- `create_relationship_edge`
- `update_relationship_status`
- `get_relationship_explanation`

### Crawler MCP Tools

- `crawl_url`
- `get_internal_links`
- `check_canonical`
- `check_indexability`
- `detect_redirect`
- `get_broken_links`

### Embedding Search MCP Tools

Foundation scope, backed by the Phase 2 similarity method (TF-IDF MVP or
embedding model - whichever Module 7.2 lands on):

- `semantic_search_pages`
- `find_similar_reports`
- `find_similar_articles`
- `find_similar_case_studies`
- `get_similarity_score`

Deferred to Phase 5 (require paragraph-level data): `semantic_search_paragraphs`,
`find_duplicate_paragraphs`, `find_claim_similarity`.

### SEO Rules MCP Tools

- `validate_canonical_target`
- `validate_indexability`
- `validate_anchor_text`
- `validate_faceted_url_risk`
- `validate_link_count`
- `validate_redirect_risk`

### Search Console MCP Tools

Design only unless credentials are available:

- `get_page_queries`
- `get_page_ctr`
- `get_pages_ranking_positions_4_to_20`
- `get_indexing_status`

### GA4 MCP Tools

Design only unless credentials are available:

- `get_page_sessions`
- `get_conversion_events`
- `get_report_enquiries`
- `get_assisted_conversions`

---

## TECHNICAL REQUIREMENTS

### Backend

- Python
- SQLite for Phase 2 local prototype
- FastAPI
- SQLAlchemy models kept in sync with actual DB
- Deterministic extraction logic first
- Optional LLM or external model only after deterministic MVP works

### Semantic Similarity

Acceptable MVP options:

- TF-IDF using title + H1 + meta description + entity text
- Local cosine similarity
- Embedding model if dependency and runtime are stable

### Safety

- No direct publishing
- No CMS writes
- No destructive DB rebuilds without backup
- Dry-run mode for agents
- JSON reports for every agent execution
- Manual review path for low-confidence data

---

## EXECUTION DISCIPLINE RULES

The scope above is achievable in 10 solo days only if these rules hold. When
time pressure hits, cut in this order and never the reverse:

1. **API-first, dashboard-light.** Swagger UI is an acceptable Phase 2
   dashboard. No visual dashboard work before all API endpoints exist.
2. **TF-IDF first.** No embedding-model dependency unless TF-IDF similarity
   is working end-to-end with time to spare.
3. **Design-first for GSC/GA4/MCP.** Documents and schema stubs satisfy
   Phase 2. Zero production integration work without credentials in hand.
4. **Deterministic before LLM.** No LLM calls in Agent 2/3 until the
   deterministic MVP meets coverage targets.
5. **The scoring foundations (business priority, intent stage, AI readiness,
   search opportunity) are single-pass computations over existing data** -
   each is hours, not days. If any of them starts growing beyond that,
   reduce it to a design note and move on.
6. **First thing to drop under pressure:** optional write/correction API
   endpoints (script-based correction is acceptable). **Last thing to drop:**
   Agent 2 entity extraction quality - everything downstream depends on it.

---

## DETAILED 10-DAY BREAKDOWN

---

## DAY 1: PHASE 2 SCOPE, SCHEMA DESIGN AND BASELINE AUDIT

**Date:** Tuesday, July 7, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Lock Phase 2 scope, audit Phase 1 baseline, and design the schema upgrades required for the intelligence layer.

### Module 1.1: Phase 1 Baseline Audit

**Deliverables:**

- Current DB counts verified
- Current API endpoints verified
- Current tests checked
- Current data gaps documented

**Acceptance Criteria:**

- Content node count is confirmed.
- Empty intelligence tables are confirmed.
- Known dependency/test issues are documented.
- Phase 2 starts from a clean, known baseline.

**Tasks:**

- [ ] Run DB count checks for all tables
- [ ] Check `content_nodes` field completeness
- [ ] Confirm `content_entities` and `relationship_edges` baseline
- [ ] Run current tests
- [ ] Record dependency gaps
- [ ] Save baseline notes in Phase 2 report

### Module 1.2: Schema Upgrade Design

**Deliverables:**

- Final schema plan for Phase 2
- Migration approach
- Index plan
- Backup plan

**Acceptance Criteria:**

- New tables are clearly defined.
- Existing tables are not broken.
- Migration can be run safely.
- Rollback/backup path is documented.

**Tasks:**

- [ ] Define `node_entities`
- [ ] Define `entity_extraction_logs`
- [ ] Define optional `semantic_embeddings`
- [ ] Define optional `seo_opportunities`
- [ ] Define integration placeholder table
- [ ] Update schema docs draft

### DAY 1 SUCCESS CHECKLIST

- [ ] Phase 2 scope locked
- [ ] Baseline audit complete
- [ ] Schema design complete
- [ ] Backup/migration approach documented
- [ ] No code changes made without backup plan

---

## DAY 2: DATABASE MIGRATION AND ENTITY FOUNDATION

**Date:** Wednesday, July 8, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Implement Phase 2 database schema upgrades and prepare the entity extraction foundation.

### Module 2.1: Database Migration Script

**Deliverables:**

- Safe migration script
- New Phase 2 tables
- Indexes
- Verification query output

**Acceptance Criteria:**

- Migration is repeat-safe.
- Existing Phase 1 data remains intact.
- New tables exist after migration.
- Indexes are created.

**Tasks:**

- [ ] Create backup before migration
- [ ] Add migration script
- [ ] Create `node_entities`
- [ ] Create `entity_extraction_logs`
- [ ] Create `semantic_embeddings` or similarity placeholder
- [ ] Create `seo_opportunities`
- [ ] Create integration placeholder table
- [ ] Verify table creation

### Module 2.2: Entity Taxonomy Configuration

**Deliverables:**

- Entity type constants
- Known country/region map
- Known industry map
- Known aliases
- Normalization helpers

**Acceptance Criteria:**

- Entity types match master PRD.
- Country/region normalization works.
- Industry normalization works.
- Aliases can be expanded later.

**Tasks:**

- [ ] Define entity type list
- [ ] Define country-to-region map
- [ ] Define industry aliases
- [ ] Define common market suffix cleanup rules
- [ ] Add normalization tests

### DAY 2 SUCCESS CHECKLIST

- [ ] Migration implemented
- [ ] New tables verified
- [ ] Entity taxonomy foundation created
- [ ] Existing Phase 1 data intact

---

## DAY 3: AGENT 2 ENTITY EXTRACTION MVP

**Date:** Thursday, July 9, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Build Agent 2 MVP to extract and normalize entities from Phase 1 content nodes.

### Module 3.1: Agent 2 Core Logic

**Deliverables:**

- `agents/agent_2_entity_extraction.py`
- Dry-run mode
- Limit mode
- JSON report output
- Transaction-safe DB update

**Acceptance Criteria:**

- Agent reads `content_nodes`.
- Agent extracts entities deterministically.
- Agent writes to `content_entities` and `node_entities`.
- Agent can run without modifying DB in dry-run mode.

**Extraction Source Scope Note:**

The master PRD Agent 2 spec covers extraction from "pages and paragraphs."
Phase 2 deliberately extracts from stored metadata only (URL slug, title, H1,
meta description, existing industry/country fields) - no live body-content
crawling. Consequence: entity types that mostly live in body text (company,
product, technology, regulation, claim, evidence) will have low coverage in
Phase 2. This is accepted and documented; body-content extraction joins in a
later phase alongside paragraph evidence mapping. Coverage targets in this
plan apply to metadata-derivable entity types (industry, market, geography,
segment).

**Tasks:**

- [ ] Load active content nodes
- [ ] Extract entities from URL slug
- [ ] Extract entities from title
- [ ] Extract entities from H1
- [ ] Extract entities from meta description
- [ ] Use existing industry/country fields as trusted evidence
- [ ] Assign confidence scores
- [ ] Write report without DB writes in dry-run mode

### Module 3.2: Entity Confidence Scoring

**Deliverables:**

- Confidence score model
- Extraction source tracking
- Low-confidence thresholds

**Acceptance Criteria:**

- Trusted fields get higher confidence.
- URL/title inference gets moderate confidence.
- Weak extraction gets low confidence.
- Low-confidence records are reportable.

**Tasks:**

- [ ] Define scoring for exact DB field match
- [ ] Define scoring for title/H1 match
- [ ] Define scoring for slug inference
- [ ] Define scoring for alias inference
- [ ] Flag low-confidence entities

### DAY 3 SUCCESS CHECKLIST

- [ ] Agent 2 MVP created
- [ ] Dry-run works
- [ ] Confidence scoring works
- [ ] JSON report generated
- [ ] No duplicate entities created

---

## DAY 4: ENTITY NORMALIZATION, DEDUPLICATION AND MANUAL CORRECTION

**Date:** Friday, July 10, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Make entities clean, searchable and correctable.

### Module 4.1: Entity Normalization

**Deliverables:**

- Canonical names
- Normalized names
- Alias handling
- Duplicate prevention

**Acceptance Criteria:**

- UAE and United Arab Emirates resolve to one entity.
- Industry aliases resolve consistently.
- Market names are normalized.
- Duplicate entity creation is prevented.

**Tasks:**

- [ ] Normalize casing
- [ ] Normalize country aliases
- [ ] Normalize region names
- [ ] Normalize industry names
- [ ] Normalize market suffixes
- [ ] Prevent duplicate normalized entities

### Module 4.2: Manual Correction Structure

**Deliverables:**

- Correction fields/status workflow
- Low-confidence report
- Manual correction script or API design

**Acceptance Criteria:**

- Extracted, approved, corrected and rejected statuses exist.
- Original extracted values are preserved.
- Corrected values can be stored.
- Low-confidence values can be listed.

**Tasks:**

- [ ] Add correction status handling
- [ ] Add rejected entity handling
- [ ] Add corrected entity handling
- [ ] Generate low-confidence CSV/JSON
- [ ] Document correction workflow

### DAY 4 SUCCESS CHECKLIST

- [ ] Entity normalization works
- [ ] Duplicate prevention works
- [ ] Manual correction workflow documented
- [ ] Low-confidence report available

---

## DAY 5: ENTITY API AND DASHBOARD EXTENSIONS

**Date:** Saturday, July 11, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Expose entity intelligence through the API/dashboard layer.

### Module 5.1: Entity API Endpoints

**Deliverables:**

- Entity list endpoint
- Entity detail endpoint
- Page entities endpoint
- Taxonomy endpoints
- Low-confidence endpoint

**Acceptance Criteria:**

- APIs return JSON.
- Pagination and filters are supported where needed.
- Page-to-entity mapping is visible.
- Low-confidence entities are visible.

**Tasks:**

- [ ] Add `/api/entities`
- [ ] Add `/api/entities/{entity_id}`
- [ ] Add `/api/pages/{node_id}/entities`
- [ ] Add `/api/entities/low-confidence`
- [ ] Add `/api/taxonomy/markets`
- [ ] Add `/api/taxonomy/regions`
- [ ] Update API docs

### Module 5.2: Entity Coverage Report

**Deliverables:**

- Entity coverage JSON report
- Summary metrics
- Missing entity list

**Acceptance Criteria:**

- Coverage report lists pages with no entities.
- Report lists missing market/country/region/industry.
- Report includes confidence distribution.

**Tasks:**

- [ ] Count pages with entities
- [ ] Count pages missing market
- [ ] Count pages missing geography
- [ ] Count low-confidence entities
- [ ] Produce JSON report

### DAY 5 SUCCESS CHECKLIST

- [ ] Entity endpoints working
- [ ] Entity coverage report generated
- [ ] API documentation updated
- [ ] Dashboard can fetch entity data

---

## DAY 6: AGENT 3 RELATIONSHIP MAPPING MVP

**Date:** Sunday, July 12, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Build Agent 3 MVP to generate relationship edges from extracted entities and page metadata.

### Module 6.1: Relationship Rule Engine

**Deliverables:**

- `agents/agent_3_relationship_mapping.py`
- Relationship rule definitions
- Dry-run mode
- JSON report
- DB write mode

**Acceptance Criteria:**

- Agent reads nodes and node entities.
- Agent creates relationship candidates.
- Agent writes to `relationship_edges`.
- Duplicate edges are avoided.

**Tasks:**

- [ ] Create same-industry relationships
- [ ] Create same-market relationships
- [ ] Create country-region relationships
- [ ] Create global-local relationships
- [ ] Create report-article relationships
- [ ] Create case-study-support relationships
- [ ] Add dry-run report

### Module 6.2: Relationship Types

**Deliverables:**

- Supported relationship type list
- Direction rules
- Confidence rules

**Acceptance Criteria:**

- Relationship types match master PRD where feasible.
- Direction is stored.
- Confidence score is stored.
- Status defaults to pending.

**Tasks:**

- [ ] Implement parent-child where evidence exists
- [ ] Implement industry-market
- [ ] Implement market-segment where evidence exists
- [ ] Implement country-region
- [ ] Implement global-local
- [ ] Implement same-market
- [ ] Implement case-study support

### DAY 6 SUCCESS CHECKLIST

- [ ] Agent 3 MVP created
- [ ] Relationship candidates generated
- [ ] Relationship edges stored
- [ ] Duplicate edges prevented
- [ ] Report generated

---

## DAY 7: RELATIONSHIP SCORING, SEMANTIC SIMILARITY AND BUSINESS PRIORITY

**Date:** Monday, July 13, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Add scoring signals to relationships and create foundations for semantic and business intelligence.

### Module 7.1: Relationship Scoring

**Deliverables:**

- Confidence score
- Entity overlap score
- Geo match score
- Market match score
- SEO value score
- Business value score

**Acceptance Criteria:**

- Every relationship has a confidence score.
- Scoring is deterministic and explainable.
- Scores are bounded from 0 to 100 or 0.0 to 1.0 consistently.

**Tasks:**

- [ ] Score entity overlap
- [ ] Score geography match
- [ ] Score market match
- [ ] Score content type relationship
- [ ] Score authority/SEO value
- [ ] Score business value

### Module 7.2: Semantic Similarity Foundation

**Deliverables:**

- Similarity method
- Page text generation
- Similarity scores
- Optional storage

**Acceptance Criteria:**

- Similarity can compare pages.
- Scores are reproducible.
- Similarity is available to Agent 3.

**Tasks:**

- [ ] Build page text from title, H1, meta and entities
- [ ] Implement TF-IDF or selected local method
- [ ] Compute pairwise similarity for reasonable candidate sets
- [ ] Store or report semantic similarity

### Module 7.3: Business Priority Score Foundation

**Deliverables:**

- Business priority scoring model
- Updated `content_nodes.business_priority`
- Updated `content_nodes.intent_stage`
- Report

**Acceptance Criteria:**

- Reports and high-value pages can be prioritized.
- Orphan/underlinked status influences score.
- Industry/country priorities can be configured.
- Output maps to the master PRD Section 23.2 bands: High (push links
  aggressively from authority pages), Medium (normal contextual links),
  Low (only where highly relevant).
- Master PRD Section 23.1 inputs that need business data (revenue potential,
  sales team demand, search demand, lead conversion potential, consulting/
  survey/procurement/expert-panel relevance) are represented as configurable
  placeholder weights so real values can be plugged in later without model
  rework.

**Tasks:**

- [ ] Define priority factors (full master PRD 23.1 input list; mark
      business-data-dependent inputs as configurable placeholders)
- [ ] Score content type priority
- [ ] Score country/region priority
- [ ] Score industry priority
- [ ] Score authority/orphan signals
- [ ] Map final score to High/Medium/Low per master PRD 23.2
- [ ] Set `content_nodes.intent_stage` from content type mapping
      (article = awareness, case study = consideration/proof,
      report = decision/commercial) - field exists in schema but was
      previously never populated
- [ ] Save business priority

### Module 7.4: AI Readiness Score Foundation

The master PRD (Section 22) requires an AI-readiness score per priority page,
and the Intelligence Dashboard (Section 24.3) reports it by industry. The
`ai_readiness_score` field exists in `content_nodes` but nothing computed it
before this module. Phase 2 scores only the factors computable from existing
data; body-content factors (TOC, FAQ, methodology sections) are deferred to a
later crawl-based pass and documented as such.

**Deliverables:**

- AI readiness scoring model (computable-subset)
- Updated `content_nodes.ai_readiness_score`
- Per-industry summary in the intelligence report

**Acceptance Criteria:**

- Score is deterministic and explainable per master PRD guardrails.
- Computable factors used: clear market definition evidence (market entity
  present), clear geography (country/region entity present), structured
  metadata completeness (title/H1/meta present), entity richness, internal
  links to related entities (relationship edges exist), updated date recency.
- Non-computable factors (TOC/FAQ/methodology/structured data/author
  attribution) are explicitly listed as deferred, not silently skipped.
- Output maps to master PRD 22.2 bands: High / Medium / Low.

**Tasks:**

- [ ] Define computable factor list and weights
- [ ] Score entity richness per page
- [ ] Score metadata completeness per page
- [ ] Score relationship connectivity per page
- [ ] Map to High/Medium/Low bands
- [ ] Save `ai_readiness_score`
- [ ] Add per-industry AI-readiness summary to intelligence report
- [ ] Document deferred body-content factors

### DAY 7 SUCCESS CHECKLIST

- [ ] Relationship scoring works
- [ ] Semantic similarity MVP works
- [ ] Business priority score exists
- [ ] Intent stage populated from content type
- [ ] AI readiness foundation score exists
- [ ] Reports generated

---

## DAY 8: SEO OPPORTUNITY FOUNDATION, GSC/GA4 DESIGN AND MCP DESIGN

**Date:** Tuesday, July 14, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Create the early SEO opportunity layer and design the external integrations required by the master PRD.

### Module 8.1: Agent 4 SEO Opportunity Foundation

**Deliverables:**

- SEO opportunity script/agent
- `seo_opportunities` records
- Opportunity report

**Acceptance Criteria:**

- Orphan pages are identified.
- Underlinked pages are identified.
- High-priority underlinked pages are identified.
- Entity/relationship gaps are identified.

**Tasks:**

- [ ] Detect orphan pages
- [ ] Detect underlinked pages
- [ ] Detect high-priority targets
- [ ] Detect missing market entities
- [ ] Detect missing relationship coverage
- [ ] Populate `content_nodes.search_opportunity_score` from opportunity
      signals (field exists in schema but was previously never written;
      becomes the pre-GSC placeholder that real position-4-20 data will
      refine once credentials are available)
- [ ] Generate opportunity report

### Module 8.2: GSC Integration Design

**Deliverables:**

- GSC integration design doc
- Credential requirements
- Data schema
- API/MCP tool design

**Acceptance Criteria:**

- Required metrics are defined.
- Credential setup is documented.
- URL mapping to `content_nodes` is defined.
- Position 4-20 opportunity logic is defined.

**Tasks:**

- [ ] Define GSC fields
- [ ] Define credential flow
- [ ] Define sync process
- [ ] Define GSC MCP tools
- [ ] Document limitations

### Module 8.3: GA4 Integration Design

**Deliverables:**

- GA4 integration design doc
- Credential requirements
- Data schema
- API/MCP tool design

**Acceptance Criteria:**

- Required metrics are defined.
- URL mapping to `content_nodes` is defined.
- Conversion signals are defined.
- GA4 MCP tools are defined.

**Tasks:**

- [ ] Define GA4 fields
- [ ] Define credential flow
- [ ] Define sync process
- [ ] Define conversion signals
- [ ] Define GA4 MCP tools

### Module 8.4: MCP Design Pack

**Deliverables:**

- MCP architecture doc
- Tool lists
- Permission boundaries
- Phase-wise MCP rollout

**Acceptance Criteria:**

- All 12 MCP servers are accounted for.
- Phase 2 MCPs are clearly separated from later MCPs.
- Tool permissions are scoped.
- No write/publish tools are enabled without approval.

**Tasks:**

- [ ] Document Content Inventory MCP
- [ ] Document Knowledge Graph MCP
- [ ] Document Crawler MCP
- [ ] Document SEO Rules MCP
- [ ] Document GSC MCP
- [ ] Document GA4 MCP
- [ ] List deferred MCPs

### DAY 8 SUCCESS CHECKLIST

- [ ] SEO opportunity foundation works
- [ ] GSC integration design complete
- [ ] GA4 integration design complete
- [ ] MCP design pack complete

---

## DAY 9: RELATIONSHIP API, GRAPH VISIBILITY, TESTING AND DOCUMENTATION

**Date:** Wednesday, July 15, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Expose relationships through API/dashboard and complete testing/documentation.

### Module 9.1: Relationship API Endpoints

**Deliverables:**

- Relationship list endpoint
- Page relationships endpoint
- Entity relationships endpoint
- Relationship stats endpoint

**Acceptance Criteria:**

- Relationships can be queried by page.
- Relationships can be queried by entity.
- Relationship types are visible.
- Pending/approved/rejected status is visible.

**Tasks:**

- [ ] Add `/api/relationships`
- [ ] Add `/api/pages/{node_id}/relationships`
- [ ] Add `/api/entities/{entity_id}/relationships`
- [ ] Add `/api/relationships/types`
- [ ] Add `/api/intelligence/relationship-coverage`

### Module 9.2: Testing

**Deliverables:**

- Unit tests
- API tests
- Data validation tests
- Agent dry-run tests

**Acceptance Criteria:**

- Entity extraction tests pass.
- Normalization tests pass.
- Relationship generation tests pass.
- API endpoint tests pass.

**Tasks:**

- [ ] Test entity normalization
- [ ] Test duplicate entity prevention
- [ ] Test page-to-entity mapping
- [ ] Test relationship creation
- [ ] Test relationship scoring
- [ ] Test API endpoints

### Module 9.3: Documentation

**Deliverables:**

- Updated schema docs
- Agent 2 docs
- Agent 3 docs
- API docs
- Known limitations

**Acceptance Criteria:**

- A future developer can understand Phase 2 output.
- Commands are documented.
- Report methodology is documented.
- Limitations are clear.

**Tasks:**

- [ ] Write Agent 2 doc
- [ ] Write Agent 3 doc
- [ ] Update API doc
- [ ] Update schema doc
- [ ] Write known limitations

### DAY 9 SUCCESS CHECKLIST

- [ ] Relationship API working
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Known limitations documented

---

## DAY 10: FINAL VALIDATION, REPORTS AND PHASE 2 HANDOFF

**Date:** Thursday, July 16, 2026  
**Deadline:** 6:00 PM IST  
**Owner:** Shrey

### Objective

Verify Phase 2 end-to-end, package handoff material, and prepare the project for Phase 3 recommendation engine work.

### Module 10.1: Final End-To-End Validation

**Deliverables:**

- Full Phase 2 validation report
- DB counts
- Entity coverage
- Relationship coverage
- Opportunity summary

**Acceptance Criteria:**

- Agent 2 runs successfully.
- Agent 3 runs successfully.
- API endpoints respond.
- Reports are generated.
- No critical blocker remains.

**Tasks:**

- [ ] Run migration validation
- [ ] Run Agent 2
- [ ] Run Agent 3
- [ ] Run SEO opportunity foundation
- [ ] Run API smoke tests
- [ ] Run test suite
- [ ] Generate final validation report

### Module 10.2: Handoff Package

**Deliverables:**

- Phase 2 handoff document
- Final metrics
- What was built
- What works
- Known limitations
- Phase 3 recommendations

**Acceptance Criteria:**

- Handoff is complete and readable.
- Phase 3 dependencies are clear.
- Integration gaps are clear.
- Commands and reports are linked.

**Tasks:**

- [ ] Write Phase 2 handoff
- [ ] Summarize all deliverables
- [ ] Summarize DB schema changes
- [ ] Summarize API changes
- [ ] Summarize GSC/GA4 readiness
- [ ] Summarize MCP readiness
- [ ] List next Phase 3 tasks

### Module 10.3: Final Repository Cleanup

**Deliverables:**

- Clean worktree
- Final commit
- Phase 2 tag
- Optional GitHub push

**Acceptance Criteria:**

- No accidental temp files committed.
- Reports and docs are organized.
- Commit message is clear.
- Tag identifies Phase 2 completion.

**Tasks:**

- [ ] Review git status
- [ ] Remove unnecessary temp files
- [ ] Commit Phase 2 work
- [ ] Create `v2.0-phase2-intelligence-layer` tag
- [ ] Push if approved

### DAY 10 SUCCESS CHECKLIST

- [ ] Final validation complete
- [ ] Handoff complete
- [ ] Tests pass or known failures documented
- [ ] Git status reviewed
- [ ] Phase 2 ready for Phase 3

---

## FINAL PHASE 2 DELIVERABLES

- Phase 2 PRD
- Database migration script
- Updated schema documentation
- Agent 2 Entity Extraction Agent
- Agent 2 execution report
- Entity normalization utilities
- Page-to-entity mapping table
- Manual correction workflow
- Entity API endpoints
- Entity coverage report
- Agent 3 Relationship Mapping Agent
- Relationship scoring logic
- Relationship API endpoints
- Relationship coverage report
- Semantic similarity foundation
- Business priority score foundation
- Intent stage mapping
- AI readiness score foundation
- SEO opportunity foundation (including search opportunity score)
- Relationship type coverage matrix vs master PRD
- GSC integration design
- GA4 integration design
- MCP design pack
- Updated API documentation
- Updated dashboard/API usage guide
- Test coverage for Phase 2 logic
- Phase 2 handoff document

---

## PHASE 2 QUALITY METRICS

| Metric | Target |
|---|---:|
| Active pages with at least one entity | 95%+ |
| Active pages with geography entity | 90%+ |
| Active pages with industry or market entity | 80%+ |
| Duplicate normalized entities | 0 critical duplicates |
| Relationship edges generated for active pages | 70%+ pages have at least one edge |
| Low-confidence entities visible | 100% visible in report/API |
| Active pages with business priority band (High/Medium/Low) | 100% |
| Active pages with intent stage | 100% |
| Active pages with AI-readiness score (computable-subset) | 100% |
| Entity API response time | under 500 ms local |
| Relationship API response time | under 700 ms local |
| Agent dry-run support | required |
| JSON execution reports | required |
| Tests for core extraction/scoring | required |

---

## PHASE 2 RISKS AND MITIGATIONS

| Risk | Impact | Mitigation |
|---|---|---|
| Entity extraction is inaccurate | Bad relationships later | Use deterministic rules, confidence scores, manual correction |
| Entity duplicates are created | Dirty graph | Normalize names and enforce uniqueness |
| Market extraction is weak from title/slug alone | Low coverage | Use title, H1, meta, URL and existing fields together |
| Relationship edges are noisy | Bad recommendations later | Keep status pending and require confidence thresholds |
| GSC/GA4 credentials unavailable | Integration delay | Build schema/design/stubs first |
| Embedding dependencies are heavy | Slower delivery | Use TF-IDF MVP first |
| Dashboard becomes too broad | Miss deadline | API-first delivery; visual dashboard can follow |
| Scope expands into Phase 3 | Delay | Do not build full recommendations in Phase 2 |

---

## PHASE 3 READINESS CRITERIA

Phase 3 can begin when:

- Entities are extracted and normalized.
- Page-to-entity mapping is available.
- Relationship edges exist.
- Relationship scores exist.
- Semantic similarity score exists.
- Business priority score exists.
- SEO opportunities are visible.
- GSC/GA4 integration path is documented.
- MCP architecture is documented.
- API exposes entities and relationships.

Phase 3 will then focus on:

- Link recommendation engine
- Anchor text agent
- Placement suggestions
- SEO validation workflow
- Editorial review queue
- Recommendation scoring

---

## APPENDIX A: 10-DAY DEADLINE DATES

| Day | Date | Deadline | Focus |
|---:|---|---|---|
| 1 | Tuesday, July 7, 2026 | 6:00 PM IST | Scope, audit, schema design |
| 2 | Wednesday, July 8, 2026 | 6:00 PM IST | Migration and entity foundation |
| 3 | Thursday, July 9, 2026 | 6:00 PM IST | Agent 2 MVP |
| 4 | Friday, July 10, 2026 | 6:00 PM IST | Normalization and correction |
| 5 | Saturday, July 11, 2026 | 6:00 PM IST | Entity API and coverage |
| 6 | Sunday, July 12, 2026 | 6:00 PM IST | Agent 3 MVP |
| 7 | Monday, July 13, 2026 | 6:00 PM IST | Scoring, semantic similarity, business priority |
| 8 | Tuesday, July 14, 2026 | 6:00 PM IST | SEO opportunities, GSC/GA4, MCP design |
| 9 | Wednesday, July 15, 2026 | 6:00 PM IST | Relationship API, tests, docs |
| 10 | Thursday, July 16, 2026 | 6:00 PM IST | Validation, handoff, cleanup |

---

## APPENDIX B: SOLO OWNERSHIP RULE

All Phase 2 work is owned by Shrey.

No tasks are assigned to Vansh, QA, tech team, SEO team, content team, or any other person in this execution plan. Other teams may be referenced as future users or reviewers, but Phase 2 execution ownership remains with Shrey.

---

## CONCLUSION

Phase 2 is the intelligence foundation of the Ken Intelligence Linking Engine. It transforms the Phase 1 content inventory into a searchable, explainable knowledge graph by adding entities, relationships, semantic similarity, business priority and early SEO opportunity intelligence.

The phase must stay disciplined: build the intelligence layer first, prepare GSC/GA4/MCP foundations, and avoid jumping too early into final link recommendations. A strong Phase 2 will make Phase 3 recommendation generation faster, safer and more accurate.
