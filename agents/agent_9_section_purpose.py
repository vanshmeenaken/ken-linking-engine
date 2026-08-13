"""Agent 9 - Section Purpose Agent (master PRD 13.9; Phase 3).

Reads each page's REAL section structure (analysis/contextual_placement.py
fetch_sections) and, per section, records: what the section is for, whether
it is a sensible home for internal links, what kind of link belongs there,
and two honesty flags - sections with no recognisable purpose and linkable
sections that currently carry no internal links.

Deterministic and template-based (project discipline: deterministic before
LLM): purposes come from keyword rules over the page's own headings, never
from guessing. The crawler reports the page as it is; this agent interprets.

Writes one row per section to section_purpose_map (replacing that page's
previous rows, so re-running refreshes rather than duplicates). Pages that
fail to crawl are skipped and reported - never fabricated (a crawl failure
is not evidence about the page; the same rule as contextual placement).

Usage:
    python agents/agent_9_section_purpose.py --dry-run
    python agents/agent_9_section_purpose.py --limit 5 --dry-run
    python agents/agent_9_section_purpose.py              # recommendation sources
    python agents/agent_9_section_purpose.py --all-active # every active page
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.contextual_placement import fetch_sections

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

_CHAPTER_BANNER_RE = re.compile(r"^chapter\s*\d+", re.IGNORECASE)

# (purpose, keywords) in priority order: first match wins. Checked against
# the three real page templates (new report / old report / case study) - see
# tests for the actual headings each rule was verified on.
_PURPOSE_KEYWORDS = [
    ("navigation", ("related tags",)),
    ("author", ("about the author",)),
    ("toc", ("report structure", "table of content")),
    ("related_reports", ("related report", "related research",
                         "adjacent report", "related market",
                         "country reports", "regional reports",
                         "other regional")),
    ("cta", ("want the full report", "analyst walkthrough", "download",
             "get in touch", "contact us", "request sample", "let's talk",
             "talk strategy", "book a", "speak to", "get started")),
    ("faq", ("faq", "frequently asked")),
    ("methodology", ("methodology", "our approach", "research approach",
                     "market assessment", "go-to-market", "strategy phase",
                     "survey")),
    ("case_study", ("client background", "problem statement",
                    "key initiative", "engagement outcome", "the client",
                    "business problem", "situation", "complication",
                    "solution", "problem", "outcome", "result", "impact")),
    ("competitive", ("competitive", "competition", "players",
                     "company profiles", "companies")),
    ("regional", ("regional analysis", "by region", "geography")),
    ("segmentation", ("segmentation", "segment", "products")),
    ("market_size", ("market size", "market data", "market breakdown",
                     "growth forecast", "market value")),
    ("industry_analysis", ("growth driver", "challenge", "opportunit",
                           "industry analysis")),
    ("audience", ("target audience", "stakeholder", "who should")),
    ("scope", ("scope",)),
    # "About the Report" is its OWN purpose, not "overview": on shorter
    # report templates it is the page's entire body (segmentation, players,
    # regional notes - real varied prose), not a restatement of the report's
    # headline numbers. Bundling it under "overview" banned cross-report
    # links from the ONLY content section 50 short-template pages have,
    # collapsing most of them to the Related Reports fallback - the opposite
    # of the 2026-08-13 editorial intent. Checked BEFORE "overview" so its
    # keyword ("about the report") is claimed here first.
    ("about_report", ("about the report",)),
    ("overview", ("overview", "market summary",
                  "executive summary", "introduction", "conclusion",
                  "insight")),
]

# Case-study pages headline their narrative with bare question words. These
# must match EXACTLY (not as substrings - "how" appears inside countless
# report headings) so they sit outside the keyword loop.
_CASE_STUDY_EXACT = {"why", "who", "where", "when", "what", "how"}

# Sections whose paragraphs must never HOST a contextual or evidence link,
# even when a sentence there matches well: structural/meta content (found via
# manual review - an author bio's "we support OEMs with data-driven analysis"
# vector-matched a cement-market target, and an FAQ answer matched a laundry
# target despite the FAQ-stays-link-free rule). Shared by contextual
# placement (scripts/22) and Agent 8 evidence mapping.
EXCLUDED_PLACEMENT_PURPOSES = {
    "toc", "methodology", "faq", "cta", "chapter_banner", "navigation",
    "audience", "scope", "author",
}

# Cross-report links (Agent 6/scripts 22-26: pointing THIS page at a
# DIFFERENT market's report) must never land in the page's own opening hero
# stat or its Market Overview - those exist to state THIS report's own
# numbers, not to send the reader elsewhere. Found via manual review: a
# link to Russia's e-learning report was about to sit in South Africa's very
# first sentence ("...worth USD 1.2 billion in 2025..."), and its stored
# "Related Markets" label was a synthetic fallback - the sentence has no
# real heading at all, it is the pre-heading intro paragraph.
#
# This is intentionally SEPARATE from EXCLUDED_PLACEMENT_PURPOSES: Agent 8
# (paragraph evidence) still needs to see intro/overview claims - that is
# precisely where a report's headline stat lives, and Agent 8 evidencing it
# (with a SAME-market source, gated by geography+subject) is a different,
# legitimate use than an unrelated adjacent-market cross-link.
NEVER_CROSS_REPORT_LINK_PURPOSES = EXCLUDED_PLACEMENT_PURPOSES | {"intro", "overview"}

# purpose -> (linkable, guidance). Guidance is the PRD's "recommend
# section-specific links / CTA by section intent" in one plain sentence.
PURPOSE_RULES = {
    "intro": (False, "Opening hero stat - states THIS report's own headline "
                     "numbers. Never link to a different report here; keep "
                     "the reader's first impression focused on this market."),
    "overview": (False, "Market Overview - must stay about THIS report's own "
                        "market only. Never link to a different report here "
                        "(editorial rule, 2026-08-13); send cross-report "
                        "links to segmentation, regional, or competitive "
                        "sections instead."),
    "about_report": (True, "General report body (common on shorter report "
                           "templates, where it is the page's only real "
                           "content) - a legitimate home for cross-report "
                           "links, distinct from the Market Overview ban."),
    "scope": (False, "Scope definition - keep link-free."),
    "audience": (False, "Audience list - keep link-free."),
    "market_size": (True, "Data narrative - link regional versions of this "
                          "market for comparison, or a case study evidencing "
                          "the numbers."),
    "segmentation": (True, "Segment framework - link segment-specific reports "
                           "where a segment has its own page."),
    "regional": (True, "Regional analysis - the best home for the same market "
                       "in other geographies."),
    "industry_analysis": (True, "Drivers and challenges - link adjacent "
                                "markets and supporting articles or case "
                                "studies as evidence."),
    "competitive": (True, "Competitive landscape - link case studies or "
                          "reports covering the same key players."),
    "toc": (False, "Report structure listing - keep link-free."),
    "methodology": (False, "Methodology - keep link-free."),
    "faq": (False, "FAQ - keep link-free for now (answers may carry links "
                   "in a later phase)."),
    "related_reports": (True, "The page's related-reports area - where "
                              "related_reports_block links belong."),
    "cta": (False, "Conversion block - keep to its own call to action; no "
                   "report links."),
    "case_study": (True, "Case study narrative - link the market report this "
                         "case evidences."),
    "chapter_banner": (False, "Chapter banner heading - not a content "
                              "section."),
    "navigation": (False, "Tag/navigation block - carries its own links; "
                          "add nothing."),
    "author": (False, "Author bio - keep link-free."),
    "other": (False, "Unrecognised purpose - review manually before placing "
                     "links."),
}


def classify_heading(heading: str | None) -> str:
    """Map a real section heading to a purpose. None = pre-heading intro."""
    if heading is None:
        return "intro"
    h = heading.strip().lower()
    if _CHAPTER_BANNER_RE.match(h):
        return "chapter_banner"
    if h.rstrip(":?") in _CASE_STUDY_EXACT:
        return "case_study"
    for purpose, keywords in _PURPOSE_KEYWORDS:
        if any(k in h for k in keywords):
            return purpose
    # a "heading" longer than a real section label is a prose headline
    # ("Global Application Container Market, valued at USD 5.8 billion,
    # thrives on...") - one template opens with these summary sentences
    if len(h) > 80 and "market" in h:
        return "overview"
    return "other"


@dataclass
class SectionRecord:
    node_id: str
    url: str
    heading: str | None
    section_order: int
    purpose: str
    paragraph_count: int
    internal_link_count: int
    linkable: bool
    link_guidance: str
    flag_purposeless: bool
    flag_missing_links: bool


def build_section_records(node_id: str, url: str,
                          sections: list[dict]) -> list[SectionRecord]:
    """Interpret one crawled page's sections (pure - no I/O, testable)."""
    records = []
    for sec in sections:
        purpose = classify_heading(sec["heading"])
        linkable, guidance = PURPOSE_RULES[purpose]
        n_paras = len(sec["paragraphs"])
        records.append(SectionRecord(
            node_id=node_id, url=url,
            heading=sec["heading"], section_order=sec["order"],
            purpose=purpose,
            paragraph_count=n_paras,
            internal_link_count=sec["internal_link_count"],
            linkable=linkable,
            link_guidance=guidance,
            # a heading nobody can classify, with no content under it
            flag_purposeless=(purpose == "other" and n_paras == 0),
            # a good link home that currently links nowhere
            flag_missing_links=(linkable and n_paras > 0
                                and sec["internal_link_count"] == 0),
        ))
    return records


