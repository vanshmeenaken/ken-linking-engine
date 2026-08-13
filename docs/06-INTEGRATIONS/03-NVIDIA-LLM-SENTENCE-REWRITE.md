# NVIDIA LLM Sentence Rewrite

## Purpose

When a link is placed inside an existing sentence, the editor needs to see
the sentence rewritten to carry the anchor naturally, not just be told which
sentence to use. A deterministic template did this first, but every link of
the same relationship type got the identical connector phrase ("a dynamic
also shaping the ..."), which reads robotic across a hundred links.

An LLM now writes each rewrite from the sentence's actual content. NVIDIA NIM
hosts the model; the key already lives in `.env` as `NVIDIA_API_KEY`.

## What the LLM does and does not decide

The LLM has one narrow job: rephrase one sentence. Everything else stays
deterministic (project discipline: deterministic before LLM).

| Decision | Owner |
| --- | --- |
| Which pages should link | Agent 6 (scores, gates) |
| Where on the page the link goes | contextual placement + Agent 9 sections |
| What anchor text to use | Agent 7 anchor banks + intent-aware rotation |
| How the sentence reads with the anchor in it | **the LLM** |

## Keys and parallelism

The API takes roughly 10-60 seconds per call, so a serial run over ~120
links is impractical. `.env` holds several keys - `NVIDIA_API_KEY`, then
`NVIDIA_API_KEY_2`, `_3`, ... - and `integrations.nvidia_llm.api_keys()`
returns all of them in order. The generation script runs one worker per key
(`--workers` overrides), so concurrency never concentrates rate-limit
pressure on a single credential.

`.env` is gitignored; keys must never be committed, pasted into docs, or
echoed into logs.

## Model and safety

- Model: `meta/llama-3.3-70b-instruct` via `https://integrate.api.nvidia.com/v1`
- Prompt rules: keep every existing fact and number byte-for-byte, invent
  nothing new, use the anchor verbatim, one sentence, output only the
  sentence.
- Verification before any rewrite is accepted
  (`integrations/nvidia_llm.py`):
  1. the anchor must appear verbatim in the output;
  2. every number in the original must still appear in the rewrite
     (`_contains_all_numbers`) - a dropped or altered figure rejects the
     response outright.
- Output punctuation is normalised (`normalise_punctuation`) to match the
  scraped-page style: no em/en dashes, no smart quotes. The rewrite then
  sits beside the original sentence without a visible style shift, and the
  web team can paste it as-is.
- Fails closed: a missing key, a network error, or a failed check returns
  `None`, and the caller falls back to the deterministic template. The
  pipeline never breaks because an external API had a bad moment.

## Precomputed, not live

`scripts/36_generate_woven_sentences.py` generates and stores the rewrite in
`link_recommendations.woven_sentence`, with `woven_sentence_source` recording
`llm` or `template`. API reads never call the LLM - an API call per dashboard
page load would be slow and would re-spend the budget on unchanged data.

## Commands

```powershell
python scripts/35_woven_sentence_migration.py          # one-time schema
python scripts/36_generate_woven_sentences.py --limit 3 --dry-run
python scripts/36_generate_woven_sentences.py          # all active links
python scripts/36_generate_woven_sentences.py --only-template-fallbacks
python scripts/36_generate_woven_sentences.py --only-missing
```

`--only-template-fallbacks` retries only rows that fell back to the
template, for when an API issue is resolved. `--only-missing` fills in rows
with no stored rewrite - which is exactly the set re-placed since the last
run, because `scripts/22_place_contextual_links.py` clears `woven_sentence`
whenever it changes a placement (a rewrite of a sentence no longer in use
would otherwise be shown to the editor).

## Standard follow-up after any re-placement

```powershell
python scripts/22_place_contextual_links.py      # placements change
python scripts/36_generate_woven_sentences.py --only-missing
```

## Verification

```powershell
python -m pytest tests/test_nvidia_llm.py tests/test_generate_woven_sentences.py -q
sqlite3 ken_links.db "SELECT woven_sentence_source, COUNT(*) FROM link_recommendations WHERE woven_sentence IS NOT NULL GROUP BY woven_sentence_source"
```

Tests mock the client completely - the suite makes no network calls. The
dashboard labels any template-sourced rewrite so an editor knows which
wording came from the fallback.

## Example

Original sentence on the Russia e-learning report:

> The future of the Russia e-learning and skills platforms market appears
> promising, driven by technological advancements and evolving educational
> needs.

LLM rewrite carrying the anchor:

> The future of the Russia e-learning and skills platforms market appears
> promising, driven by technological advancements and evolving educational
> needs, similar to trends observed in the South Africa E-Learning and
> Skills Platforms Market.
