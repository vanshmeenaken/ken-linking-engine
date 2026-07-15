# SEO Validation Agent

## Purpose

Agent 10 is a deterministic gate that checks a proposed internal link before it
is ever recommended or approved. It takes a source page, a target page, an
anchor text, and a placement, and runs them against the SEO validation rules
(master PRD section 18), returning an explainable per-rule PASS or FAIL. It is
read-only against `content_nodes`: no crawling, no LLM calls.

It was built ahead of the recommendation engine (Agent 6, not yet built). It
works standalone today and is designed to become Agent 6's mandatory gate, so no
recommendation can be produced without passing these checks.

## What it checks

- Target is canonical, indexable, and crawlable
- Anchor text is descriptive, not a generic phrase ("click here", "read more",
  "this report", and similar are rejected)
- Placement is contextually relevant
- The target is not a faceted or low-value URL
- The page is not already overloaded with links
- The link is not a self-link

## Honest scope limits

Documented, not silently skipped:

- Anchor diversity needs a history of previously used anchors per target page.
  That history (`anchor_banks`) does not exist until Agent 7, so this rule
  currently reports PASS with `deferred: true`.
- Cannibalization risk needs the recommendation history table
  (`link_recommendations`), not yet created, and is treated the same way.
- Robots.txt and true crawler-blocked detection need a live fetch. Agent 1
  already does this at crawl time, so this agent reuses that stored result
  (`content_nodes.indexability_status`) rather than re-crawling.

## Safety

Read-only. It never writes to the database and never modifies a page. It only
returns a judgement.

## Commands

Validate one proposed link from the command line:

```powershell
python agents/agent_10_seo_validation.py --source <node_id> --target <node_id> `
  --anchor "India Electric Vehicle Market Outlook" --placement body_paragraph
```

## API

Exposed at `POST /api/internal-linking/validate` (master PRD section 29.2). Body:

```json
{
  "source_node_id": "<id>",
  "target_node_id": "<id>",
  "anchor_text": "India Electric Vehicle Market Outlook",
  "placement": "body_paragraph"
}
```

The response is the full per-rule matrix plus an overall verdict.

## Verification

```powershell
python -m pytest tests/test_seo_validation_agent.py -q
```

The tests cover known good links (should PASS) and known bad ones (generic
anchor, self-link, non-indexable target) to confirm it flags the right things.
