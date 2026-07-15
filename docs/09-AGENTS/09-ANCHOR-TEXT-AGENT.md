# Anchor Text Agent

## Purpose

Agent 7 builds an anchor bank for each page that receives recommended links: a
set of diverse, safe anchor-text options for one target page. The point is
anchor diversity (master PRD 18.4). If every inbound link to a page used the
same exact-match anchor, that reads as over-optimization to search engines. A
bank lets the deployment step rotate anchors instead of repeating one phrase.

Writes to `anchor_banks`, one row per target page.

## Anchor categories

Each bank holds several categorised variations, all built from the page's own
market, country, and region, so nothing is invented:

- `primary_anchor` the main descriptive anchor, for example "India Online
  Grocery Market"
- `secondary_anchors` natural variations (Outlook, Analysis, Size) plus a
  regional form (for example "Asia Pacific Online Grocery Market")
- `long_tail_anchors` longer phrases (Trends and Forecast, Growth and
  Opportunities)
- `country_specific_anchors` the country + market form
- `market_specific_anchors` the market on its own
- `commercial_anchors` report / sample-report intent
- `restricted_anchors` the generic phrases that must never be used
  ("click here", "read more", and similar), stored so the deployment step
  knows what to reject

## Shared anchor logic

The descriptive-anchor rules live in `analysis/anchor_text.py` and are shared
with Agent 6, so both agents format geography and market suffixes the same way:
acronyms stay upper (UAE, KSA, APAC), and " Market" is only appended when the
value does not already end in it (never "... Market Market"). Generic anchors
are defined once there too.

## Safety

- `--dry-run` builds and reports without writing.
- Idempotent: keyed unique on target_node_id, so re-running updates the bank in
  place rather than duplicating.
- All writes happen in one transaction.

## Commands

Build banks for pages that receive a recommended link (the default):

```powershell
python agents/agent_7_anchor_text.py --dry-run
python agents/agent_7_anchor_text.py
```

Build a bank for every active page, not just recommendation targets:

```powershell
python agents/agent_7_anchor_text.py --all-active
```

## Verification

```powershell
python -m pytest tests/test_anchor_text_agent.py -q
```

Through the API: `GET /api/pages/{node_id}/anchors` returns the full bank for a
page, including the restricted list.
