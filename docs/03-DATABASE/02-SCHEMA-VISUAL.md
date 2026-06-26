# DATABASE SCHEMA - VISUAL REFERENCE

## OVERVIEW

```
                    ┌─────────────────────────┐
                    │   CONTENT_NODES (30)    │
                    │  - node_id (PK, UUID)   │
                    │  - url (UNIQUE)         │
                    │  - 28 other fields      │
                    └──────────┬──────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
      [CONTAINS RELATIONSHIPS]      [HAS CRAWL OPERATIONS]
                │                             │
                ▼                             ▼
    ┌───────────────────────┐    ┌──────────────────────┐
    │ RELATIONSHIP_EDGES(19)│    │  CRAWL_LOGS (10)     │
    │ - edge_id (PK, UUID)  │    │ - crawl_id (PK, int) │
    │ - source_node_id (FK) │    │ - url                │
    │ - target_node_id (FK) │    │ - node_id (FK)       │
    │ - 16 other fields     │    │ - 7 other fields     │
    └───────────┬───────────┘    └──────────────────────┘
                │
    ┌───────────┴──────────┐
    │ REFERENCES ENTITIES  │
    │ (both source & target)
    ▼
┌──────────────────────────┐
│ CONTENT_ENTITIES (12)    │
│ - entity_id (PK, UUID)   │
│ - entity_name (required) │
│ - 10 other fields        │
│ - parent_entity_id (FK)  │ ← Self-reference for hierarchy
└──────────────────────────┘
```

---

## TABLE SPECIFICATIONS

### TABLE 1: CONTENT_NODES (30 columns)
**Purpose:** One row per page/content item

| Field | Type | Key | Notes |
|-------|------|-----|-------|
| node_id | VARCHAR | PK | UUID, unique identifier |
| url | VARCHAR | UNIQUE | Required, normalized URL |
| canonical_url | VARCHAR | - | Defaults to url on load |
| **Page Text:** | | | |
| title | VARCHAR | - | Page title |
| meta_title | VARCHAR | - | SEO meta title |
| meta_description | VARCHAR | - | SEO meta description |
| h1 | VARCHAR | - | Main heading |
| **Classification:** | | | |
| content_type | VARCHAR | IX | report, article, market_page, etc. |
| industry | VARCHAR | IX | Primary industry |
| sub_industry | VARCHAR | - | Sub-classification |
| market | VARCHAR | - | Market name |
| segment | VARCHAR | - | Market segment |
| **Geography:** | | | |
| country | VARCHAR | IX | Country code/name |
| region | VARCHAR | - | Region within country |
| global_or_local | VARCHAR | - | "global" or "local" |
| **Business:** | | | |
| intent_stage | VARCHAR | - | awareness/consideration/decision |
| business_priority | VARCHAR | - | high/medium/low |
| **Dates:** | | | |
| published_date | VARCHAR | - | ISO format |
| updated_date | VARCHAR | - | ISO format |
| **Technical:** | | | |
| indexability_status | VARCHAR | - | indexable/noindex/blocked |
| crawl_depth | INTEGER | - | Depth from root |
| internal_links_in | INTEGER | - | # pages linking here |
| internal_links_out | INTEGER | - | # pages linked from here |
| **Scoring:** | | | |
| orphan_status | INTEGER | IX | 0=linked, 1=orphan |
| page_authority_score | FLOAT | - | 0-100 |
| search_opportunity_score | FLOAT | - | 0-100 |
| ai_readiness_score | FLOAT | - | 0-100 |
| **Status:** | | | |
| status | VARCHAR | IX | active/inactive |
| created_at | VARCHAR | - | ISO timestamp |
| updated_at | VARCHAR | - | ISO timestamp |

**Indexes:** 6 (url, content_type, industry, country, status, orphan_status)

---

### TABLE 2: CONTENT_ENTITIES (12 columns)
**Purpose:** Markets, industries, countries, companies, segments

| Field | Type | Key | Notes |
|-------|------|-----|-------|
| entity_id | VARCHAR | PK | UUID, unique identifier |
| entity_name | VARCHAR | REQUIRED | Display name |
| entity_type | VARCHAR | IX | market, industry, country, company, etc. |
| normalized_name | VARCHAR | IX | Standardized name for matching |
| aliases | VARCHAR | - | Comma-separated alternate names |
| parent_entity_id | VARCHAR | FK,IX | → content_entities.entity_id (self) |
| industry | VARCHAR | - | Parent industry if applicable |
| country | VARCHAR | - | Associated country |
| region | VARCHAR | - | Associated region |
| confidence_score | FLOAT | - | 0-100 extraction confidence |
| created_at | VARCHAR | - | ISO timestamp |
| updated_at | VARCHAR | - | ISO timestamp |

**Indexes:** 3 (entity_type, normalized_name, parent_entity_id)
**Self-Reference:** parent_entity_id creates hierarchies (e.g., market → industry → region)

---

### TABLE 3: RELATIONSHIP_EDGES (19 columns)
**Purpose:** Typed connections between pages and/or entities

