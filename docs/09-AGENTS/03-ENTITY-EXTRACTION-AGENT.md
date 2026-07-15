# Entity Extraction Agent

## Purpose

Agent 2 extracts normalized entities from the stored metadata of every active
content node: URL slug, title, H1, meta description, and the trusted
industry/country fields written by Agent 1. It populates the knowledge graph's
building blocks so later agents can reason about what each page is about.

It is deliberately metadata-only. No live crawling and no LLM calls, following
the Phase 2 rule of deterministic logic before any model. Body-content entity
types (company, product, technology, regulation, claim, evidence) mostly live
in page text, not metadata, so they are out of scope for this phase and
documented as deferred.

## Entity types extracted

- industry
- country
- region
- market
- time_period

## What it writes (one transaction)

- `content_entities` deduplicated by normalized_name plus entity_type, so
  "UAE" and "United Arab Emirates" resolve to a single entity.
- `node_entities` the page-to-entity mapping, with the source field it came
  from, the extraction method, and a confidence score.
- `content_nodes` backfills `market` and `region` where they were confidently
  extracted.
- `entity_extraction_logs` one row per node plus a run summary row.

## Confidence model

Every mapping carries a score so uncertain ones can be reviewed:

- `0.95` trusted database field (industry, country, verified by Agent 1)
- `0.90` region derived from a trusted country through the taxonomy map
- `0.90` a scope value reclassified as a region (for example "gcc" becomes
  Middle East)
- `0.85` an explicit time period found in the title (year-range regex)
- `0.65` market extracted from a title pattern (base score)
- `+0.15` when the H1 independently agrees with the title's market
- `+0.10` when the URL slug independently agrees (market score caps at 0.90)
- Anything below `0.50` is flagged low-confidence for manual review.

The low-confidence list is what the entity correction workflow (doc 02) and the
`/api/entities/low-confidence` endpoint surface for a human to approve, correct,
or reject. Original extracted values are always preserved.

## Safety

- `--dry-run` performs full extraction and reporting without any database write.
- Deduplication prevents a second run from creating duplicate entities.
- All writes for a run happen in one SQLite transaction; any failure rolls back.
- A JSON execution report records methodology, counts, and low-confidence items.

## Commands

Dry run (report only, no writes):

```powershell
python agents/agent_2_entity_extraction.py --dry-run
```

Small batch for inspection:

```powershell
python agents/agent_2_entity_extraction.py --limit 25
```

Full live run:

```powershell
python agents/agent_2_entity_extraction.py
```

## Verification

```powershell
python -m pytest tests/test_entity_extraction_agent.py tests/test_entity_corrections.py -q
```

Check coverage after a run:

```powershell
python scripts/11_entity_coverage_report.py
```

Or through the API: `GET /api/intelligence/entity-coverage` reports the share of
active pages with any entity, with geography, and with an industry or market,
against the Phase 2 targets (95 percent, 90 percent, 80 percent).
