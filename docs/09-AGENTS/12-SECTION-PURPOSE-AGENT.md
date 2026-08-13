# Section Purpose Agent (Agent 9)

## Purpose

Agent 9 reads each page's real section structure (its actual H2 headings and
the paragraphs under them) and records what every section is for, whether it
is a sensible home for internal links, and what kind of link belongs there.
This is master PRD 13.9. Before it existed, placement labels were guessed
from the relationship type; now they come from the page itself.

Writes to `section_purpose_map`, one row per section, rebuilt per page on
each run.

## Key concepts

- The crawler (`fetch_sections` in `analysis/contextual_placement.py`)
  reports the page as it is: headings in document order, paragraphs attached
  to the heading above them, internal links counted anywhere in the section
  (including link lists in list items), plus table and image counts.
- `classify_heading` maps a real heading to one of ~19 purposes using
  keyword rules verified against the three live page templates: new reports
  (CHAPTER banners plus descriptive headings), old reports (About the
  Report / FAQ / Adjacent Reports), and case studies (Why / Who / Problem /
  Solution narrative headings).
- Purposes marked not linkable (FAQ, TOC, methodology, CTA, author bio,
  navigation, chapter banners, scope, audience) form
  `EXCLUDED_PLACEMENT_PURPOSES`: contextual links and evidence rows are
  never placed in them. This guard exists because vector search alone once
  matched an author bio and an FAQ answer over genuine market prose.
- Two honesty flags per section: `flag_purposeless` (an unclassifiable
  heading with no content under it) and `flag_missing_links` (a good link
  home that currently links nowhere).

## Safety

- Read-only crawl; a page that fails to crawl writes nothing (a crawl
  failure is not evidence about the page).
- Writes only to `section_purpose_map`; never touches recommendations,
  decisions, or anchors.

## Commands

```powershell
python agents/agent_9_section_purpose.py --dry-run
python agents/agent_9_section_purpose.py --limit 5 --dry-run
python agents/agent_9_section_purpose.py                # recommendation sources
python agents/agent_9_section_purpose.py --all-active   # every active page
```

## Verification

```powershell
python -m pytest tests/test_section_purpose_agent.py -q
sqlite3 ken_links.db "SELECT purpose, COUNT(*) FROM section_purpose_map GROUP BY purpose ORDER BY 2 DESC"
sqlite3 ken_links.db "SELECT COUNT(*) FROM section_purpose_map WHERE flag_missing_links=1"
```