class SectionPurposeAgent:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = Path(db_path)

    def _pages(self, limit: int | None, all_active: bool) -> list[sqlite3.Row]:
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            if all_active:
                q = ("SELECT node_id, url FROM content_nodes "
                     "WHERE status='active'")
            else:
                # placement needs sections for pages that GIVE links
                q = ("SELECT node_id, url FROM content_nodes "
                     "WHERE status='active' AND node_id IN "
                     "(SELECT DISTINCT source_node_id FROM link_recommendations)")
            if limit:
                q += f" LIMIT {int(limit)}"
            return conn.execute(q).fetchall()
        finally:
            conn.close()

    def crawl(self, limit: int | None = None, all_active: bool = False,
              delay: float = 0.3) -> tuple[list[SectionRecord], list[str]]:
        """Crawl pages and interpret sections. Returns (records, failed_urls)."""
        pages = self._pages(limit, all_active)
        records, failed = [], []
        print(f"Crawling {len(pages)} pages for section structure...")
        for i, page in enumerate(pages, 1):
            try:
                sections = fetch_sections(page["url"])
                if not sections:
                    failed.append(page["url"])
                    print(f"  [{i}] no sections: {page['url'].split('/')[-1]}")
                    continue
                records.extend(
                    build_section_records(page["node_id"], page["url"], sections))
            except Exception as exc:
                failed.append(page["url"])
                print(f"  [{i}] skip {page['url'].split('/')[-1]}: {exc}")
            time.sleep(delay)
        return records, failed

    def write(self, records: list[SectionRecord]) -> int:
        if not records:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            # replace each crawled page's rows wholesale (refresh, not append)
            for node_id in {r.node_id for r in records}:
                conn.execute(
                    "DELETE FROM section_purpose_map WHERE node_id=?", (node_id,))
            for r in records:
                conn.execute(
                    """INSERT INTO section_purpose_map
                       (section_id, node_id, url, heading, section_order,
                        purpose, paragraph_count, internal_link_count,
                        linkable, link_guidance, flag_purposeless,
                        flag_missing_links, crawled_at, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (str(uuid.uuid4()), r.node_id, r.url, r.heading,
                     r.section_order, r.purpose, r.paragraph_count,
                     r.internal_link_count, int(r.linkable), r.link_guidance,
                     int(r.flag_purposeless), int(r.flag_missing_links),
                     now, now, now))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return len(records)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all-active", action="store_true",
                        help="crawl every active page, not just pages that "
                             "have outgoing link recommendations")
    args = parser.parse_args(argv)

    agent = SectionPurposeAgent(args.db)
    records, failed = agent.crawl(args.limit, args.all_active)

    by_purpose: dict[str, int] = {}
    for r in records:
        by_purpose[r.purpose] = by_purpose.get(r.purpose, 0) + 1
    pages = len({r.node_id for r in records})
    print(f"\nPages sectioned: {pages}   sections: {len(records)}   "
          f"crawl failures: {len(failed)}")
    for purpose, count in sorted(by_purpose.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}  {purpose}")
    print(f"Flagged purposeless: {sum(r.flag_purposeless for r in records)}")
    print(f"Linkable but link-free: {sum(r.flag_missing_links for r in records)}")

    if args.dry_run:
        print("Database update: skipped (dry run)")
    else:
        n = agent.write(records)
        print(f"Database update: committed ({n} section rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
