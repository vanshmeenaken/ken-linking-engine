# Business Priority Agent

## Purpose

Agent 5 scores every active page's commercial priority and writes a
High/Medium/Low band to `content_nodes.business_priority`. The band drives how
aggressively later phases push internal links to a page: High means push from
authority pages, Medium means normal contextual links, Low means only where
highly relevant.

This is the second half of the fix-first decision. Agent 4 finds pages that are
broken; Agent 5 says which broken pages are worth fixing. The two together let
the recommendation engine target valuable-and-broken pages first, rather than
treating every orphan equally.

## Factors and weights

The score is a weighted blend of factors computable from current data. Weights
sum to 1.0:

- `intent` 0.35 commercial intent of the content type
- `authority` 0.25 existing page authority, a proxy for established value
- `industry_priority` 0.20 configurable, strategic industries weighted up
- `country_priority` 0.20 configurable, strategic geographies weighted up

Intent scores by content type: report (decision) 1.0, case study
(consideration) 0.6, article (awareness) 0.3.

Bands: High at 0.66 or above, Medium at 0.4 or above, otherwise Low.

## Why buyer intent is a proxy today

Intent is currently inferred from page type: a report page implies a
decision-stage visitor, an article implies a browser. This is a reasonable
proxy but not a measurement. Once GA4 data is connected, real conversion signals
(sample requests, enquiries per page) replace the proxy, so a high-converting
article can be recognised as valuable even though its type suggests otherwise.

## Configurable placeholders

The master PRD lists many business inputs that this project does not have data
for yet: revenue potential, report sales priority, consulting and survey and
expert-panel and procurement relevance, sales-team demand, search demand, and
lead-conversion potential. These are kept as named placeholders in the agent so
the model documents exactly what is missing, rather than silently omitting it.
Real values plug into the configuration without changing the model.

Strategic industries and geographies (Healthcare, Automotive/Transportation/
Logistics, Technology and Telecom; India, Saudi Arabia, UAE) are the MVP-scope
priorities and are weighted up; everything else gets a neutral baseline so no
page is zeroed out.

## Why search opportunity is deliberately excluded

`search_opportunity_score` measures an SEO gap, not commercial value. Mixing it
into the priority score made every orphan look high priority (no pages landed in
Low). Business value and SEO opportunity are separate axes and are kept separate
here; the later link score (master PRD section 17) combines them explicitly.

## Safety

- `--dry-run` scores and reports without writing.
- Idempotent: re-running updates the band in place.

## Commands

```powershell
python agents/agent_5_business_priority.py --dry-run
python agents/agent_5_business_priority.py
```

## Verification

```powershell
python -m pytest tests/test_business_priority_agent.py -q
```

Through the API: `GET /api/intelligence/business-priority` gives band counts, a
band-by-content-type matrix, and the top High-priority pages.
