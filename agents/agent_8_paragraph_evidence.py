"""Agent 8 - Paragraph Evidence Agent (master PRD 13.8; Phase 3).

Maps paragraph claims to evidence. For every meaningful paragraph of a page:

  - classifies it (market_claim vs context) from the numbers it carries;
  - fingerprints it (sha256 knowledge hash, so re-crawls can detect change);
  - checks whether a claim is SUPPORTED - a link inside the paragraph itself,
    a link elsewhere in its section, or nothing at all;
  - finds the best evidence page (a report or case study covering the same
    subject and geography) for unsupported claims, above a similarity
    threshold - below it, no evidence is recorded (never pad).

Deterministic (project discipline: deterministic before LLM): claim
detection is regex over the paragraph's own text; evidence matching is the
same vector search used everywhere else (analysis/vector_store.py). Nothing
is invented; a crawl failure writes nothing.

Structural sections (author bios, FAQs, TOCs, CTAs...) are excluded via the
same EXCLUDED_PLACEMENT_PURPOSES guard used by contextual placement - a
claim inside boilerplate is not a claim worth evidencing.

Writes one row per kept paragraph to paragraph_evidence_map (replacing that
page's previous rows on re-run).

Usage:
    python agents/agent_8_paragraph_evidence.py --dry-run
    python agents/agent_8_paragraph_evidence.py --limit 5 --dry-run
    python agents/agent_8_paragraph_evidence.py               # rec source pages
    python agents/agent_8_paragraph_evidence.py --all-reports # every active report
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agent_9_section_purpose import (EXCLUDED_PLACEMENT_PURPOSES,
                                            classify_heading)
from analysis.contextual_placement import fetch_sections
from analysis.subject_similarity import market_technology_relevance
from analysis.vector_store import VectorStore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

# A paragraph is a MARKET CLAIM when it states a quantified market fact:
# money sizes, growth rates, market share percentages. A bare year ("2025")
# or a list numbering is NOT a claim - the number must be a quantity.
_CLAIM_PATTERNS = [
    re.compile(r"\bUSD?\s?\$?\s?[\d,.]+\s*(billion|million|bn|mn|trillion)", re.I),
    re.compile(r"\$\s?[\d,.]+\s*(billion|million|bn|mn|trillion)", re.I),
    re.compile(r"\bCAGR\b", re.I),
    re.compile(r"[\d.]+\s?%"),
    re.compile(r"\b(valued at|worth|expected to reach|projected to reach|"
               r"estimated at|grew by|growing at|increased by|declined by)\b", re.I),
]

# Minimum vector similarity for an evidence candidate to even be considered.
# Vector score alone is NOT sufficient: the first dry run showed a China tire
# report "evidencing" a battery-management claim (shared "China" + automotive
# terms) and a railway-management report matching on the words "management
# system". Every candidate must also pass the subject gate
# (market_technology_relevance - Shrey's validated 4-layer method, the same
# gate Agent 6 uses) and the geography gate below.
EVIDENCE_THRESHOLD = 0.20


def knowledge_hash(paragraph: str) -> str:
    """Stable fingerprint of a paragraph's content (the PRD's knowledge
    hash): whitespace-collapsed, lowercased, sha256."""
    normalised = re.sub(r"\s+", " ", (paragraph or "").strip().lower())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def is_market_claim(paragraph: str) -> bool:
    return any(p.search(paragraph or "") for p in _CLAIM_PATTERNS)


def support_status(paragraph_links: int, section_links: int) -> str:
    if paragraph_links > 0:
        return "supported"
    if section_links > 0:
        return "section_supported"
    return "unsupported"


@dataclass
class EvidenceRecord:
    node_id: str
    url: str
    section_heading: str | None
    section_purpose: str
    paragraph_index: int
    paragraph_text: str
    paragraph_hash: str
    classification: str
    has_numeric_claim: bool
    support_status: str | None
    evidence_target_node_id: str | None = None
    evidence_target_url: str | None = None
    evidence_type: str | None = None
    evidence_score: float | None = None


def build_evidence_records(node_id: str, url: str,
                           sections: list[dict]) -> list[EvidenceRecord]:
    """Interpret one crawled page's paragraphs (pure - no I/O, testable).
    Evidence targets are attached separately by the agent (needs the DB)."""
    records: list[EvidenceRecord] = []
    index = 0
    for sec in sections:
        purpose = classify_heading(sec["heading"])
        if purpose in EXCLUDED_PLACEMENT_PURPOSES:
            index += len(sec["paragraphs"])
            continue
        for para, para_links in zip(sec["paragraphs"], sec["paragraph_links"]):
            claim = is_market_claim(para)
            records.append(EvidenceRecord(
                node_id=node_id, url=url,
                section_heading=sec["heading"], section_purpose=purpose,
                paragraph_index=index,
                paragraph_text=para[:1000],
                paragraph_hash=knowledge_hash(para),
                classification="market_claim" if claim else "context",
                has_numeric_claim=claim,
                support_status=(support_status(para_links,
                                               sec["internal_link_count"])
                                if claim else None),
            ))
            index += 1
    return records


class ParagraphEvidenceAgent:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = Path(db_path)

    def _connect_ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _pages(self, limit: int | None, all_reports: bool) -> list[sqlite3.Row]:
        conn = self._connect_ro()
        try:
            if all_reports:
                q = ("SELECT node_id, url, title, market, country "
                     "FROM content_nodes "
                     "WHERE status='active' AND content_type='report'")
            else:
                q = ("SELECT node_id, url, title, market, country "
                     "FROM content_nodes "
                     "WHERE status='active' AND node_id IN "
                     "(SELECT DISTINCT source_node_id FROM link_recommendations)")
            if limit:
                q += f" LIMIT {int(limit)}"
            return conn.execute(q).fetchall()
        finally:
            conn.close()

    def _evidence_store(self) -> tuple[VectorStore, dict[str, sqlite3.Row]]:
        """A vector store over every active report and case study (title +
        market + country, geography kept - evidence should match geography)."""
        conn = self._connect_ro()
        try:
            rows = conn.execute(
                """SELECT node_id, url, title, market, country, content_type
                   FROM content_nodes
                   WHERE status='active'
                     AND content_type IN ('report', 'case_study')""").fetchall()
        finally:
            conn.close()
        items = [(r["node_id"],
                  " ".join(filter(None, [r["title"], r["market"], r["country"]])))
                 for r in rows]
        return VectorStore.fit(items), {r["node_id"]: r for r in rows}

    def attach_evidence(self, records: list[EvidenceRecord],
                        store: VectorStore,
                        nodes: dict[str, sqlite3.Row],
                        source: sqlite3.Row | dict) -> int:
        """Find the best evidence page for each unsupported market claim.

        Three gates, all mandatory - never pad:
          1. vector score >= EVIDENCE_THRESHOLD (candidate discovery only);
          2. geography: a country-specific candidate must match the source
             page's country (a West Africa battery report cannot evidence a
             China market number); country-less/global candidates pass;
          3. subject: market_technology_relevance between the source page's
             subject and the candidate's subject must accept (kills
             term-overlap matches like tire-report-for-battery-claim).
        """
        src_subject = " ".join(filter(None, [source["market"], source["title"]]))
        src_country = (source["country"] or "").strip().lower()
        attached = 0
        for r in records:
            if r.classification != "market_claim":
                continue
            if r.support_status == "supported":
                continue  # the claim already carries its own link
            for res in store.search(r.paragraph_text, top_k=5,
                                    exclude={r.node_id}):
                if res.score < EVIDENCE_THRESHOLD:
                    break  # results are sorted; nothing further qualifies
                cand = nodes[res.item_id]
                cand_country = (cand["country"] or "").strip().lower()
                if cand_country and src_country and cand_country != src_country:
                    continue
                cand_subject = " ".join(
                    filter(None, [cand["market"], cand["title"]]))
                rel = market_technology_relevance(
                    store.corpus, src_subject, cand_subject)
                if not rel.accepted:
                    continue
                r.evidence_target_node_id = cand["node_id"]
                r.evidence_target_url = cand["url"]
                r.evidence_type = cand["content_type"]
                r.evidence_score = round(res.score, 4)
                attached += 1
                break
        return attached

    def crawl(self, limit: int | None = None, all_reports: bool = False,
              delay: float = 0.3) -> tuple[list[EvidenceRecord], list[str]]:
        pages = self._pages(limit, all_reports)
        store, nodes = self._evidence_store()
        records, failed = [], []
        print(f"Crawling {len(pages)} pages for paragraph evidence...")
        for i, page in enumerate(pages, 1):
            try:
                sections = fetch_sections(page["url"])
                if not sections:
                    failed.append(page["url"])
                    continue
                page_records = build_evidence_records(
                    page["node_id"], page["url"], sections)
                self.attach_evidence(page_records, store, nodes, page)
                records.extend(page_records)
            except Exception as exc:
                failed.append(page["url"])
                print(f"  [{i}] skip {page['url'].split('/')[-1]}: {exc}")
            time.sleep(delay)
        return records, failed

    def write(self, records: list[EvidenceRecord]) -> int:
        if not records:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            for node_id in {r.node_id for r in records}:
                conn.execute(
                    "DELETE FROM paragraph_evidence_map WHERE node_id=?",
                    (node_id,))
            for r in records:
                conn.execute(
                    """INSERT INTO paragraph_evidence_map
                       (evidence_row_id, node_id, url, section_heading,
                        section_purpose, paragraph_index, paragraph_text,
                        paragraph_hash, classification, has_numeric_claim,
                        support_status, evidence_target_node_id,
                        evidence_target_url, evidence_type, evidence_score,
                        crawled_at, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (str(uuid.uuid4()), r.node_id, r.url, r.section_heading,
                     r.section_purpose, r.paragraph_index, r.paragraph_text,
                     r.paragraph_hash, r.classification,
                     int(r.has_numeric_claim), r.support_status,
                     r.evidence_target_node_id, r.evidence_target_url,
                     r.evidence_type, r.evidence_score, now, now, now))
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
    parser.add_argument("--all-reports", action="store_true",
                        help="crawl every active report, not just pages with "
                             "outgoing link recommendations")
    args = parser.parse_args(argv)

    agent = ParagraphEvidenceAgent(args.db)
    records, failed = agent.crawl(args.limit, args.all_reports)

    claims = [r for r in records if r.classification == "market_claim"]
    unsupported = [r for r in claims if r.support_status == "unsupported"]
    with_evidence = [r for r in claims if r.evidence_target_node_id]
    pages = len({r.node_id for r in records})
    print(f"\nPages mapped: {pages}   paragraphs: {len(records)}   "
          f"crawl failures: {len(failed)}")
    print(f"Market claims: {len(claims)}")
    print(f"  supported (link in paragraph)  : "
          f"{sum(1 for r in claims if r.support_status == 'supported')}")
    print(f"  section has links, claim not   : "
          f"{sum(1 for r in claims if r.support_status == 'section_supported')}")
    print(f"  unsupported (no links at all)  : {len(unsupported)}")
    print(f"Evidence pages found (>= {EVIDENCE_THRESHOLD}): {len(with_evidence)}")

    if args.dry_run:
        print("Database update: skipped (dry run)")
        print("\nSample unsupported claims with found evidence:")
        shown = 0
        for r in records:
            if r.evidence_target_node_id and r.support_status == "unsupported":
                print(f'  [{r.evidence_score}] "{r.paragraph_text[:100]}..."')
                print(f'     section : {r.section_heading}')
                print(f'     evidence: {r.evidence_target_url.split("/")[-1]} '
                      f'({r.evidence_type})')
                shown += 1
                if shown >= 6:
                    break
    else:
        n = agent.write(records)
        print(f"Database update: committed ({n} paragraph rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
