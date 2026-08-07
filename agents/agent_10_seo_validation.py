"""Agent 10 — SEO Validation (master PRD §18 rule engine).

A deterministic gate that checks a proposed internal link (source page,
target page, anchor text, placement) against the SEO validation rules before
it's ever recommended or approved. Read-only against content_nodes — no
crawling, no LLM calls, fully explainable per-rule PASS/FAIL output.

Built ahead of a specific recommendation engine (Agent 6, not built yet):
this agent is designed to be called standalone today, and reused as Agent 6's
mandatory gate whenever recommendations are generated. Exposed via
POST /api/internal-linking/validate (master PRD §29.2).

Honest scope limits (documented, not silently skipped):
  - Anchor diversity (§18.4) needs a history of previously-used anchors per
    target page. That history (`anchor_banks`) doesn't exist until Agent 7 —
    this rule currently always reports PASS with `deferred: true`.
  - Cannibalization risk needs the recommendation history table
    (`link_recommendations`, migration #2, not yet run) — same treatment.
  - Robots.txt / true crawler-blocked detection needs a live fetch, which
    Agent 1 already does at crawl time; this agent reuses that result
    (`content_nodes.indexability_status`) rather than re-crawling.

Usage:
    python agents/agent_10_seo_validation.py --source <node_id> --target <node_id> \
        --anchor "India Electric Vehicle Market Outlook" --placement body_paragraph
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

# ── §18.3 anchor text rules ───────────────────────────────────────────────────

ANCHOR_AVOID_LIST = {
    "click here", "read more", "this report", "learn more", "best report",
    "market research report", "here", "more info", "find out more",
}

# ── §18.5 link-quantity ranges by page type ──────────────────────────────────
# (article split into short/long by internal_links_out isn't knowable without
# body word count, which Agent 1 doesn't capture — apply the "long article"
# band to all articles, the wider/safer range, and document the limitation.)

LINK_COUNT_RANGES = {
    "report": (10, 25),
    "article": (5, 15),      # short(5-8) + long(8-15) merged — see note above
    "case_study": (5, 12),
    "market_page": (10, 25),  # treated like report — same content shape
    "industry_page": (30, 999),
    "country_page": (20, 999),
}

# ── §18.7 faceted / non-indexable URL patterns ────────────────────────────────

FACETED_QUERY_KEYS = {
    "sort", "sort_by", "price", "price_min", "price_max", "page", "filter",
    "session", "sessionid", "sid", "q", "query", "search",
}
FACETED_PATH_HINTS = ("/search", "/filter", "/sort")

# master PRD 18.6 placement priority, PLUS the actual values Agent 6 / the
# contextual-placement script emit. The two vocabularies drifted apart:
# Agent 10 was written against the PRD's abstract names; Agent 6 emits its own
# concrete names for the same concepts. Both are accepted so a real
# recommendation is never flagged "unknown" just because the two agents used a
# different word for the same placement. body_paragraph and contextual_body
# are the same thing; likewise related_report_module / related_reports_block.
PLACEMENT_PRIORITY = [
    "body_paragraph", "contextual_body",
    "section_block", "hub_link",
    "related_report_module", "related_reports_block",
    "evidence_block", "toc_section", "sidebar", "footer",
]


@dataclass
class RiskFlag:
    rule: str
    description: str
    severity: str  # BLOCKER | HIGH | MEDIUM


@dataclass
class ValidationResult:
    source_url: str
    target_url: str
    anchor_text: str
    placement: str
    crawlability_status: str = "PASS"
    canonical_status: str = "PASS"
    indexability_status: str = "PASS"
    anchor_quality_score: float = 1.0
    link_count_status: str = "PASS"
    faceted_url_status: str = "PASS"
    risk_flags: list[RiskFlag] = field(default_factory=list)
    deferred_checks: list[str] = field(default_factory=list)
    overall_status: str = "approved_for_review"
    approval_required: bool = True  # master PRD §26 — always true, no auto-publish


class SEOValidationAgent:
    """Validates a single proposed (source, target, anchor, placement) link
    against master PRD §18 rules, using content_nodes as ground truth."""

    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_node(self, conn, node_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM content_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()

    def validate(self, source_node_id: str, target_node_id: str,
                anchor_text: str, placement: str = "body_paragraph",
                proposed_target_url: str | None = None) -> ValidationResult:
        conn = self._connect()
        try:
            source = self._get_node(conn, source_node_id)
            target = self._get_node(conn, target_node_id)
            if source is None or target is None:
                missing = "source" if source is None else "target"
                result = ValidationResult(
                    source_url=source["url"] if source else "",
                    target_url=target["url"] if target else "",
                    anchor_text=anchor_text, placement=placement,
                    overall_status="rejected", crawlability_status="FAIL",
                )
                result.risk_flags.append(RiskFlag(
                    "node_not_found", f"{missing} node_id does not exist", "BLOCKER"
                ))
                return result

            result = ValidationResult(
                source_url=source["url"], target_url=target["url"],
                anchor_text=anchor_text, placement=placement,
            )
            self._check_canonical(target, proposed_target_url, result)
            self._check_indexability(target, result)
            self._check_crawlability(target, result)
            self._check_faceted_url(target["url"], result)
            self._check_anchor_quality(anchor_text, result)
            self._check_placement(placement, result)
            self._check_link_count(source, result)
            self._check_self_link(source, target, result)

            result.deferred_checks = [
                "anchor_diversity (§18.4) — requires anchor_banks, built with Agent 7",
                "cannibalization_risk — requires link_recommendations history, "
                "built with the recommendation engine",
            ]
            self._decide(result)
            return result
        finally:
            conn.close()

    # ── individual rules ──────────────────────────────────────────────────

    @staticmethod
    def _check_canonical(target: sqlite3.Row, proposed_url: str | None,
                         result: ValidationResult) -> None:
        canonical = target["canonical_url"] or target["url"]
        check_url = proposed_url or target["url"]
        if check_url != canonical:
            result.canonical_status = "FAIL"
            result.risk_flags.append(RiskFlag(
                "non_canonical_target",
                f"Target URL '{check_url}' is not the canonical URL "
                f"('{canonical}')", "BLOCKER",
            ))

    @staticmethod
    def _check_indexability(target: sqlite3.Row, result: ValidationResult) -> None:
        status = (target["indexability_status"] or "").lower()
        if target["status"] == "removed" or status in (
            "noindex", "redirected_removed",
        ) or status.startswith("http_4") or status.startswith("http_5"):
            result.indexability_status = "FAIL"
            result.risk_flags.append(RiskFlag(
                "non_indexable_target",
                f"Target indexability_status is '{status}' "
                f"(page status: {target['status']})", "BLOCKER",
            ))

    @staticmethod
    def _check_crawlability(target: sqlite3.Row, result: ValidationResult) -> None:
        parts = urlsplit(target["url"])
        if parts.scheme not in ("http", "https") or not parts.netloc:
            result.crawlability_status = "FAIL"
            result.risk_flags.append(RiskFlag(
                "not_crawlable_href",
                f"Target URL is not a standard http(s) href: '{target['url']}'",
                "BLOCKER",
            ))
        path_lower = parts.path.lower()
        if any(hint in path_lower for hint in FACETED_PATH_HINTS):
            result.crawlability_status = "FAIL"
            result.risk_flags.append(RiskFlag(
                "internal_search_result_url",
                "Target looks like an internal search/filter result page",
                "HIGH",
            ))

    @staticmethod
    def _check_faceted_url(url: str, result: ValidationResult) -> None:
        query = parse_qs(urlsplit(url).query)
        bad_keys = FACETED_QUERY_KEYS & {k.lower() for k in query}
        if bad_keys:
            result.faceted_url_status = "FAIL"
            result.risk_flags.append(RiskFlag(
                "faceted_url_risk",
                f"Target URL has faceted/session query params: {sorted(bad_keys)}",
                "HIGH",
            ))

    @staticmethod
    def _check_anchor_quality(anchor_text: str, result: ValidationResult) -> None:
        text = (anchor_text or "").strip()
        lowered = text.lower()
        score = 1.0
        if not text:
            result.risk_flags.append(RiskFlag(
                "empty_anchor", "Anchor text is empty", "BLOCKER"
            ))
            score = 0.0
        elif lowered in ANCHOR_AVOID_LIST:
            result.risk_flags.append(RiskFlag(
                "generic_anchor_text",
                f"Anchor text '{text}' is on the avoid-list (§18.3)", "HIGH",
            ))
            score = 0.1
        elif len(text.split()) == 1 and not re.search(r"market|report|outlook", lowered):
            # single bare word, no market/report/outlook qualifier — likely a
            # generic country-only or one-word anchor (§18.3 "avoid generic
            # country-only anchors")
            result.risk_flags.append(RiskFlag(
                "generic_single_word_anchor",
                f"Anchor text '{text}' is a single generic word, not "
                "descriptive (§18.3 country+market / market+intent format)",
                "MEDIUM",
            ))
            score = 0.5
        elif len(text) > 100:
            result.risk_flags.append(RiskFlag(
                "anchor_too_long",
                f"Anchor text is {len(text)} characters — likely a full "
                "sentence, not an anchor", "MEDIUM",
            ))
            score = 0.6
        result.anchor_quality_score = score

    @staticmethod
    def _check_placement(placement: str, result: ValidationResult) -> None:
        if placement not in PLACEMENT_PRIORITY:
            result.risk_flags.append(RiskFlag(
                "unknown_placement_type",
                f"'{placement}' is not a recognized placement type", "MEDIUM",
            ))
        elif placement == "footer":
            result.risk_flags.append(RiskFlag(
                "footer_placement",
                "Footer links should not be the main linking strategy for "
                "report pages (§18.6)", "MEDIUM",
            ))

    @staticmethod
    def _check_link_count(source: sqlite3.Row, result: ValidationResult) -> None:
        content_type = source["content_type"] or "report"
        low, high = LINK_COUNT_RANGES.get(content_type, (5, 999))
        current = source["internal_links_out"] or 0
        if current + 1 > high:
            result.link_count_status = "FAIL"
            result.risk_flags.append(RiskFlag(
                "link_count_exceeded",
                f"Source page already has {current} outbound links; adding "
                f"one more exceeds the {content_type} range ({low}-{high})",
                "HIGH",
            ))

    @staticmethod
    def _check_self_link(source: sqlite3.Row, target: sqlite3.Row,
                         result: ValidationResult) -> None:
        if source["node_id"] == target["node_id"]:
            result.risk_flags.append(RiskFlag(
                "self_link", "Source and target are the same page", "BLOCKER"
            ))

    @staticmethod
    def _decide(result: ValidationResult) -> None:
        severities = {f.severity for f in result.risk_flags}
        if "BLOCKER" in severities:
            result.overall_status = "rejected"
        elif "HIGH" in severities:
            result.overall_status = "needs_revision"
        else:
            result.overall_status = "approved_for_review"
        # approval_required is always True — master PRD §26: no content-body
        # link change is ever auto-published in this build.


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--source", required=True, dest="source_node_id")
    parser.add_argument("--target", required=True, dest="target_node_id")
    parser.add_argument("--anchor", required=True, dest="anchor_text")
    parser.add_argument("--placement", default="body_paragraph")
    args = parser.parse_args(argv)

    agent = SEOValidationAgent(args.db)
    result = agent.validate(args.source_node_id, args.target_node_id,
                            args.anchor_text, args.placement)
    output = asdict(result)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if result.overall_status != "rejected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
