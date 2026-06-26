# Ken Intelligence Linking Engine - PRD Summary
**Document:** Intelligent MCP, LLM and Agentic Internal Linking System for Ken Research  
**Version:** Strategy PRD (June 2026)

---

## 1. PRODUCT OVERVIEW

**What:** An MCP-powered, LLM-assisted, agentic internal linking platform that transforms Ken's website from a content repository into a connected market intelligence graph.

**Why:** Manual internal linking at Ken's scale is impossible. The system must understand market relationships, industry hierarchies, global vs India segmentation, report relationships, and commercial intent—not just keyword matching.

**Who Uses It:** SEO Team, Content Team, Research Team, Tech Team, Business Research Team, Consulting Team, Leadership

---

## 2. CORE PROBLEMS SOLVED

- Pages not connected by market relationships
- High-value reports don't receive enough internal authority
- Articles don't guide users to relevant reports
- Country/global pages unclear relationships
- Old content doesn't link to new reports
- Research evidence disconnected after edits
- Duplicate insights not detected
- No single intelligence linking dashboard

---

## 3. BUSINESS & SEO GOALS

| Goal Type | Key Targets |
|-----------|-----------|
| **SEO** | Reduce orphan pages by 80%, improve crawl depth, improve internal authority flow, reduce crawl waste |
| **Business** | Increase report enquiries, increase cross-sell (articles→reports, reports→consulting), improve high-priority report discovery |
| **Content Intelligence** | Map evidence to paragraphs, connect reports/articles/case studies, detect unsupported claims, preserve research during refresh |
| **AI Search** | Make content entity-rich, support future AI overviews/citations, improve AI-readiness |

---

## 4. SYSTEM ARCHITECTURE

```
Content Sources (Website, CMS, Report Store)
    ↓
Crawl & Content Inventory
    ↓
Entity Extraction Layer
    ↓
Knowledge Graph / Relationship Index
    ↓
Vector Embeddings & Semantic Search
    ↓
MCP Tool Layer (12 specialized servers)
    ↓
LLM Reasoning Layer
    ↓
Agentic Workflow Layer (14 agents)
    ↓
SEO Validation Layer
    ↓
Recommendation Engine
    ↓
Editorial Review Dashboard
    ↓
CMS Deployment Layer
    ↓
Performance Measurement & Feedback Loop
```

---

## 5. THE 14 AGENTIC WORKERS

| Agent | Purpose | Key Actions |
|-------|---------|-------------|
| **1. Content Inventory Agent** | Build & maintain content node database | Fetch metadata, classify content type, check canonical, store as nodes |
| **2. Entity Extraction Agent** | Extract entities from pages/paragraphs | Extract industry, market, segment, country, region, company, claim type |
| **3. Relationship Mapping Agent** | Create relationship edges between content | Map parent-child, industry-market, global-local, case study support, evidence support |
| **4. SEO Opportunity Agent** | Find SEO-driven linking opportunities | Find orphan pages, underlinked pages, position 4-20 pages, poor anchor diversity, broken links |
| **5. Business Priority Agent** | Rank opportunities by commercial value | Score by report revenue potential, lead conversion, strategic priority, consulting relevance |
| **6. Link Recommendation Agent** | Generate internal link recommendations | Output source, target, anchor, placement, relationship type, scores, risk flag |
| **7. Anchor Text Agent** | Create safe & diverse anchor text | Generate 4-5 natural anchor variations per target, avoid generic/overused anchors |
| **8. Paragraph Evidence Agent** | Map paragraph claims to evidence | Classify paragraphs, detect unsupported claims, find supporting reports/case studies, create knowledge hash |
| **9. Section Purpose Agent** | Evaluate section-level usefulness | Detect TOC sections, identify purpose, recommend section-specific links, flag purposeless sections |
| **10. SEO Validation Agent** | Validate recommendations before approval | Check canonical, indexability, crawlability, anchor quality, placement, link count, faceted URL risk |
| **11. Editorial Review Agent** | Prepare human-friendly review notes | Explain why link recommended, where to place, what anchor, what relationships, SEO/business value, risk |
| **12. Deployment Agent** | Apply approved changes through CMS | Create CMS drafts, insert approved links, update related blocks, log changes |
| **13. Measurement Agent** | Measure post-deployment impact | Track internal link clicks, GA4 engagement, report enquiries, search metrics, conversion paths |
| **14. Link Decay Agent** | Monthly maintenance & hygiene | Find broken links, redirect chains, archived links, non-canonical links, repeated anchors, irrelevant links |

---

## 6. MCP SERVER LAYER (12 Specialized Servers)

