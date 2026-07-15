# Relationship Mapping Agent

## Purpose

Agent 3 creates typed, scored relationship edges between content nodes, using
the entities Agent 2 extracted. These edges are the internal-linking graph: they
say which two pages are genuinely related and why. Every edge is written with
`status = 'pending'` so nothing is auto-trusted; a human or a later phase
reviews before anything is acted on.

The agent is precision-first. The project quality bar is that a short correct
set of connections beats a long noisy one, so when a match is uncertain, no edge
is created.

## Edge types and confidence

Each edge type carries a fixed base confidence:

- `same_market` (0.90) two pages independently mapped to the same market entity
- `global_local` (0.80) same market, one page global-scope and one local-scope
- `report_article_support` (0.75) an article sharing a market with a report
- `case_study_support` (0.75) a case study sharing a market with a report
- `country_region` (0.65) a region hub linked to local pages in that region,
  same industry only
- `adjacent_market` (0.60) same industry, different market, high text similarity

`same_industry` is deliberately not built as raw page pairs. For broad
industries that would produce thousands of low-value pairs. Industry membership
is available directly from `node_entities` instead.

## Market to parent industry is NOT an edge

A market belonging to an industry (for example Freight Trucking belongs to
Automotive, Transportation and Logistics) is entity hierarchy, not a link
between two pages. It is written to `content_entities.parent_entity_id`, its
designed home, never to `relationship_edges`.

An earlier version stored this as `industry_market` self-loop edges, where the
source and target node were the same page. Those 384 self-loops were 78 percent
of the edge table and inflated every page-to-page connectivity metric (the site
looked 82 percent connected when the true page-to-page figure was 24 percent).
They were migrated out (see `scripts/18_fix_industry_market_edges.py`) and the
agent no longer produces them. The `/api/intelligence/relationship-coverage`
endpoint carries a `self_loop_edges` canary that must stay at 0; a non-zero
value means page-scoped entity facts have leaked back into the links table.

## Scoring signals

Beyond the base confidence, each edge stores component scores used by later
phases: semantic similarity, entity overlap, geography match, market match, and
an SEO value score. Business value score is left for Agent 5, documented rather
than silently zeroed.

## Safety

- `--dry-run` builds and reports edges without writing.
- Duplicate edges are prevented by a unique key on
  (source_node_id, target_node_id, relationship_type).
- Stale edges from a previous run whose logic no longer produces them are
  removed, but only `pending` edges created by this agent; anything a human has
  reviewed (approved, rejected, corrected) is preserved.
- All writes happen in one transaction.

## Commands

Dry run:

```powershell
python agents/agent_3_relationship_mapping.py --dry-run
```

Small batch:

```powershell
python agents/agent_3_relationship_mapping.py --limit 25 --dry-run
```

Full live run:

```powershell
python agents/agent_3_relationship_mapping.py
```

## Verification

```powershell
python -m pytest tests/test_relationship_agent.py -q
```

Check the graph through the API:

- `GET /api/relationships/types` edge counts and average confidence per type
- `GET /api/intelligence/relationship-coverage` page-to-page connectivity
  against the 70 percent target, plus the self-loop canary
- `GET /api/pages/{node_id}/relationships` every connection for one page
