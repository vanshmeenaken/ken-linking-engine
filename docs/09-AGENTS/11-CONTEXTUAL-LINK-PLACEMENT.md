# Contextual Link Placement

## Purpose

Finds the real sentence in a source page's body where a recommended link
genuinely belongs (master PRD 18.6, placement priority #1: relevant body
paragraph). This is the highest-value placement for AI search / GEO: a link
embedded in a relevant sentence teaches an AI engine how two topics relate,
which a footer "related links" box does not.

Applied across the recommendations by `scripts/22_place_contextual_links.py`,
which crawls the distinct source pages that have recommendations (read-only)
and enriches each recommendation with its placement.

## Ranking method: vector search first, keyword fallback

1. **Vector search** (`best_placement_semantic`, primary). Builds a small
   VectorStore (see the Vector Search Foundation doc) over the source page's
   paragraphs and searches it with the target's subject text. Catches
   paraphrased matches that keyword overlap would miss.
2. **Keyword overlap** (`best_placement`, fallback). Used only when vector
   search finds nothing above threshold - typically very short or sparse
   paragraphs where TF-IDF vectors carry little signal.
3. **Neither finds a home** -> the link is not forced into an unrelated
   sentence. It is routed to `placement_type='related_reports_block'`, an
   end-of-page block (the pattern real SEO publications use for links that do
   not have a natural contextual home).

## Precision guards (both found via manual review, both are correctness rules,
not ranking-method details, so they apply regardless of which method wins)

**Geography exclusion.** The search/match query is built from `subject_text()`,
which strips country/region words before comparison. Two paragraphs sharing
only "Middle East" or "UAE" must never count as a topical match; only sharing
the actual subject ("cold storage", "car rental") qualifies. Caught in review:
a UAE Cold Storage link had matched a Saudi real-estate paragraph on region
alone; the fix moved it to a paragraph about the KSA cold-storage market.

**Boilerplate filtering.** Ken's report pages end with a standard "why work
with us" company-pitch block (consultant methodology, "syndicated and
customized", "if you need any support"). Its promotional language overlaps
with target titles enough to occasionally outscore genuine content paragraphs.
`is_boilerplate()` filters these out of `fetch_paragraphs()` before any ranking
happens, so they can never win regardless of method. Caught in review: for a
Vietnam Pharmaceutical Market Entry target, the boilerplate paragraph
"We have set a benchmark in the industry..." outscored the page's own genuine
Brazil-pharmaceuticals content paragraph; filtering the boilerplate out fixed
it.

## Anchor rotation

When several source pages link to the same target, `scripts/22_place_...`
rotates their anchor text from that target's anchor bank (Agent 7) instead of
repeating the identical anchor (master PRD 18.4: no single exact-match anchor
should dominate). The strongest inbound link keeps the target's primary
anchor; subsequent ones get a variation (Outlook, regional form, etc.).

## Safety

- Crawl is read-only, one request per distinct source page, with a short delay
  between requests.
- `--dry-run` runs placement and reports without writing.
- Idempotent: re-running recomputes placement, anchors, and paragraph vectors
  from scratch (`ON CONFLICT ... DO UPDATE`).
- Paragraph text and vectors are persisted (`paragraph_embeddings`), so a
  future placement run can be extended to reuse them without recrawling.

## Commands

```powershell
python scripts/22_place_contextual_links.py --dry-run
python scripts/22_place_contextual_links.py
```

## Verification

```powershell
python -m pytest tests/test_contextual_placement.py -q
```

Through the API and dashboard: `GET /api/recommendations/review-queue` and
`GET /api/pages/{node_id}/recommendations` both return `suggested_sentence`;
the dashboard's Link Recommendations table shows it in italics under each
recommendation's placement.