| MCP Server | Key Tools Exposed | Purpose |
|-----------|------------------|---------|
| **Content Inventory** | get_page_by_url, search_pages, list_pages_by_industry, get_canonical_url, get_orphan_pages | Access structured page metadata & status |
| **CMS** | fetch_cms_content, create_link_insertion_draft, update_related_reports_block, submit_for_editorial_review | Control content edits & link insertions |
| **Search Console** | get_page_queries, get_page_ctr, get_pages_ranking_positions_4_to_20, get_indexing_status | Use search data to prioritize links |
| **GA4** | get_page_sessions, get_conversion_events, get_report_enquiries, get_assisted_conversions | Use behavior & conversion data |
| **Crawler** | crawl_url, get_broken_links, get_redirect_chains, get_faceted_url_patterns | Audit crawlability & link health |
| **Knowledge Graph** | get_related_entities, get_relationships_for_page, create_relationship_edge, get_relationship_explanation | Query & update relationship index |
| **Embedding Search** | semantic_search_pages, find_similar_reports, find_duplicate_paragraphs, get_embedding_similarity_score | Find semantically similar pages & duplicates |
| **Evidence Library** | search_evidence, search_case_studies, map_paragraph_to_evidence, flag_unsupported_claim | Connect paragraphs to research proof |
| **SEO Rules** | validate_anchor_text, validate_canonical_target, validate_faceted_url_risk, validate_link_count | Validate recommendations before deployment |
| **Jira** | create_jira_epic, create_jira_story, update_task_status, assign_owner | Convert recommendations into execution tickets |
| **Deployment** | *implied in CMS server* | Apply approved changes safely |
| **Report Store** | *implied in Content Inventory* | Access report data |

---

## 7. DATA MODEL (7 Core Tables)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| **content_nodes** | All pages as nodes | url, canonical_url, content_type, industry, country, market, segment, crawl_depth, authority_score, ai_readiness_score |
| **content_entities** | Extracted entities | entity_name, entity_type, normalized_name, parent_entity_id, confidence_score |
| **relationship_edges** | Page relationships | source_node_id, target_node_id, relationship_type, confidence_score, seo_value_score, business_value_score |
| **link_recommendations** | All recommendations | source_url, target_url, anchor_text, placement_type, link_score, seo_score, business_score, risk_flag, approval_status |
| **anchor_banks** | Anchor text for targets | target_url, primary_anchor, secondary_anchors, country_specific_anchors, overuse_flag |
| **paragraph_evidence_map** | Paragraph-to-proof mapping | paragraph_id, claim_type, market_entity, evidence_id, case_study_id, unsupported_claim_flag |
| **section_purpose_map** | Section context & intent | section_id, section_type, section_purpose, recommended_links, missing_link_flag |

---

## 8. LINK SCORING FORMULA

**Final Score = 16 factors:**
- 16% Semantic Similarity
- 12% Entity Overlap
- 10% Market/Segment Relationship
- 8% Geography Match
- 8% Search Intent Match
- 8% Business Value
- 8% Page Authority Transfer
- 6% Freshness
- 5% Crawl Priority
- 5% Anchor Quality
- 5% Evidence Support
- 4% Conversion Path
- 3% AI Readiness
- 2% Sentiment/External

**Score Buckets:**
- **90-100:** Priority link (strongly recommend)
- **80-89:** Strong recommendation (needs editor review)
- **65-79:** Secondary (use in related blocks)
- **50-64:** Hold in queue
- **Below 50:** Do not recommend

---

## 9. RELATIONSHIP TYPES SUPPORTED (20+)

**Market:** Parent/child, same market, adjacent, upstream, downstream, emerging, mature, high-growth
**Geography:** Global-to-regional, regional-country, India-to-state, Asia Pacific-to-India
**Content:** Article supports report, case study supports report, survey supports claim, chart/table/image support
**Business:** Report→consulting, report→survey, article→report, case study→consulting
**SEO:** Authority redistribution, orphan recovery, freshness, crawl depth, anchor diversity, canonicalization

---

## 10. LINK TYPES SUPPORTED (20+)

Navigational, Breadcrumb, Contextual, Related reports, Related articles, Hub-and-spoke, Parent-child, Global-to-local, Section-level, Table of contents, Evidence-based, Case study, Commercial CTA, Footer, Sidebar, Image/infographic, FAQ, Pagination, Cross-service, Entity-based, Freshness-based, Conversion-path, Authority redistribution, Broken-link replacement

---

## 11. KEY USER WORKFLOWS

| Workflow | Trigger | Agent Actions | Output |
|----------|---------|---------------|--------|
| **New Report Published** | Report goes live | Add to inventory, extract entities, create node, find related assets, generate link opportunities | 10-30 link opportunities submitted for approval |
| **New Article Published** | Article goes live | Extract topic/intent, find related reports/markets, generate 3-8 internal links, recommend CTAs | Article becomes connected to report-store & conversion journeys |
| **Existing Page Refresh** | Content refresh task | Audit links, remove broken ones, replace old report links, improve anchor diversity, add evidence links | Fresh, connected, commercially-useful page |
| **Monthly Audit Cycle** | Monthly SEO cycle | Find orphans, broken links, redirect chains, non-canonical links, underlinked priority pages | Monthly internal linking audit dashboard |
| **Report Editing** | Research team edits | Break into paragraphs, extract claims, detect repeats/unsupported claims, map to evidence, find case studies | Evidence-backed, intelligence-linked report |