| Field | Type | Key | Notes |
|-------|------|-----|-------|
| edge_id | VARCHAR | PK | UUID, unique identifier |
| source_node_id | VARCHAR | FK,IX | → content_nodes.node_id |
| target_node_id | VARCHAR | FK,IX | → content_nodes.node_id |
| source_entity_id | VARCHAR | FK | → content_entities.entity_id |
| target_entity_id | VARCHAR | FK | → content_entities.entity_id |
| relationship_type | VARCHAR | IX | market, parent-child, evidence, etc. |
| relationship_direction | VARCHAR | - | uni/bidirectional |
| **Confidence Scores:** | | | |
| confidence_score | FLOAT | - | Overall link confidence (0-100) |
| semantic_similarity_score | FLOAT | - | Content similarity score |
| entity_overlap_score | FLOAT | - | Shared entities percentage |
| geo_match_score | FLOAT | - | Geographic relevance |
| market_match_score | FLOAT | - | Market relevance |
| business_value_score | FLOAT | - | Commercial importance |
| seo_value_score | FLOAT | - | SEO benefit |
| **Audit Trail:** | | | |
| created_by | VARCHAR | - | Agent or user who created |
| reviewed_by | VARCHAR | - | Reviewer (editorial approval) |
| status | VARCHAR | IX | pending/approved/rejected |
| created_at | VARCHAR | - | ISO timestamp |
| updated_at | VARCHAR | - | ISO timestamp |

**Indexes:** 4 (source_node_id, target_node_id, relationship_type, status)

---

### TABLE 4: CRAWL_LOGS (10 columns)
**Purpose:** Operation history for crawls, loads, and ingests

| Field | Type | Key | Notes |
|-------|------|-----|-------|
| crawl_id | INTEGER | PK | Auto-incrementing sequence |
| url | VARCHAR | IX | URL processed |
| node_id | VARCHAR | FK | → content_nodes.node_id |
| operation | VARCHAR | - | load/crawl/validate/update |
| status | VARCHAR | IX | success/failed/pending |
| http_status | INTEGER | - | HTTP response code (200, 404, etc.) |
| crawl_depth | INTEGER | - | Depth at crawl time |
| error | TEXT | - | Error message if failed |
| notes | TEXT | - | Additional context |
| crawled_at | VARCHAR | - | ISO timestamp |

**Indexes:** 2 (url, status)

---

## FOREIGN KEY RELATIONSHIPS

```
content_entities
  ├─ parent_entity_id → content_entities.entity_id (self-reference)
  
relationship_edges
  ├─ source_node_id → content_nodes.node_id
  ├─ target_node_id → content_nodes.node_id
  ├─ source_entity_id → content_entities.entity_id
  └─ target_entity_id → content_entities.entity_id
  
crawl_logs
  └─ node_id → content_nodes.node_id
```

---

## INDEXES FOR PERFORMANCE

**Content Nodes (6 indexes):**
- url (unique lookups)
- content_type (filtering by type)
- industry (filtering by industry)
- country (filtering by country)
- status (active/inactive filtering)
- orphan_status (orphan detection)

**Content Entities (3 indexes):**
- entity_type (entity classification lookups)
- normalized_name (entity matching)
- parent_entity_id (hierarchy traversal)

**Relationship Edges (4 indexes):**
- source_node_id (find outgoing links from page)
- target_node_id (find incoming links to page)
- relationship_type (filter by link type)
- status (find approved/pending links)

**Crawl Logs (2 indexes):**
- url (audit trail lookups)
- status (find failed operations)

**Total: 15 performance indexes**

---

## DATA CURRENTLY LOADED

| Table | Rows | Status |
|-------|------|--------|
| content_nodes | 500 | ✅ Ken Research URLs loaded |
| content_entities | 0 | Pending: Agent 2 (Day 4+) |
| relationship_edges | 0 | Pending: Agent 3 (Day 4+) |
| crawl_logs | 500 | ✅ Load operations logged |

---

## KEY DESIGN DECISIONS

### 1. UUID vs Integer IDs
- **node_id, entity_id, edge_id** use VARCHAR(UUID) for distributed system readiness
- **crawl_id** uses INTEGER auto-increment for operation sequence tracking

### 2. String Timestamps
- All timestamps stored as VARCHAR (ISO 8601 format)
- Reason: SQLite TEXT is more flexible; can add timezone info in future

### 3. Score Fields (0-100)
- Multiple score columns in relationship_edges for multi-factor confidence
- Individual factors (semantic, entity, geo, market, business, SEO) can be analyzed separately

### 4. Status Enums
- content_nodes.status: "active" / "inactive"
- relationship_edges.status: "pending" / "approved" / "rejected" (editorial review)
- crawl_logs.status: "success" / "failed" / "pending"

### 5. Hierarchical Entities
- content_entities.parent_entity_id creates tree structures
- Example: Segment → Market → Industry → Region

### 6. Flexible Classification
- content_nodes has both industry AND market AND segment (multiple classification axes)
- Allows queries like: "All articles in Healthcare industry, Diagnostics market, India"

---

## SAMPLE QUERIES

```sql
-- Find all orphan pages
SELECT url, title FROM content_nodes WHERE orphan_status = 1 AND status = 'active';

-- Find high-authority pages
SELECT url, page_authority_score FROM content_nodes WHERE page_authority_score > 75 ORDER BY page_authority_score DESC;

-- Find all relationships for a page
SELECT * FROM relationship_edges WHERE source_node_id = ? OR target_node_id = ?;

-- Find pending editorial approvals
SELECT * FROM relationship_edges WHERE status = 'pending' ORDER BY created_at;

-- Find pages by industry and country
SELECT url, title FROM content_nodes WHERE industry = 'automotive' AND country = 'india';

-- Get entity hierarchy
SELECT entity_id, entity_name, parent_entity_id FROM content_entities WHERE parent_entity_id IS NOT NULL;

-- Recent operations
SELECT url, operation, status FROM crawl_logs ORDER BY crawled_at DESC LIMIT 10;
```

---

## NOTES

✅ Schema is **production-ready** for Day 3+ operations  
✅ All required fields for Phase 1 foundation present  
✅ Extensible for future phases (more agents, scoring)  
✅ Foreign keys enabled (PRAGMA foreign_keys = ON)  
✅ Indexes optimized for common query patterns
