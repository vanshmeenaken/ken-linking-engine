# Ken Intelligence Linking Engine — Database Schema

**Database:** `ken_links.db` (SQLite)
**Setup:** `python scripts/01_setup_db.py` (creates + verifies, safe to re-run)
**Load:** `python scripts/02_load_urls.py scripts/sample_urls.csv`
**Foreign keys:** enabled (`PRAGMA foreign_keys = ON`)

## Tables

### 1. `content_nodes` — one row per page (primary table, 30 cols)
| Column | Type | Notes |
|---|---|---|
| node_id | TEXT PK | UUID |
| url | TEXT | required, unique |
| canonical_url | TEXT | defaults to url on load |
| title, meta_title, meta_description, h1 | TEXT | page text |
| content_type | TEXT | report, article, market_page, country_page, industry_page… |
| industry, sub_industry, market, segment | TEXT | classification |
| country, region, global_or_local | TEXT | geography |
| intent_stage | TEXT | awareness / consideration / decision |
| business_priority | TEXT | high / medium / low |
| published_date, updated_date | TEXT | |
| indexability_status | TEXT | indexable / noindex / blocked |
| crawl_depth | INTEGER | |
| internal_links_in, internal_links_out | INTEGER | link counts |
| orphan_status | VARCHAR | orphan, under_linked, normal, or well_linked |
| page_authority_score, search_opportunity_score, ai_readiness_score | REAL | scores |
| status | TEXT | active / inactive |
| created_at, updated_at | TEXT | timestamps |

### 2. `content_entities` — markets, industries, countries, companies… (12 cols)
`entity_id` (PK, UUID), entity_name, entity_type, normalized_name, aliases,
`parent_entity_id` (→ content_entities.entity_id), industry, country, region,
confidence_score, created_at, updated_at.

### 3. `relationship_edges` — typed connections between pages/entities (19 cols)
`edge_id` (PK, UUID), source_node_id (→ content_nodes), target_node_id (→ content_nodes),
source_entity_id / target_entity_id (→ content_entities), relationship_type,
relationship_direction, confidence_score, semantic_similarity_score, entity_overlap_score,
geo_match_score, market_match_score, business_value_score, seo_value_score,
created_by, reviewed_by, status (pending/approved/rejected), created_at, updated_at.

### 4. `crawl_logs` — crawl/ingest/load operation history (10 cols)
`crawl_id` (PK, autoincrement), url, node_id (→ content_nodes), operation, status,
http_status, crawl_depth, error, notes, crawled_at.

## Indexes
- `content_nodes`: url, content_type, industry, country, status, orphan_status
- `content_entities`: entity_type, normalized_name, parent_entity_id
- `relationship_edges`: source_node_id, target_node_id, relationship_type, status
- `crawl_logs`: url, status

## Foreign keys
- relationship_edges.source_node_id / target_node_id → content_nodes.node_id
- relationship_edges.source_entity_id / target_entity_id → content_entities.entity_id
- content_entities.parent_entity_id → content_entities.entity_id (self)
- crawl_logs.node_id → content_nodes.node_id

## Data loaded (Day 2)
- 500 URLs loaded into `content_nodes` from `scripts/sample_urls.csv`
- Columns populated: url, canonical_url, title, content_type, industry, country, global_or_local, status
- Source: existing Ken Research catalog (report pages); other content types added later.

## Verify
```
python scripts/01_setup_db.py
sqlite3 ken_links.db ".tables"
sqlite3 ken_links.db "SELECT COUNT(*) FROM content_nodes"          -- 500
sqlite3 ken_links.db "SELECT url,COUNT(*) FROM content_nodes GROUP BY url HAVING COUNT(*)>1"  -- empty
sqlite3 ken_links.db "SELECT * FROM content_nodes LIMIT 5"
```