---

## 12. EDITORIAL CONTROLS (Human-in-the-Loop)

**V1 Rule:** No direct publishing without approval.

**Always Require Human Approval:**
- New contextual body links
- Commercial CTA changes
- Links to consulting pages
- Links involving market numbers/evidence
- Canonical/indexability changes
- Faceted URL indexation changes
- Bulk deployment (50+ pages)

**Can Be Auto-Approved (Later Versions):**
- Broken-link replacement with exact canonical equivalent
- Breadcrumb correction
- Related block update from approved relationship
- Internal link to same parent with high confidence

---

## 13. SEO VALIDATION RULES

**Crawlability:**
- Use standard crawlable HTML href (not JS-only)
- Don't link to blocked/search-result URLs
- Important links not hidden behind unrevealed tabs

**Canonical:**
- Always link to canonical URL
- Avoid: tracking URLs, duplicates, old slugs, redirects, filtered URLs, HTTP, non-preferred trailing slash, session URLs

**Anchor Text:**
- Descriptive anchors only (avoid "click here," "read more," "best report")
- Use format: Country+Market, Region+Market, Market+Segment, Market+Intent
- Maintain per-URL anchor bank (no single exact-match anchor dominates)

**Link Quantity:**
- Short article: 5-8 links
- Long article: 8-15 links
- Report page: 10-25 links
- Industry hub: 30+ links (if structured)
- Country hub: 20+ links (if structured)

**Placement Priority:**
1. Relevant body paragraph
2. Section-specific block
3. Related report module
4. Case study/evidence block
5. TOC section
6. Sidebar
7. Footer

---

## 14. DASHBOARDS (4 Views)

| Dashboard | Key Metrics |
|-----------|-----------|
| **SEO Dashboard** | Total pages, total internal links, orphan pages, broken links, pages deeper than 3 clicks, high-value underlinked pages, anchor diversity score |
| **Business Dashboard** | Internal link clicks, report enquiries from links, sample requests, consulting enquiries, top converting source/target pages, assisted conversions |
| **Intelligence Dashboard** | Entity coverage, relationship coverage, global/local mapping, paragraph evidence mapping, case study linkage, unsupported claim count, duplicate claims, AI-readiness by industry |
| **Editorial Dashboard** | Recommendation queue, approve/reject links, edit anchor/placement, view reason/risk/previews, bulk approve low-risk, assign to owners, export to Jira |

---

## 15. ACCESS CONTROL & ROLES

| Role | Permissions |
|------|-----------|
| **Admin** | All permissions |
| **SEO Manager** | Approve/reject SEO links, run audits, export recommendations |
| **Content Editor** | Review placement, edit anchor, approve content links |
| **Research Reviewer** | Approve evidence/case study mapping, reject unsupported claims |
| **Tech Developer** | Manage MCP tools, deploy approved changes, view logs |
| **Leadership Viewer** | View dashboards only (read-only) |

---

## 16. SUCCESS METRICS

| Category | Target |
|----------|--------|
| **SEO** | 80% orphan reduction, priority pages have minimum links, crawl depth improves, broken links near zero, anchor diversity improves, position 4-20 pages improve, indexing improves |
| **Business** | Report enquiry clicks increase, sample request clicks increase, consulting CTA clicks increase, assisted conversions increase, high-value report discovery improves |
| **Content Intelligence** | Paragraph evidence mapping coverage ↑, unsupported claims ↓, duplicate claims ↓, case study linkage ↑, global/local coverage ↑, pages with TOC ↑ |
| **AI Readiness** | Entity-rich link pages ↑, methodology/evidence link pages ↑, FAQ-linked pages ↑, case-study-supported pages ↑, AI-readiness score improves by industry |

---

## 17. MVP SCOPE

**Duration:** Build as internal prototype first (no public launch)

**Content Scope:**
- **3 Industries:** Healthcare, Automotive, Technology/Telecom
- **3 Geographies:** India, Saudi Arabia, UAE
- **5 Content Types:** Report pages, Articles, Industry pages, Country pages, Case studies

**MVP Capabilities:**
✅ Content inventory  
✅ Entity extraction  
✅ Relationship index  
✅ Semantic search  
✅ Link recommendations  
✅ Anchor suggestions  
✅ SEO validation  
✅ Editorial dashboard  
✅ Manual deployment export  
✅ Basic performance tracking  

