# Phase 2 Handoff Document

**Phase:** 2, Intelligence Layer
**Status:** Complete
**Date:** 15 July 2026
**Owner:** Shrey

## What Phase 2 Was

Phase 1 answered "what pages exist and how linked are they." Phase 2 answers
"what is each page about, how are pages related, and where is the opportunity."
It turns the 500-page inventory into a queryable knowledge graph with entities,
relationships, scores, and now live Google data.

## What Was Built

- Agent 2 (Entity Extraction): normalized entities from page metadata.
- Agent 3 (Relationship Mapping): typed, scored page-to-page edges.
- Agent 4 (SEO Opportunity): the fixable-problem queue plus
  `search_opportunity_score`.
- Agent 5 (Business Priority): High/Medium/Low commercial band per page.
- Agent 10 (SEO Validation): a pre-recommendation link checker.
- Five new database tables (node_entities, entity_extraction_logs,
  semantic_embeddings, seo_opportunities, integration_placeholders) plus new
  scoring columns on content_nodes.
- 17 new API endpoints (entities, relationships, opportunities, intelligence
  summaries, integration status).
- Dashboard sections for business priority, page connections, the fix-first
  list, and Google connection status.
- Live Google Search Console and GA4 integration with a one-time OAuth login.

## What Works (verified numbers)

- 498 active pages, 447 entities, 2,017 page-to-entity mappings.
- 110 relationship edges, all genuine page-to-page, self-loop canary at 0.
  Types: adjacent_market 57, same_market 29, report_article_support 8,
  country_region 7, case_study_support 5, global_local 4.
- 898 open SEO opportunities.
- Business priority: 148 High, 325 Medium, 25 Low.
- Search Console live: 194 inventory pages matched, 11,065 site-wide pages in
  striking distance (positions 4-20).
- GA4 live: 368 inventory pages matched, 612 site-wide pages with conversions.
- 178 tests passing under the venv interpreter, plus 7 Agent 1 tests under the
  global interpreter. 0 failures.

## Cross-Agent Consistency

Connected pages plus missing-relationship opportunities equal active pages:
120 + 378 = 498. Every active page either has a real page-to-page edge or is
flagged as needing one. This is asserted in the test suite.

## Known Limitations

- Page-to-page connectivity is 120 of 498 active pages (24.1 percent), below the
  70 percent target. This is a consequence of the 500-page sample: most pages'
  real siblings (same market, other geographies) are not in the sample, so no
  edge can be created. It rises sharply with the full catalog.
- Google data covers the whole site (about 42,000 pages) while the inventory is
  500, so most GSC and GA4 rows are unmatched. They are stored with
  status='unmatched' rather than dropped, so the coverage gap stays visible.
- Buyer intent in business priority is a page-type proxy until the GA4
  conversion mapping is built.
- Entity extraction is metadata-only; body-content entity types (company,
  product, technology) are deferred.
- The GA4 conversion-to-business-value mapping needs the property's real
  key-event names (`python scripts/20_sync_ga4.py --events`).

## A Live Bug This Phase Surfaced

While reviewing the fix-first list, the system exposed a real SEO bug on Ken's
live site: several report pages serve "nan" instead of the market name in their
Google search title (for example "nan Market Size & Forecast Report 2025-2031").
The page content is fine; the title template is receiving an empty market name.
Reported to the content team. Likely affects more pages across the full catalog.

## Where Phase 3 Starts

The recommendation engine (Agent 6) has everything it needs to begin:

- relationship edges (which pages relate, and why)
- SEO opportunities (which pages need help)
- business priority (which pages deserve help first)
- Agent 10 as the mandatory validation gate
- live GSC data (real rankings, striking-distance targets) and GA4 data (real
  conversions) to prioritise by

The immediate next builds: activate the GSC-driven opportunity types in Agent 4
(position_4_to_20, high_impression_low_ctr), build the GA4 conversion mapping,
and start Agent 6 generating source-to-target link recommendations with anchor
text, each passed through Agent 10.

## Documentation Index

- Agent guides: `docs/09-AGENTS/03` through `07`
- Google integrations: `docs/06-INTEGRATIONS/`
- MCP design pack: `docs/07-MCP/01-MCP-DESIGN-PACK.md`
- Phase 2 schema design: `docs/03-DATABASE/04-PHASE2-SCHEMA-DESIGN.md`
- API reference: `docs/API.md`
