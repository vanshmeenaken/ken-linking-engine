# SEO Opportunity Agent

## Purpose

Agent 4 turns the Phase 1 and Phase 2 intelligence into a queue of actionable
SEO opportunities: pages that are underperforming for a reason internal links
can fix. It is a deterministic detector, not an LLM. It also writes a per-page
`search_opportunity_score` to `content_nodes`, a column that existed since
Phase 1 but was never populated. That score is the pre-GSC placeholder that real
position 4-20 data refines once Search Console is connected.

## Opportunity types

All computable from current data:

- `orphan_page` zero incoming internal links
- `underlinked_page` one or two incoming links
- `high_priority_underlinked` underlinked and high authority or decision intent
- `missing_market_entity` an active page with no market entity
- `missing_geo_entity` an active page with no country or region entity
- `missing_relationships` an active page with no relationship edges
- `entity_low_confidence` a page with a sub-0.5 confidence entity mapping
- `stale_metadata` missing title, H1, or meta description

## Scoring: worst problem wins

`search_opportunity_score` is the score of the single biggest problem on a page,
not the sum of its problems. An orphan page scores 1.0 whether or not it also has
other issues, because the orphan status is what you fix first. This keeps the
score honest as a fix-first ranking rather than letting many small issues
out-rank one severe one.

A blank score means the page was checked and no fixable problem was found, not
that it was skipped.

## Deferred, not dropped

Documented so nothing looks silently missing:

- `global_local_gap` on this dataset only two markets have both a global and a
  local page, so a "no counterpart" flag would fire for almost every page and is
  content-creation work this system cannot action. Re-add with a sharper
  definition when the catalog has real global/local market pairs.
- `position_4_to_20` and `high_impression_low_ctr` need GSC ranking and
  impression data. With Search Console now connected, these are the natural next
  additions; the striking-distance list is already served at
  `/api/opportunities/striking-distance`.

## Consistency guarantee

Connected pages plus `missing_relationships` opportunities equal total active
pages: every active page either has a real page-to-page edge or is flagged as
needing one. This cross-agent check is asserted in the test suite.

## Safety

- `--dry-run` detects and reports without writing.
- Opportunities are keyed unique on (node_id, opportunity_type), so re-running
  updates rather than duplicates.
- All writes happen in one transaction.

## Commands

```powershell
python agents/agent_4_seo_opportunity.py --dry-run
python agents/agent_4_seo_opportunity.py
```

## Verification

```powershell
python -m pytest tests/test_seo_opportunity_agent.py -q
```

Through the API:

- `GET /api/opportunities` filterable list, most valuable first
- `GET /api/opportunities/orphans` and `/underlinked`
- `GET /api/opportunities/high-priority` the fix-first list: valuable and broken
