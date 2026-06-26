# KEN INTELLIGENCE LINKING ENGINE - COMPLETE EXECUTION PLAN
## Full System Build: Local Development → Tech Team Handoff

**Version:** 1.0  
**Date:** June 2026  
**Team:** Vansh (Lead) + Shrey (Automation Intern)  
**Timeline:** 6-8 weeks to local MVP + handoff  
**Scope:** All agents, all servers, complete system (local first, website deployment later)  
**Architecture:** Supabase (free vector DB) + Python backend + Local testing (500 URLs)

---

## TABLE OF CONTENTS

1. [Executive Context](#executive-context)
2. [Technology Stack (Free Tier)](#technology-stack-free-tier)
3. [System Architecture - Local First](#system-architecture--local-first)
4. [Phase Breakdown (6-8 Weeks)](#phase-breakdown-6-8-weeks)
5. [All 14 Agents - Implementation Order](#all-14-agents--implementation-order)
6. [All 12 MCP Servers - Specs](#all-12-mcp-servers--specs)
7. [Data Models & Database Schema](#data-models--database-schema)
8. [Week-by-Week Detailed Plan](#week-by-week-detailed-plan)
9. [Testing Strategy](#testing-strategy)
10. [Handoff to Tech Team](#handoff-to-tech-team)
11. [Repository Structure](#repository-structure)
12. [Success Criteria](#success-criteria)

---

## EXECUTIVE CONTEXT

### What We're Building

A complete, production-ready agent-based internal linking system that:
- ✅ Understands content relationships (entities, markets, geography)
- ✅ Generates intelligent link recommendations (14 agents)
- ✅ Validates recommendations for SEO safety
- ✅ Tracks evidence and supports research validation
- ✅ Measures impact (links generated, approvals, engagement)
- ✅ Runs as self-healing automated system

### Build Approach: Local-First

**Phase 1-5 (Weeks 1-8): Local Development**
- You + Shrey build everything locally
- Test with 500 Ken Research URLs
- No website deployment
- No AWS/cloud infrastructure
- Use free tools (Supabase, free APIs)
- Deliver complete codebase + documentation

**Phase 6 (After Week 8): Tech Team Handoff**
- Tech team takes your code
- Scales to full URL inventory
- Deploys to Ken website
- Integrates with CMS
- Goes live

### Why This Approach?

✅ You control development completely  
✅ Fast iteration without infrastructure overhead  
✅ Prove concept locally before website risk  
✅ Tech team handles production deployment  
✅ Clear separation of concerns  

---

## TECHNOLOGY STACK (Free Tier)

### Backend & Language
- **Language:** Python 3.11
- **Framework:** FastAPI (or Flask if simpler)
- **Task Queue:** APScheduler (local) or BullMQ + Redis (local)
- **Database:** PostgreSQL (local) or SQLite (simplest)
- **Vector Database:** Supabase (free tier) with pgvector extension
- **Embeddings:** Groq (free API) or Gemini (free API)
- **LLM:** Groq or Gemini (free APIs)

### File Storage & Persistence
- **Local Storage:** /data folder in repo
- **CSV/JSON:** For intermediate data
- **Database:** Supabase (free tier PostgreSQL + vector search)

### Development Tools
- **Version Control:** GitHub
- **API Testing:** Postman (free) or curl
- **Monitoring:** Simple logging to console/file
- **Documentation:** Markdown in repo

### Free Tier Limits (Sufficient)
- **Supabase:** 500 MB free tier (plenty for 500 URLs)
- **Groq API:** 30 requests/minute
- **Gemini API:** 60 requests/minute
- **GitHub:** Unlimited private repos

### Total Cost
**$0** (completely free)

---

## SYSTEM ARCHITECTURE - LOCAL FIRST

```
┌─────────────────────────────────────────────────────────────┐
│                     INPUT SOURCES                            │
│  (CSV files, local URLs, sample data for 500 URLs)          │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ↓                       ↓
    ┌─────────────┐      ┌──────────────────┐
    │  SQLite/    │      │  Supabase        │
    │  PostgreSQL │      │  (Vector DB)     │
    │  (Local)    │      │  (pgvector)      │
    └──────┬──────┘      └────────┬─────────┘
           │                      │
           └──────────┬───────────┘
                      ↓
        ┌─────────────────────────────────┐
        │   MCP Server Layer (Python)     │
        │  (12 local MCP servers)         │
        └──────────┬──────────────────────┘
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
    ┌─────────────────┐  ┌──────────────────┐
    │  LLM Agents     │  │  Groq/Gemini API │
    │  (14 agents)    │  │  (Free)          │
    └─────────────────┘  └──────────────────┘
        │
        ↓
    ┌─────────────────────────────────┐
    │  FastAPI Server                 │
    │  (Local development server)     │
    └─────────────────────────────────┘
        │
        ↓
    ┌─────────────────────────────────┐
    │  Dashboard                      │
    │  (Approval UI, metrics)         │
    └─────────────────────────────────┘
```

### Key Difference from Production

**Local Development:**
- Python agents run in same process
- Direct database connections
- No containerization
- No cloud infrastructure
- All in single GitHub repo

**Production (Tech Team Handles):**
- Agents in separate microservices
- API layer for external calls
- Docker containers
- Kubernetes orchestration
- Cloud deployment
- CMS integration

---

## PHASE BREAKDOWN (6-8 WEEKS)

### Phase 1: Foundation & Data Layer (Week 1-2)
**Goal:** Set up infrastructure, load data, create core database

**Week 1:**
- Day 1-2: GitHub repo, local environment setup
- Day 3-4: Supabase setup, PostgreSQL local
- Day 5: CSV → Database loading (500 URLs)
- Day 6: Data validation + cleaning
- Day 7: Schema design completion

**Week 2:**
- Day 8-9: Content inventory agent (MVP-1 equivalent)
- Day 10-11: Data enrichment (canonicals, crawl depth)
- Day 12-13: Basic dashboard backend (endpoints only)
- Day 14: Testing + fixes

**Deliverable:** 500 URLs in database, clean, canonical, classified, ready for agents

---

### Phase 2: Intelligence Layer (Week 3-4)
**Goal:** Extract entities, map relationships, build knowledge graph

**Week 3:**
- Day 15-16: Entity extraction agent + prompt
- Day 17-18: Entity extraction on 500 URLs
- Day 19: Entity validation (manual review of 50)
- Day 20: Taxonomy creation (industries, countries, markets)
- Day 21: Entity database storage

**Week 4:**
- Day 22-23: Relationship mapping agent + prompt
- Day 24-25: Generate relationships between all 500 URLs
- Day 26: Business priority scoring agent
- Day 27: Semantic embeddings generation → Supabase vector DB
- Day 28: Testing relationships + validation

**Deliverable:** Knowledge graph complete, 500 URLs with entities + relationships + priorities

---

### Phase 3: Recommendation Engine (Week 5-6)
**Goal:** Generate intelligent link recommendations, validate for SEO

**Week 5:**
- Day 29-30: Link scoring formula implementation
- Day 31-32: Link recommendation agent core logic
- Day 33-34: Anchor text generation agent
- Day 35: Placement recommendation agent
- Day 36: Score calculation on all URL pairs

**Week 6:**
- Day 37-38: SEO validation agent + rules engine
- Day 39: Risk assessment agent
- Day 40: Editorial review agent (prep reviews)
- Day 41-42: Generate 500+ recommendations for MVP URLs
- Day 43-44: Spot check quality (manual validation of 50 recommendations)

**Deliverable:** 500+ high-quality recommendations, validated, ready for approval

---

### Phase 4: Deployment & Measurement Agents (Week 7)
**Goal:** Build deployment tracking, measurement, and automation agents

**Week 7:**
- Day 45-46: Deployment agent (simulate CMS insertion, local file output)
- Day 47-48: Measurement agent (track hypothetical impact)
- Day 49: Link decay agent (find broken links, outdated links)
- Day 50-51: Dashboard completion (full approval UI + metrics)
- Day 52: End-to-end testing (500 URLs through full pipeline)

**Deliverable:** Complete system works end-to-end with 500 URLs

---

### Phase 5: All MCP Servers + Full Automation (Week 8)
**Goal:** Build all 12 MCP servers, implement agent orchestration

**Week 8:**
- Day 53-54: Build all 12 MCP servers (Python-based, local)
- Day 55: Agent orchestration + scheduling
- Day 56: Error handling + logging
- Day 57: Full system stress test (1000 simulated URLs)
- Day 58-60: Documentation, code cleanup, repo preparation
- Day 61-62: Tech team handoff package preparation

**Deliverable:** 
- Complete codebase with all agents + servers
- Full documentation
- Testing reports
- Ready for tech team integration

---

## ALL 14 AGENTS - IMPLEMENTATION ORDER

### Agent Bucket 1: Data Foundation (Phase 1)
**1. Content Inventory Agent**
- Input: URLs (CSV)
- Actions: Crawl metadata, classify content type, extract canonical
- Output: content_nodes table
- Implementation: Days 8-9 (Week 2)
- Dependencies: None
- MCP: Content Inventory MCP (reads from local DB)

---

### Agent Bucket 2: Intelligence (Phase 2)
**2. Entity Extraction Agent**
- Input: Page content from content_nodes
- Actions: Extract industry, market, country, segment, entities
- Output: content_entities table + entity_to_page mapping
- Implementation: Days 15-16 (Week 3)
- Dependencies: Agent 1 (needs pages)
- MCP: None (direct Groq/Gemini call)

**3. Relationship Mapping Agent**
- Input: content_nodes + content_entities
- Actions: Identify relationships between pages
- Output: relationship_edges table
- Implementation: Days 22-23 (Week 4)
- Dependencies: Agents 1, 2 (needs entities)
- MCP: Knowledge Graph MCP (stores relationships)

**4. SEO Opportunity Agent**
- Input: content_nodes, crawl data, link data
- Actions: Find orphan pages, underlinked pages, ranking opportunities
- Output: SEO opportunity queue
- Implementation: Days 24-25 (Week 4, parallel with Agent 3)
- Dependencies: Agent 1
- MCP: Crawler MCP (crawl analysis), Search Console MCP (GSC data)

**5. Business Priority Agent**
- Input: content_nodes + revenue data + strategic priority
- Actions: Score pages by business value
- Output: business_priority field in content_nodes
- Implementation: Days 26-27 (Week 4)
- Dependencies: Agent 1
- MCP: None (internal scoring)

---

### Agent Bucket 3: Recommendations (Phase 3)
**6. Link Recommendation Agent**
- Input: source page + related pages + scores
- Actions: Generate actual recommendations with all metadata
- Output: link_recommendations table
- Implementation: Days 29-34 (Week 5)
- Dependencies: Agents 1-5
- MCP: Content Inventory MCP, Knowledge Graph MCP, Embedding Search MCP

**7. Anchor Text Agent**
- Input: source page + target page + context
- Actions: Generate 5 anchor text variations
- Output: anchor_banks table
- Implementation: Days 35-36 (Week 5)
- Dependencies: Agent 6
- MCP: None (direct LLM call)

**8. Paragraph Evidence Agent**
- Input: Page paragraphs + content_nodes
- Actions: Map paragraphs to evidence, create knowledge hashes
- Output: paragraph_evidence_map table
- Implementation: Days 37-38 (Week 6, parallel)
- Dependencies: Agent 1
- MCP: Evidence Library MCP, Embedding Search MCP

**9. Section Purpose Agent**
- Input: Page structure + paragraphs
- Actions: Classify sections, recommend section-level links
- Output: section_purpose_map table
- Implementation: Days 39-40 (Week 6)
- Dependencies: Agent 8
- MCP: None (direct analysis)

**10. SEO Validation Agent**
- Input: Recommendations (source + target + anchor)
- Actions: Validate crawlability, canonical, anchor quality, faceted URLs
- Output: risk_flags, validation_result in link_recommendations
- Implementation: Days 41-42 (Week 6)
- Dependencies: Agent 6
- MCP: SEO Rules MCP, Crawler MCP

**11. Editorial Review Agent**
- Input: Validated recommendations
- Actions: Prepare human-friendly review notes
- Output: editorial_notes field
- Implementation: Days 43-44 (Week 6)
- Dependencies: Agents 6, 10
- MCP: None (text formatting)

---

### Agent Bucket 4: Deployment & Measurement (Phase 4-5)
**12. Deployment Agent**
- Input: Approved recommendations
- Actions: Simulate CMS insertion, create deployment logs
- Output: deployment_logs table, modified files/CSV
- Implementation: Days 45-46 (Week 7)
- Dependencies: Agent 11
- MCP: CMS MCP, Deployment MCP

**13. Measurement Agent**
- Input: Deployed links + hypothetical GA4/GSC data
- Actions: Track impact (clicks, conversions, rankings)
- Output: performance_logs table
- Implementation: Days 47-48 (Week 7)
- Dependencies: Agent 12
- MCP: GA4 MCP, Search Console MCP

**14. Link Decay Agent**
- Input: All links + page status
- Actions: Find broken links, redirect chains, outdated links
- Output: Link hygiene report
- Implementation: Days 49-50 (Week 7)
- Dependencies: Agent 1, 12
- MCP: Crawler MCP

---

## ALL 12 MCP SERVERS - SPECS

### MCP-1: Content Inventory Server
**Purpose:** Provide structured access to page metadata and content inventory

**Tools:**
- `get_page_by_url(url)` → Page data
- `get_page_by_id(node_id)` → Page data
- `search_pages(query, filters)` → List of pages
- `list_pages_by_industry(industry)` → Pages
- `list_pages_by_country(country)` → Pages
- `list_pages_by_market(market)` → Pages
- `list_pages_by_node_type(type)` → Pages
- `get_canonical_url(url)` → Canonical
- `get_page_status(url)` → Status
- `get_internal_links_in(url)` → Links pointing to this
- `get_internal_links_out(url)` → Links from this
- `get_orphan_pages()` → List of orphans
- `get_recently_published_pages()` → Recent pages

**Database Tables:** content_nodes

**Used By:** Agents 1, 4, 6, 10, 12, 14

**Implementation:** Week 1-2

---

### MCP-2: Knowledge Graph Server
**Purpose:** Query and manage relationship index

**Tools:**
- `get_related_entities(entity_id)` → Related entities
- `get_relationships_for_page(url)` → All relationships
- `get_parent_child_relationships(url)` → Hierarchy
- `get_global_local_relationships()` → Geo relationships
- `get_country_region_relationships()` → Country relationships
- `get_case_study_relationships(url)` → Case study links
- `get_evidence_relationships(url)` → Evidence links
- `create_relationship_edge(source, target, type, confidence)` → Create
- `update_relationship_confidence(edge_id, score)` → Update
- `reject_relationship(edge_id)` → Reject
- `get_relationship_explanation(edge_id)` → Explanation text

**Database Tables:** relationship_edges, content_entities

**Used By:** Agents 3, 5, 6, 9

**Implementation:** Week 3-4

---

### MCP-3: Embedding Search Server
**Purpose:** Find semantically similar pages and paragraphs

**Tools:**
- `semantic_search_pages(query, limit)` → Similar pages
- `semantic_search_paragraphs(query, limit)` → Similar paragraphs
- `find_similar_reports(report_url, limit)` → Similar reports
- `find_similar_articles(article_url, limit)` → Similar articles
- `find_similar_case_studies(url, limit)` → Similar case studies
- `find_duplicate_paragraphs(paragraph_text)` → Duplicates
- `find_claim_similarity(claim_text)` → Similar claims
- `get_embedding_similarity_score(text1, text2)` → Score

**Database Tables:** page_embeddings, paragraph_embeddings

**Used By:** Agents 2, 6, 8, 14

**Implementation:** Week 3-4

---

### MCP-4: Evidence Library Server
**Purpose:** Connect paragraphs to research proof

**Tools:**
- `search_evidence(query)` → Evidence items
- `get_evidence_by_id(evidence_id)` → Evidence data
- `search_case_studies(query)` → Case studies
- `search_charts(query)` → Charts/images
- `search_tables(query)` → Data tables
- `search_product_images(query)` → Product images
- `map_paragraph_to_evidence(paragraph_id, evidence_id)` → Link
- `get_evidence_confidence_score(paragraph, evidence)` → Score
- `flag_unsupported_claim(paragraph_id, reason)` → Flag

**Database Tables:** paragraph_evidence_map, evidence_library, case_studies

**Used By:** Agents 8, 9, 11

**Implementation:** Week 4-5

---

### MCP-5: SEO Rules Server
**Purpose:** Validate link recommendations for SEO safety

**Tools:**
- `validate_anchor_text(anchor)` → Valid/Invalid + reason
- `validate_crawlable_href(url)` → Crawlable/Not
- `validate_canonical_target(url)` → Canonical check
- `validate_indexable_target(url)` → Indexable check
- `validate_link_placement(page_type, placement)` → Valid placement
- `validate_anchor_diversity(target_url, anchor)` → Diversity check
- `validate_link_count(source_url, new_count)` → Count check
- `validate_faceted_url_risk(url)` → Faceted check
- `validate_internal_nofollow_risk(source, target)` → Nofollow check
- `validate_redirect_risk(url)` → Redirect chain check
- `validate_schema_breadcrumb(url)` → Breadcrumb check

**Database Tables:** None (pure validation rules)

**Used By:** Agents 10, 11, 12

**Implementation:** Week 5-6

---

### MCP-6: Crawler Server
**Purpose:** Audit crawlability and link health

**Tools:**
- `crawl_url(url)` → Crawl result
- `crawl_section(url, section)` → Section crawl
- `get_broken_links(url)` → Broken links on page
- `get_redirect_chains(url)` → Redirect chains
- `get_non_canonical_internal_links(url)` → Non-canonical links
- `get_pages_deeper_than_depth(depth)` → Deep pages
- `get_pages_without_breadcrumbs()` → Missing breadcrumbs
- `get_pages_without_toc()` → Missing TOC
- `get_pages_with_excessive_links(limit)` → Over-linked
- `get_pages_with_js_only_links()` → JS-only links
- `get_blocked_urls()` → Blocked pages
- `get_faceted_url_patterns()` → Faceted patterns

**Database Tables:** crawl_logs

**Used By:** Agents 1, 4, 10, 14

**Implementation:** Week 2, 6

---

### MCP-7: Jira Server
**Purpose:** Convert recommendations into execution tickets

**Tools:**
- `create_jira_epic(name, description, priority)` → Epic ID
- `create_jira_story(epic_id, description, assignee)` → Story ID
- `create_jira_task(story_id, task, assignee)` → Task ID
- `update_task_status(task_id, status)` → Updated
- `assign_owner(task_id, owner)` → Assigned
- `attach_recommendation_export(task_id, file)` → Attached
- `create_monthly_audit_task()` → Task ID

**Database Tables:** jira_sync_log

**Used By:** Agent 11, 12

**Implementation:** Week 6-7

---

### MCP-8: Search Console Server
**Purpose:** Use search data to prioritize links

**Tools:**
- `get_page_queries(url)` → Search queries
- `get_page_impressions(url)` → Impressions count
- `get_page_clicks(url)` → Clicks count
- `get_page_ctr(url)` → Click-through rate
- `get_page_average_position(url)` → Avg ranking
- `get_pages_with_high_impressions_low_ctr()` → Opportunities
- `get_pages_ranking_positions_4_to_20()` → Position 4-20
- `get_indexing_status()` → Indexed/not indexed
- `get_crawl_errors()` → Crawl issues

**Database Tables:** gsc_data (simulated locally)

**Used By:** Agents 4, 13

**Implementation:** Week 7

---

### MCP-9: GA4 Server
**Purpose:** Use behavior and conversion data

**Tools:**
- `get_page_sessions(url)` → Session count
- `get_page_engagement(url)` → Engagement rate
- `get_scroll_depth(url)` → Average scroll %
- `get_internal_link_clicks(url)` → Link clicks
- `get_conversion_events(url)` → Conversions
- `get_report_enquiries(url)` → Report enquiries
- `get_sample_requests(url)` → Sample requests
- `get_lead_sources()` → Lead source tracking
- `get_assisted_conversions(url)` → Assisted conversions

**Database Tables:** ga4_data (simulated locally)

**Used By:** Agents 5, 13

**Implementation:** Week 7

---

### MCP-10: CMS Server
**Purpose:** Control content edits and draft link insertion

**Tools:**
- `fetch_cms_content(url)` → CMS content
- `create_link_insertion_draft(url, link, anchor, placement)` → Draft
- `update_related_reports_block(url, links)` → Update block
- `update_related_articles_block(url, links)` → Update block
- `update_toc_block(url, structure)` → Update TOC
- `update_breadcrumb_mapping(url, breadcrumbs)` → Update
- `submit_for_editorial_review(draft_id)` → Submit
- `publish_approved_change(draft_id)` → Publish
- `rollback_change(deployment_id)` → Rollback

**Database Tables:** deployment_logs, cms_drafts

**Used By:** Agent 12

**Implementation:** Week 7 (simulated locally)

---

### MCP-11: Report Store Server
**Purpose:** Access report metadata and inventory

**Tools:**
- `search_reports(query, filters)` → Reports
- `get_report_by_id(report_id)` → Report data
- `get_report_metadata(report_id)` → Metadata
- `list_reports_by_industry(industry)` → Industry reports
- `list_reports_by_country(country)` → Country reports
- `list_reports_by_market(market)` → Market reports
- `get_report_update_date(report_id)` → Last updated
- `get_related_reports(report_id)` → Related reports

**Database Tables:** reports (reference)

**Used By:** Agents 1, 6, 9

**Implementation:** Week 1-2

---

### MCP-12: Deployment Server
**Purpose:** Track and manage deployment lifecycle

**Tools:**
- `create_cms_draft(recommendation_id)` → Draft ID
- `insert_link(draft_id, link_html, location)` → Inserted
- `update_block(draft_id, block_type, content)` → Updated
- `publish_change(draft_id, notes)` → Published
- `rollback_change(deployment_id)` → Rolled back
- `get_deployment_status(deployment_id)` → Status
- `log_deployment(recommendation_id, action, result)` → Logged
- `get_deployment_history(url)` → History

**Database Tables:** deployment_logs, deployment_history

**Used By:** Agent 12

**Implementation:** Week 7

---

## DATA MODELS & DATABASE SCHEMA

### Core Tables (PostgreSQL/SQLite)

```sql
-- 1. Content Inventory
CREATE TABLE content_nodes (
  node_id UUID PRIMARY KEY,
  url TEXT UNIQUE NOT NULL,
  canonical_url TEXT,
  title TEXT,
  meta_title VARCHAR(160),
  meta_description VARCHAR(160),
  h1 TEXT,
  content_type VARCHAR(50),
  node_type VARCHAR(50),
  industry VARCHAR(100),
  sub_industry VARCHAR(100),
  market VARCHAR(100),
  segment VARCHAR(100),
  country VARCHAR(100),
  region VARCHAR(100),
  global_or_local VARCHAR(20),
  intent_stage VARCHAR(50),
  business_priority VARCHAR(20),
  conversion_value DECIMAL,
  published_date DATETIME,
  updated_date DATETIME,
  indexability_status VARCHAR(50),
  crawl_depth INT,
  internal_links_in INT DEFAULT 0,
  internal_links_out INT DEFAULT 0,
  orphan_status VARCHAR(20),
  page_authority_score DECIMAL,
  search_opportunity_score DECIMAL,
  ai_readiness_score DECIMAL,
  status VARCHAR(50) DEFAULT 'active',
  created_at DATETIME,
  updated_at DATETIME
);

-- 2. Entities
CREATE TABLE content_entities (
  entity_id UUID PRIMARY KEY,
  entity_name VARCHAR(255),
  entity_type VARCHAR(50),
  normalized_name VARCHAR(255),
  aliases JSONB,
  parent_entity_id UUID,
  industry VARCHAR(100),
  country VARCHAR(100),
  region VARCHAR(100),
  confidence_score DECIMAL,
  created_at DATETIME,
  updated_at DATETIME
);

-- 3. Relationships
CREATE TABLE relationship_edges (
  edge_id UUID PRIMARY KEY,
  source_node_id UUID REFERENCES content_nodes,
  target_node_id UUID REFERENCES content_nodes,
  source_entity_id UUID REFERENCES content_entities,
  target_entity_id UUID REFERENCES content_entities,
  relationship_type VARCHAR(100),
  relationship_direction VARCHAR(20),
  confidence_score DECIMAL,
  semantic_similarity_score DECIMAL,
  entity_overlap_score DECIMAL,
  geo_match_score DECIMAL,
  market_match_score DECIMAL,
  business_value_score DECIMAL,
  seo_value_score DECIMAL,
  created_by VARCHAR(100),
  reviewed_by VARCHAR(100),
  status VARCHAR(50),
  created_at DATETIME,
  updated_at DATETIME
);

-- 4. Link Recommendations
CREATE TABLE link_recommendations (
  recommendation_id UUID PRIMARY KEY,
  source_url TEXT,
  target_url TEXT,
  target_canonical_url TEXT,
  anchor_text VARCHAR(255),
  anchor_variant VARCHAR(255),
  placement_type VARCHAR(50),
  placement_section VARCHAR(255),
  suggested_sentence TEXT,
  relationship_type VARCHAR(100),
  link_score DECIMAL,
  seo_score DECIMAL,
  business_score DECIMAL,
  ai_readiness_score DECIMAL,
  confidence_score DECIMAL,
  risk_flag BOOLEAN,
  risk_reason TEXT,
  recommendation_reason TEXT,
  status VARCHAR(50) DEFAULT 'pending_approval',
  approved_by VARCHAR(100),
  deployed_by VARCHAR(100),
  deployed_at DATETIME,
  rollback_available BOOLEAN,
  created_at DATETIME,
  updated_at DATETIME
);

-- 5. Anchor Banks
CREATE TABLE anchor_banks (
  anchor_id UUID PRIMARY KEY,
  target_url TEXT,
  primary_anchor VARCHAR(255),
  secondary_anchors JSONB,
  long_tail_anchors JSONB,
  country_specific_anchors JSONB,
  market_specific_anchors JSONB,
  commercial_anchors JSONB,
  restricted_anchors JSONB,
  anchor_usage_count INT DEFAULT 0,
  last_used_date DATETIME,
  overuse_flag BOOLEAN
);

-- 6. Paragraph Evidence Mapping
CREATE TABLE paragraph_evidence_map (
  paragraph_id UUID PRIMARY KEY,
  page_id UUID REFERENCES content_nodes,
  paragraph_text TEXT,
  claim_type VARCHAR(100),
  market_entity VARCHAR(255),
  geo_entity VARCHAR(255),
  segment_entity VARCHAR(255),
  time_period VARCHAR(50),
  knowledge_hash VARCHAR(255),
  evidence_id UUID,
  case_study_id UUID,
  chart_id UUID,
  table_id UUID,
  image_id UUID,
  supporting_url TEXT,
  evidence_confidence_score DECIMAL,
  unsupported_claim_flag BOOLEAN,
  duplicate_claim_flag BOOLEAN
);

-- 7. Section Purpose Mapping
CREATE TABLE section_purpose_map (
  section_id UUID PRIMARY KEY,
  page_id UUID REFERENCES content_nodes,
  section_title VARCHAR(255),
  section_type VARCHAR(50),
  section_purpose TEXT,
  intent_stage VARCHAR(50),
  recommended_links JSONB,
  recommended_cta TEXT,
  missing_link_flag BOOLEAN,
  weak_section_flag BOOLEAN,
  created_at DATETIME,
  updated_at DATETIME
);

-- 8. Deployment Logs
CREATE TABLE deployment_logs (
  deployment_id UUID PRIMARY KEY,
  recommendation_id UUID REFERENCES link_recommendations,
  source_url TEXT,
  target_url TEXT,
  anchor_text VARCHAR(255),
  change_type VARCHAR(50),
  old_content_snapshot TEXT,
  new_content_snapshot TEXT,
  approved_by VARCHAR(100),
  deployed_by VARCHAR(100),
  deployed_at DATETIME,
  rollback_status VARCHAR(50),
  performance_tracking_id UUID
);

-- 9. Performance Logs
CREATE TABLE performance_logs (
  log_id UUID PRIMARY KEY,
  deployment_id UUID REFERENCES deployment_logs,
  metric_type VARCHAR(50),
  metric_value INT,
  recorded_at DATETIME,
  user_action VARCHAR(100)
);

-- 10. Crawl Logs
CREATE TABLE crawl_logs (
  crawl_id UUID PRIMARY KEY,
  url TEXT,
  crawl_time DATETIME,
  status_code INT,
  redirects JSONB,
  broken_links JSONB,
  crawl_result TEXT
);
```

### Vector Embeddings (Supabase)
```sql
-- Page embeddings (Supabase pgvector)
CREATE TABLE page_embeddings (
  id UUID PRIMARY KEY,
  url TEXT UNIQUE,
  content_chunk TEXT,
  embedding VECTOR(1536),
  created_at DATETIME
);

-- Paragraph embeddings
CREATE TABLE paragraph_embeddings (
  id UUID PRIMARY KEY,
  paragraph_id UUID,
  content TEXT,
  embedding VECTOR(1536),
  created_at DATETIME
);

CREATE INDEX ON page_embeddings USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON paragraph_embeddings USING ivfflat (embedding vector_cosine_ops);
```

---

## WEEK-BY-WEEK DETAILED PLAN

### WEEK 1: Foundation Setup

**Monday (Day 1-2)**
- [ ] Create GitHub repo (ken-linking-engine)
- [ ] Set up local Python environment (3.11 venv)
- [ ] Install dependencies: FastAPI, SQLAlchemy, Groq/Gemini SDK, Supabase client, APScheduler
- [ ] Create project folder structure
- [ ] Shrey: Learn project goals, GitHub workflow

**Tuesday-Wednesday (Day 3-4)**
- [ ] Set up Supabase free account + PostgreSQL database
- [ ] Create local SQLite backup database
- [ ] Design database schema (10 tables)
- [ ] Create database migrations/schema scripts
- [ ] Set up environment variables (.env file)

**Thursday (Day 5)**
- [ ] Create CSV with 500 sample Ken URLs (ask team for format)
- [ ] Write URL → Database loading script
- [ ] Load 500 URLs into local database
- [ ] Verify data integrity

**Friday (Day 6-7)**
- [ ] Write data validation script
- [ ] Check for duplicates, missing fields
- [ ] Cleanse data (remove params, normalize)
- [ ] Document schema in README
- [ ] Commit to GitHub (initial commit)

**Deliverable:** Database ready with 500 clean URLs

---

### WEEK 2: Content Inventory Agent

**Monday-Tuesday (Day 8-9)**
- [ ] Agent 1: Content Inventory Agent implementation
- [ ] Extract metadata from local URLs (crawl HTML or use CMS API)
- [ ] Classify content types (report, article, market_page, etc.)
- [ ] Extract H1, title, meta description
- [ ] Check canonicals
- [ ] Check indexability status (robots meta, HTTP status)

**Wednesday (Day 10)**
- [ ] Calculate crawl depth (BFS from root)
- [ ] Count internal links in/out
- [ ] Calculate orphan status (0 links = orphan)
- [ ] Store in database

**Thursday (Day 11)**
- [ ] Basic dashboard endpoints (FastAPI):
  - GET /api/pages (list all)
  - GET /api/pages/orphans (orphan list)
  - GET /api/stats (metrics)
- [ ] Test endpoints with curl/Postman

**Friday (Day 12-14)**
- [ ] Test all 500 URLs through Agent 1
- [ ] Fix any errors
- [ ] Commit "Agent 1 complete"
- [ ] Document agent in README

**Deliverable:** 500 URLs fully inventoried and classified

---

### WEEK 3: Entity Extraction & Knowledge Graph Setup

**Monday-Tuesday (Day 15-16)**
- [ ] Agent 2: Entity Extraction Agent implementation
- [ ] Create Groq/Gemini prompt for entity extraction
- [ ] Extract: industry, market, country, segment, entities
- [ ] Store in content_entities table
- [ ] Run on all 500 URLs

**Wednesday (Day 17)**
- [ ] Shrey: Manual validation of 50 URLs (spot check)
- [ ] Feedback loop: improve prompts based on validation
- [ ] Re-run extraction if accuracy < 80%

**Thursday (Day 18)**
- [ ] Create taxonomy tables (industries, markets, countries, regions)
- [ ] Populate with valid values from extracted data
- [ ] Link content_nodes to taxonomy entities

**Friday (Day 19-21)**
- [ ] Test entity extraction end-to-end
- [ ] Create dashboard endpoint: GET /api/entities
- [ ] Commit "Agent 2 complete"

**Deliverable:** All 500 URLs have extracted entities, 80%+ accuracy

---

### WEEK 4: Relationships & Business Scoring

**Monday-Tuesday (Day 22-23)**
- [ ] Agent 3: Relationship Mapping Agent
- [ ] Create prompt for identifying relationships between pages
- [ ] Generate relationship types: market, geography, content, business, SEO
- [ ] Store in relationship_edges table
- [ ] Confidence scores for each relationship

**Wednesday (Day 24-25)**
- [ ] Agent 4: SEO Opportunity Agent
- [ ] Find orphan pages
- [ ] Find underlinked pages
- [ ] Identify high-authority pages
- [ ] Create opportunity scores

**Thursday (Day 26-27)**
- [ ] Agent 5: Business Priority Agent
- [ ] Score pages by revenue potential, strategic priority
- [ ] Store in content_nodes.business_priority
- [ ] Create priority segments (High/Medium/Low)

**Friday (Day 28)**
- [ ] Generate semantic embeddings using Groq (embed 500 pages)
- [ ] Store embeddings in Supabase vector DB
- [ ] Test semantic search: "Find pages related to EV market"
- [ ] Commit "Agents 3-5 complete"

**Deliverable:** Knowledge graph built, 500 pages scored by business priority, relationships mapped

---

### WEEK 5: Link Recommendation Engine Core

**Monday-Tuesday (Day 29-31)**
- [ ] Agent 6: Link Recommendation Agent (CORE)
- [ ] Implement link score formula (16 factors)
- [ ] For each URL, find top 10 candidate targets
- [ ] Score each candidate (0-100)
- [ ] Generate detailed recommendation with reason

**Wednesday (Day 32-33)**
- [ ] Agent 7: Anchor Text Agent
- [ ] Generate 5 anchor text variations per recommendation
- [ ] Enforce rules: natural, descriptive, no generics
- [ ] Country + market + intent format
- [ ] Store in anchor_banks table

**Thursday (Day 34-35)**
- [ ] Test recommendation generation on 10 URLs
- [ ] Manually validate 20 recommendations (Shrey)
- [ ] Adjust prompts based on feedback
- [ ] Run full batch on all 500 URLs

**Friday (Day 36)**
- [ ] Generate 500+ recommendations
- [ ] Calculate average link score
- [ ] Export to CSV for review
- [ ] Commit "Link Recommendation Engine complete"

**Deliverable:** 500+ recommendations generated, ready for SEO validation

---

### WEEK 6: SEO Validation & Editorial Review

**Monday-Tuesday (Day 37-39)**
- [ ] Agent 8: Paragraph Evidence Agent
- [ ] Break pages into paragraphs
- [ ] Extract claims (market size, trends, insights)
- [ ] Find supporting evidence (reports, case studies, data)
- [ ] Create knowledge hashes (unique claim fingerprints)
- [ ] Detect duplicates

**Wednesday (Day 40)**
- [ ] Agent 9: Section Purpose Agent
- [ ] Identify TOC sections
- [ ] Classify section purpose (overview, market size, trends, etc.)
- [ ] Recommend section-level links

**Thursday (Day 41-42)**
- [ ] Agent 10: SEO Validation Agent
- [ ] Validate all recommendations against SEO rules
- [ ] Check: canonical, crawlable, anchor quality, link count, faceted URLs
- [ ] Flag risky recommendations
- [ ] Generate risk reasons

**Friday (Day 43-44)**
- [ ] Agent 11: Editorial Review Agent
- [ ] Prepare human-friendly review notes
- [ ] Explain reason, SEO value, business value, risks
- [ ] Create review queue
- [ ] Commit "Agents 8-11 complete"

**Deliverable:** Recommendations validated, ready for approval, quality scores assigned

---

### WEEK 7: Deployment & Measurement Agents

**Monday-Tuesday (Day 45-47)**
- [ ] Agent 12: Deployment Agent
- [ ] Simulate CMS link insertion (output to file/JSON for now)
- [ ] Create deployment logs with metadata
- [ ] Generate deployment tracking IDs
- [ ] Create rollback capability (store old content)

**Wednesday (Day 48-49)**
- [ ] Agent 13: Measurement Agent
- [ ] Simulate GA4/GSC data (create mock data)
- [ ] Track: internal link clicks, conversions, rankings
- [ ] Calculate assisted conversions
- [ ] Store in performance_logs

**Thursday (Day 50-51)**
- [ ] Agent 14: Link Decay Agent
- [ ] Find broken links in deployed recommendations
- [ ] Find redirect chains
- [ ] Find links to archived content
- [ ] Generate hygiene report

**Friday (Day 52)**
- [ ] End-to-end test: 500 URLs through entire pipeline
- [ ] Validate all agents work together
- [ ] Create performance report
- [ ] Commit "All 14 agents complete"

**Deliverable:** All agents working, end-to-end pipeline validated with 500 URLs

---

### WEEK 8: MCP Servers & Full System Integration

**Monday-Tuesday (Day 53-54)**
- [ ] Build all 12 MCP servers (Python)
  - Content Inventory MCP
  - Knowledge Graph MCP
  - Embedding Search MCP
  - Evidence Library MCP
  - SEO Rules MCP
  - Crawler MCP
  - Jira MCP (mock)
  - Search Console MCP (mock data)
  - GA4 MCP (mock data)
  - CMS MCP (mock)
  - Report Store MCP
  - Deployment MCP

**Wednesday (Day 55)**
- [ ] Agent orchestration + scheduling (APScheduler)
- [ ] Define workflows:
  - "New page published" → run agents 1-6, 10
  - "Monthly audit" → run agent 14
  - "Weekly measurement" → run agent 13
- [ ] Error handling + logging
- [ ] Retry logic for API calls

**Thursday (Day 56-57)**
- [ ] Full system test with 1000 simulated URLs (test scaling)
- [ ] Performance testing
- [ ] Memory usage monitoring
- [ ] Fix any bottlenecks

**Friday (Day 58-62)**
- [ ] Code cleanup + refactoring
- [ ] Complete documentation
  - README (setup, running, architecture)
  - API documentation
  - Agent documentation
  - Database schema documentation
  - Deployment guide for tech team
- [ ] Create test reports
- [ ] Package for handoff
- [ ] Final commit "Production ready for handoff"

**Deliverable:** Complete system ready for tech team deployment

---

## TESTING STRATEGY

### Unit Testing (Each Agent)
```python
# tests/test_agents.py

def test_content_inventory_agent():
    # Test URL loading
    # Test canonicalization
    # Test content type classification
    assert len(loaded_urls) == 500
    
def test_entity_extraction_agent():
    # Test entity extraction
    # Test accuracy on known samples
    assert accuracy >= 0.80
    
def test_recommendation_agent():
    # Test link score calculation
    # Test recommendation generation
    assert avg_link_score >= 75
```

### Integration Testing
```python
# tests/test_integration.py

def test_full_pipeline():
    # Load URLs
    # Run all agents
    # Verify output tables
    # Check data relationships
    assert all_tables_populated()
```

### Spot Checks (Manual)
- Day 16: Shrey validates 50 entities (80%+ accuracy target)
- Day 34: Shrey validates 20 recommendations (relevance check)
- Day 42: Shrey spot checks risk flags (correctness)

### Performance Testing
- Day 56: Test system with 1000 URLs
- Measure: execution time, memory usage, DB query performance
- Optimize if needed

---

## HANDOFF TO TECH TEAM

### What You Deliver (End of Week 8)

**1. Complete Codebase**
```
ken-linking-engine/
├── agents/           # All 14 agents
├── mcp_servers/      # All 12 MCP servers
├── database/         # Schema, migrations
├── api/              # FastAPI endpoints
├── tests/            # Unit + integration tests
├── config/           # Config templates
├── docs/             # Complete documentation
├── data/             # Sample 500 URLs, test data
├── requirements.txt  # Python dependencies
├── .env.example      # Environment template
├── README.md         # Full setup guide
└── DEPLOYMENT.md     # Tech team deployment guide
```

**2. Documentation Package**
- Architecture guide (diagrams + explanation)
- Agent specifications (what each agent does)
- MCP server API documentation
- Database schema documentation
- API endpoints documentation
- Setup instructions for production
- Deployment checklist

**3. Testing & Reports**
- Unit test suite (pytest)
- Integration test results
- Performance benchmark (1000 URLs)
- Accuracy reports (entity extraction, recommendations)
- Sample data (500 URLs) + results

**4. Deployment Package for Tech Team**
```
DEPLOYMENT GUIDE:
1. Requirements
   - Python 3.11
   - PostgreSQL 14+
   - Redis (for task queue)
   - Supabase (for vector DB)
   
2. Installation
   - Clone repo
   - pip install -r requirements.txt
   - Run migrations
   - Set environment variables
   
3. Production Setup
   - Scale to full URL inventory
   - Integrate with Ken CMS API
   - Set up GA4/GSC data connections
   - Deploy agents to production
   
4. Integration Points
   - CMS webhook for "new page published"
   - GA4 API for conversion tracking
   - Search Console API for ranking data
   - Redis for task queuing
   
5. Monitoring
   - Set up logging/alerts
   - Dashboard for agent status
   - Error tracking
```

### Tech Team's Next Steps
1. Scale database (1000s of URLs instead of 500)
2. Integrate with Ken CMS (actual link insertion, not simulated)
3. Connect GA4/GSC APIs (real data, not mocks)
4. Deploy agents to production infrastructure
5. Set up monitoring and alerting
6. Go live on website

---

## REPOSITORY STRUCTURE

```
ken-linking-engine/
│
├── agents/
│   ├── __init__.py
│   ├── agent_1_content_inventory.py
│   ├── agent_2_entity_extraction.py
│   ├── agent_3_relationship_mapping.py
│   ├── agent_4_seo_opportunity.py
│   ├── agent_5_business_priority.py
│   ├── agent_6_link_recommendation.py
│   ├── agent_7_anchor_text.py
│   ├── agent_8_paragraph_evidence.py
│   ├── agent_9_section_purpose.py
│   ├── agent_10_seo_validation.py
│   ├── agent_11_editorial_review.py
│   ├── agent_12_deployment.py
│   ├── agent_13_measurement.py
│   └── agent_14_link_decay.py
│
├── mcp_servers/
│   ├── mcp_1_content_inventory.py
│   ├── mcp_2_knowledge_graph.py
│   ├── mcp_3_embedding_search.py
│   ├── mcp_4_evidence_library.py
│   ├── mcp_5_seo_rules.py
│   ├── mcp_6_crawler.py
│   ├── mcp_7_jira.py
│   ├── mcp_8_search_console.py
│   ├── mcp_9_ga4.py
│   ├── mcp_10_cms.py
│   ├── mcp_11_report_store.py
│   └── mcp_12_deployment.py
│
├── database/
│   ├── schema.sql
│   ├── migrations.py
│   ├── models.py
│   └── seed_data.csv
│
├── api/
│   ├── main.py
│   ├── routes/
│   │   ├── pages.py
│   │   ├── recommendations.py
│   │   ├── approvals.py
│   │   ├── deployments.py
│   │   └── metrics.py
│   └── dependencies.py
│
├── dashboard/
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── assets/
│
├── tests/
│   ├── test_agents.py
│   ├── test_integration.py
│   ├── test_mcp_servers.py
│   └── fixtures/
│
├── config/
│   ├── .env.example
│   ├── settings.py
│   └── logging.yaml
│
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── AGENTS.md
│   ├── MCP_SERVERS.md
│   ├── DATABASE.md
│   ├── API.md
│   ├── SETUP.md
│   └── DEPLOYMENT.md
│
├── scripts/
│   ├── load_urls.py
│   ├── run_agents.py
│   ├── generate_reports.py
│   └── cleanup.py
│
├── data/
│   ├── sample_urls.csv
│   └── test_results/
│
├── requirements.txt
├── .gitignore
├── .env.example
└── README.md
```

---

## SUCCESS CRITERIA

### By End of Week 8

**System Works:**
- [ ] All 14 agents implemented and functional
- [ ] All 12 MCP servers operational
- [ ] 500 URLs processed end-to-end
- [ ] 500+ recommendations generated
- [ ] 70%+ of recommendations judged useful (manual validation)
- [ ] No broken links to non-canonical URLs
- [ ] All agents integrate with MCP servers

**Code Quality:**
- [ ] All code committed to GitHub
- [ ] No console errors in full pipeline run
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Code documented (docstrings, comments)
- [ ] Repository clean and organized

**Documentation:**
- [ ] README complete (setup, running, architecture)
- [ ] API documentation complete
- [ ] Agent specifications documented
- [ ] Database schema documented
- [ ] Deployment guide written
- [ ] Example data provided (500 URLs + outputs)

**Ready for Tech Team:**
- [ ] Codebase is production-ready
- [ ] All dependencies listed
- [ ] Environment setup instructions clear
- [ ] No hardcoded values or credentials
- [ ] Deployment checklist provided
- [ ] Tech team can take over and scale

---

## METRICS TO TRACK

**By Week:**
- Week 1: Database ready, 500 URLs loaded
- Week 2: Agent 1 working, URLs classified
- Week 3: Agent 2 done, entities extracted
- Week 4: Agents 3-5 done, relationships + scoring
- Week 5: Agent 6 done, 500+ recommendations
- Week 6: Agents 8-11 done, validation + review
- Week 7: Agents 12-14 done, end-to-end working
- Week 8: All 12 MCP servers, full system ready

**Quality Metrics:**
- Entity extraction accuracy: target 80%+
- Recommendation quality: target 70%+ useful
- Link score average: target 75+
- Risk flag accuracy: target 95%+
- System uptime: target 99%+

---

## NEXT STEPS (BEFORE YOU START)

1. **Get Ken Data:**
   - 500 sample URLs from Ken (CSV format)
   - Content type definitions (report, article, etc.)
   - Industry/country taxonomy
   - Any existing linking rules

2. **Set Up Infrastructure:**
   - GitHub account (if needed)
   - Supabase account + free tier
   - Groq/Gemini API keys
   - PostgreSQL locally (or use SQLite)

3. **Team Alignment:**
   - Brief Shrey on full plan
   - Decide: Weekly sync time (10am?)
   - GitHub branch strategy
   - Daily standup format

4. **Communication:**
   - Slack channel for blockers
   - GitHub issues for tasks
   - Weekly progress review with you

---

## YOU'RE READY TO EXECUTE

This is a complete, detailed execution plan for building the full Ken Intelligence Linking Engine with all agents and servers locally, then handing off to your tech team.

**Week 1:** Start Phase 1 (Foundation)  
**Week 8:** Deliver complete system to tech team  
**Tech Team:** Scales and deploys to production  

Let me know if you need clarification on any part.

Ready to start?

---

**Prepared by:** Claude  
**For:** Vansh + Shrey  
**Timeline:** 6-8 weeks  
**Scope:** Complete system with all 14 agents + 12 MCP servers