**MVP Exclusions:**
❌ Full auto-publishing  
❌ Full paragraph evidence mapping for all reports  
❌ Full marketplace faceted URL automation  
❌ Full CRM attribution  
❌ Full enterprise permission model  

---

## 18. 6-PHASE ROADMAP

| Phase | Duration | Focus | Output |
|-------|----------|-------|--------|
| **Phase 1: Foundation** | – | Content inventory, canonical normalization, content classification, taxonomy, content nodes, base dashboard | Database of all nodes |
| **Phase 2: Intelligence Layer** | – | Entity extraction, relationship index, semantic embeddings, global/local segmentation, business priority scoring | Knowledge graph |
| **Phase 3: Recommendation Engine** | – | Link opportunities, anchor generation, placement suggestions, SEO validation, editorial review queue | Recommendation engine live |
| **Phase 4: Deployment Workflow** | – | CMS drafts, related block updates, Jira export, approval logs, rollback workflow | Deployment pipeline |
| **Phase 5: Evidence & Report Intelligence** | – | Paragraph mapping, knowledge hash, case study mapping, chart/table/image support, unsupported claim detection | Research-backed intelligence |
| **Phase 6: Learning Loop** | – | GA4 feedback, GSC feedback, conversion scoring, recommendation learning, monthly link decay agent | Feedback loop active |

---

## 19. MVP ACCEPTANCE CRITERIA

✓ At least 5,000 priority URLs inventoried  
✓ 80%+ of MVP pages have correct entity extraction  
✓ 70%+ of recommendations judged useful by SEO/content team  
✓ All recommendations include reason, score, and placement  
✓ No recommendations point to non-canonical URLs  
✓ No recommendations point to blocked/noindex URLs  
✓ Orphan priority pages identified  
✓ At least 500 link recommendations generated  
✓ At least 100 approved links deployed  
✓ Dashboard shows SEO, business, and intelligence metrics  

---

## 20. KEN-SPECIFIC LINKING RULES

**Rule 1:** Every new report page must receive incoming links from industry hub, country hub, region hub, related articles, related reports, case studies, service pages.

**Rule 2:** Every article must include 3-5 contextual links + 1 report link + 1 market link + 1 related article + 1 CTA.

**Rule 3:** Every market page must link to parent industry, child segments, country pages, global page, reports, services, case studies.

**Rule 4:** Every case study must link to related market, related report, related service, industry page, country page.

**Rule 5:** Every paragraph with market claim mapped to evidence, report, case study, market segment, country/region, knowledge hash.

---

## 21. RISK CONTROLS

**Main Risks:**
- LLM hallucination
- Wrong link recommendation
- Spammy anchor text
- Over-optimization
- Incorrect canonical link
- Crawl waste from faceted pages
- Unapproved publishing
- Loss of editorial quality

**Mitigations:**
- MCP tool permission scoping
- Read-only mode by default
- Structured output schemas
- SEO validation before approval
- Audit logs for every action
- Rollback available for all deployments
- Role-based access
- Human-in-the-loop for V1

---

## 22. FINAL PRODUCT OUTCOME

The system will answer:

✓ Which reports should this article link to?  
✓ Which articles should support this report?  
✓ Which case study validates this paragraph?  
✓ Which survey supports this claim?  
✓ Which global page should connect with this India page?  
✓ Which country page is underlinked?  
✓ Which report is orphaned?  
✓ Which old article should link to a new report?  
✓ Which high-authority page should support a business-priority page?  
✓ Which anchor text should be used?  
✓ Where should the link be placed?  
✓ Which links are unsafe?  
✓ Which pages are disconnected from the market graph?  

---

## 23. TEAM OWNERSHIP

| Role | Responsibility |
|------|-----------------|
| **Product Owner** | PRD, priority, acceptance criteria, business outcomes |
| **SEO Owner** | SEO logic, anchor rules, crawlability, recommendation approval |
| **Content Owner** | Content placement, article/report readability, editorial approval |
| **Research Owner** | Evidence mapping, paragraph validation, knowledge hash quality |
| **Tech Owner** | MCP servers, database, dashboard, integrations, deployment pipeline |
| **Analytics Owner** | GA4, GSC, click tracking, performance dashboards |

---

## 24. STRATEGIC VISION

**Ken Research should build:** Not a basic internal linking tool, but an **MCP-powered market intelligence linking system**.

**System Must Be:**
- Entity-led & relationship-led
- Evidence-backed & SEO-safe
- LLM-assisted & agent-orchestrated
- Human-approved & business-priority-driven
- AI-search ready & conversion-focused
- Global/local segmentation aware

**Outcome:** Transform Ken's website from a large content repository into a **connected intelligence graph** → Stronger SEO, better AI discoverability, better report quality, better user navigation, stronger commercial conversion.

---

**Last Updated:** June 2026 | **Status:** Strategy PRD
