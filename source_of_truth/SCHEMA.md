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

## Phase 3 Planning Tables

link_recommendations stores directional source-to-target instructions,
relationship/relevance scores, anchor, placement status, plan category/rank,
validation output, and editorial audit state. Reverse directions are separate
rows.

report_link_plans stores one PRD coverage summary per active report: existing
and projected outgoing links, incoming/total opportunities, remaining
gap/capacity, regional/adjacent/content/hub mix, status, and gap reason.

anchor_banks stores safe anchor variants per target. Run
python scripts/27_report_link_planning_migration.py after the Phase 3 migration
to add the planning table and placement/plan fields.

## Sentence Fields on link_recommendations

suggested_sentence is the EXISTING sentence on the source page that the
placement anchors to (unchanged prose, quoted for the editor).

woven_sentence is the ready-to-paste rewrite of that sentence with the anchor
woven in, and woven_sentence_source records whether it came from the LLM
('llm') or the deterministic template fallback ('template'). Populated by
python scripts/36_generate_woven_sentences.py; migration:
python scripts/35_woven_sentence_migration.py

proposed_sentence is an entirely NEW claim-free sentence, used only when no
existing sentence fits (placement_type='best_available_paragraph'), to be
inserted after the named line. Migration:
python scripts/33_proposed_sentence_migration.py

## Manual Workbench Tables (/users)

sitemap_urls caches Ken's public sitemap (~5,000 URLs across the product,
article, casestudy, survey, pov and blog child sitemaps) so the workbench can
suggest related pages outside the 500-page inventory. Refresh with
analysis.sitemap_index.refresh_sitemap_cache().

manual_link_plans stores HUMAN-authored link decisions from the workbench:
source/target URL, anchor, section heading, paragraph index and excerpt, the
person's own note, how the candidate was found, and who recorded it.
Deliberately separate from link_recommendations (machine suggestions) so
provenance is never ambiguous. chosen_sentence holds the exact wording the
user settled on (what the web team pastes) and suggestion_style records
whether it came from an offered framing or was written from scratch.
Migrations:
python scripts/37_manual_linking_migration.py
python scripts/38_chosen_sentence_migration.py

## Section and Evidence Tables (Agents 9 and 8)

section_purpose_map stores one row per crawled section of a page: real
heading, section_order, classified purpose, paragraph/internal-link counts,
linkable flag, plain link guidance, and two honesty flags (purposeless,
missing links). Rebuilt per page on each Agent 9 run. Migration:
python scripts/29_section_purpose_migration.py

paragraph_evidence_map stores one row per meaningful paragraph: section
heading/purpose, paragraph text and sha256 knowledge hash, classification
(market_claim or context), support_status (supported / section_supported /
unsupported, claims only), and the best evidence page found (target node,
url, type, similarity score) when one passes all three gates. Rebuilt per
page on each Agent 8 run. Migration:
python scripts/30_paragraph_evidence_migration.py

ken_vectors.db.page_vectors / .paragraph_vectors are DERIVED sqlite-vec
index files (not tracked in git); rebuild any time with
python scripts/31_vector_backend_setup.py

## Verify
```
python scripts/01_setup_db.py
sqlite3 ken_links.db ".tables"
sqlite3 ken_links.db "SELECT COUNT(*) FROM content_nodes"          -- 500
sqlite3 ken_links.db "SELECT url,COUNT(*) FROM content_nodes GROUP BY url HAVING COUNT(*)>1"  -- empty
sqlite3 ken_links.db "SELECT * FROM content_nodes LIMIT 5"
```
