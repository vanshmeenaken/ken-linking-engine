# Link Recommendation Agent

## Purpose

Agent 6 is the core of Phase 3. It turns each trusted relationship edge from
Agent 3 into a concrete, scored, validated internal-link recommendation:
"link this source page to this target page, with this anchor text, in this
section, because." The system stops only finding opportunities and starts
producing the actual linking instructions.

Recommendations are written to `link_recommendations` with `status = 'pending'`.
Nothing is auto-applied; every recommendation is for human editorial review.

## What each recommendation contains

Source and target page, relationship type, anchor text, placement (type and
section), a 0-100 link score with its band, component scores (SEO, business,
AI readiness, confidence), a validation outcome and risk flag, and a plain
reason sentence.

## Link score (master PRD section 17)

The master PRD defines a fourteen-factor link score. Ten factors are computable
now from Phase 1/2 data plus live GSC and GA4; the other four need data this
phase does not have and are deferred, not faked. The score is rescaled over the
computable weights so it stays an honest 0-100, and the deferred factors are
recorded in the run report rather than silently scored as zero.

Computable now: semantic similarity (16), entity overlap (12), market
relationship (10), geography (8), search intent from GSC striking distance (8),
business value (8), authority transfer (8), crawl priority (5), anchor quality
(5), conversion path from GA4 (4), AI readiness (3).

Deferred: freshness (6, dates not populated), evidence support (5, Phase 5),
sentiment/external (2, out of scope).

## Score bands (master PRD 17.2)

- 90-100 priority, strongly recommend
- 80-89 strong, needs editor review
- 65-79 secondary, related blocks
- 50-64 hold in queue
- below 50 drop, not recommended

Anything below 50 is never written. The project quality bar is never to pad:
a short set of correct recommendations beats a long noisy one.

## Market and Technology Relevance Gate

Report-to-report candidates are accepted only after two independent business signals pass. Market relevance carries 65% of the combined relevance score and must be at least 0.30. Technology relevance carries 35% and must be at least 0.50. Geography cannot create relevance; it is evaluated only after the pair passes.

Accepted links are classified as:

- `regional`: the same or synonymous market in another geography
- `adjacent`: a closely related market and technology in the same/global scope
- `adjacent_regional`: a closely related market and technology in another geography

Broad-to-specialized links are supported when the technology-specific report retains the source market core, such as Rehabilitation Equipment to Rehabilitation Robots. Shared industry, geography, or generic title words are insufficient. Related report scoring gives 45% to market relevance and 30% to technology relevance, so these two signals dominate the final recommendation.

Adjacent report links use `placement_type = related_reports_block` and still require editorial approval. The optional `--use-llm-judge` flag can send prefiltered titles to a configured external model for a final semantic check; it is disabled by default so report metadata is not disclosed externally without an explicit decision.

## Anchor text

A descriptive anchor is built from the target's country and market
(master PRD 18.3 country plus market format), for example "India Online Grocery
Market". Geographic acronyms are kept upper (UAE, KSA, USA), and " Market" is
appended only when the value does not already end in it, so the agent never
emits "... Market Market". If structured fields are missing it falls back to a
cleaned title with a lower anchor-quality score. Generic anchors ("click here",
"read more") are never produced, and Agent 10 rejects them if they ever were.

Agent 7 builds diverse anchor banks per target, and
`scripts/26_rotate_recommendation_anchors.py` rotates those variants across
inbound recommendations without requiring a live-page crawl.

## Validation gate

Every proposed link is run through Agent 10 (SEO Validation) before it is
recorded. A link Agent 10 rejects is still stored, but with `status = 'rejected'`
and the risk reason, never as pending. This makes Agent 10 the mandatory gate
the master PRD requires (section 13.10).

## Safety

- `--dry-run` builds, scores, validates, and reports without any database write.
- `--limit` restricts to the top-confidence edges for a quick inspection.
- Recommendations are keyed unique on (source, target, relationship_type), so
  re-running updates rather than duplicates.
- All writes happen in one transaction.

## Commands

```powershell
python agents/agent_6_link_recommendation.py --dry-run
python agents/agent_6_link_recommendation.py --limit 20 --dry-run
python agents/agent_6_link_recommendation.py
```

## Verification

```powershell
python -m pytest tests/test_link_recommendation_agent.py -q
```

Through the API:

- `GET /api/recommendations/review-queue` the editorial queue, highest score first
- `GET /api/recommendations/stats` totals by band, status, validation
- `GET /api/recommendations` filterable list
- `GET /api/pages/{node_id}/recommendations` links a page should add or receive
