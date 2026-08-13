# Paragraph Evidence Agent (Agent 8)

## Purpose

Agent 8 maps paragraph claims to evidence (master PRD 13.8). For every
meaningful paragraph of a page it records whether the paragraph makes a
market claim (a size, a CAGR, a percentage), whether that claim is supported
by an internal link, and, for unsupported claims, the best evidence page (a
report or case study on the same subject and geography) when one genuinely
exists.

Writes to `paragraph_evidence_map`, one row per paragraph, rebuilt per page
on each run.

## Key concepts

- A market claim is detected by regex over the paragraph's own text: money
  sizes (USD 130 million), CAGR mentions, percentages, and quantified verbs
  (valued at, expected to reach). A bare year is not a claim.
- Every paragraph gets a knowledge hash (sha256 of the normalised text) so
  re-crawls can detect changed content.
- Support status for claims: `supported` (a link inside the paragraph
  itself), `section_supported` (links elsewhere in its section),
  `unsupported` (nothing).
- Evidence attachment requires three gates, all mandatory:
  1. vector similarity above threshold (candidate discovery);
  2. geography: a country-specific candidate must match the source page's
     country (a West Africa battery report cannot evidence a China number);
  3. subject: `market_technology_relevance` must accept, the same validated
     gate Agent 6 uses.
  The gates exist because ungated vector search produced a China tire
  report as "evidence" for a battery-management claim. Below the gates,
  no evidence is recorded; gaps are honest, never padded.
- Structural sections (author bios, FAQs, TOCs, CTAs) never produce
  evidence rows, via the shared `EXCLUDED_PLACEMENT_PURPOSES` guard.

## Safety

- Read-only crawl; crawl failures write nothing.
- Writes only to `paragraph_evidence_map`; it does not create link
  recommendations and never touches editorial decisions.

## Commands

```powershell
python agents/agent_8_paragraph_evidence.py --dry-run
python agents/agent_8_paragraph_evidence.py --limit 5 --dry-run
python agents/agent_8_paragraph_evidence.py                # rec source pages
python agents/agent_8_paragraph_evidence.py --all-reports  # every active report
```

## Verification

```powershell
python -m pytest tests/test_paragraph_evidence_agent.py tests/test_api_evidence.py -q
sqlite3 ken_links.db "SELECT support_status, COUNT(*) FROM paragraph_evidence_map WHERE classification='market_claim' GROUP BY support_status"
curl http://localhost:8000/api/evidence/stats
```

The dashboard's Claim Evidence panel shows the same numbers, including the
pages with the most unsupported claims.
