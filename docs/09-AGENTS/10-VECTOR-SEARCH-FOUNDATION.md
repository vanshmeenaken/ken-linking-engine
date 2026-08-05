# Vector Search Foundation

## Purpose

A real embed/index/search layer (`analysis/vector_store.py`) used to rank a
page's paragraphs by meaning rather than raw keyword overlap. It is the
foundation contextual link placement is built on, and it is designed to scale
from today's 500-page sample to Ken's full catalogue without changing the
interface any caller uses.

## Why this exists

Raw keyword overlap (does paragraph and target share the same words) misses
paraphrasing: a paragraph about "electric vehicles" would not match a target
about "EV market" under pure keyword matching. Vector similarity ranks by
meaning instead, so paraphrased and reworded content is still found.

## What "scales to 42,000 pages" actually means

The public surface is `VectorStore.fit(items)` and `store.search(query, top_k)`.
Nothing outside this module knows how text becomes a vector or how nearest
neighbours are found. Two things can be swapped in later without touching any
caller:

- **The embedder.** Today: TF-IDF (`analysis/tfidf_similarity.py`), stdlib
  only, deterministic. Later: a real embedding model (sentence-transformers or
  an API), which is what actually catches synonyms across different wording
  ("EV" and "electric vehicle") that TF-IDF term-overlap cannot.
- **The index.** Today: brute-force cosine similarity over vectors held in
  memory, loaded from SQLite. Exact and fast at hundreds to a few thousand
  items, proven at today's scale. Later: a proper vector index (pgvector,
  FAISS, or similar) for fast top-k search over millions of vectors.

## Honest limitation of the TF-IDF vectors in use today

TF-IDF weights shared terms, not shared meaning. It is a real improvement over
raw keyword overlap (it is corpus-aware and automatically downweights
boilerplate words like "market" or "report" that appear on nearly every page),
but it does not match "EV" to "electric vehicle" the way a trained embedding
model would. That is the specific gap the embedder swap closes later; nothing
built today needs to change when it happens.

## Storage

- `semantic_embeddings` (Phase 2): one vector per page, already populated.
- `paragraph_embeddings` (this phase, `scripts/23_vector_search_migration.py`):
  one row per body paragraph of a crawled source page, with its text and
  vector, so a future run does not need to recrawl or re-embed.

## Where it is used

Contextual link placement (`analysis/contextual_placement.py`,
`best_placement_semantic`) builds a small VectorStore over one source page's
paragraphs (a handful of items, so brute-force cosine is instant) and searches
it with the target's subject text. See the Contextual Link Placement doc for
the full placement logic, including the boilerplate filter and the
geography-exclusion precision guard.

## Commands

```powershell
python scripts/23_vector_search_migration.py
python scripts/23_vector_search_migration.py --verify-only
```

## Verification

```powershell
python -m pytest tests/test_vector_store.py -q
```
