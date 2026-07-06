"""Live HTML enrichment for the Ken Research content inventory.

The complete crawl finishes before any database update. Successful results are
then written in one transaction. Incoming-link counts are scoped to the pages
in the current run; outgoing-link counts cover unique Ken Research URLs found
in each page's live HTML.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import os

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()
_NVIDIA_CLIENT = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY", ""),
)
_NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"
_INDUSTRIES_LIST = "\n".join([
    "Agriculture & Animal Care",
    "Automotive, Transportation & Logistics",
    "BFSI",
    "Consumer Products & Retail",
    "Defense & Security",
    "Education & Recruitment",
    "Energy & Utilities",
    "Food, Beverage & Tobacco",
    "Healthcare",
    "Metal, Mining and Chemicals",
    "Manufacturing & Construction",
    "Media & Entertainment",
    "Public Sector and Administration",
    "Technology & Telecom",
])


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
REPORT_DIR = ROOT / "reports"
LOG_DIR = ROOT / "logs"
KEN_HOSTS = {"kenresearch.com", "www.kenresearch.com"}
KNOWN_INDUSTRIES = {
    "agriculture & animal care",
    "automotive, transportation & logistics",
    "bfsi",
    "consumer products & retail",
    "defense & security",
    "education & recruitment",
    "energy & utilities",
    "food, beverage & tobacco",
    "healthcare",
    "metal, mining and chemicals",
    "manufacturing & construction",
    "media & entertainment",
    "public sector and administration",
    "technology & telecom",
}
USER_AGENT = (
    "Mozilla/5.0 (compatible; KenResearchContentInventory/1.0; "
    "+https://www.kenresearch.com/)"
)
# Template CTA/utility paths repeated on every report page — carry no market
# relationship signal, so they are excluded from internal_links_out.
UTILITY_PATH_PREFIXES = (
    "/custom-form",
    "/sample-report",
    "/talk-to-us",
    "/book-a-discovery-call",
    "/contact-us",
    "/about-us",
    "/careers",
    "/terms-and-conditions",
    "/privacy-policy",
)
# Generic hub pages a discontinued report redirects to. Such a hub is linked
# from every page's menu, so a page that lands here after a redirect must not
# inherit the hub's own sitewide incoming-link count as if it were its own.
HUB_REDIRECT_PATHS = {"/report-store", "/", ""}


@dataclass
class PageResult:
    """Everything Agent 1 learns about one URL from a single live crawl:
    metadata, classification, link counts, and any error encountered."""

    node_id: str
    requested_url: str
    final_url: str = ""
    canonical_url: str = ""
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    content_type: str = ""
    indexability_status: str = ""
    crawl_depth: int = 0
    internal_links_out: int = 0
    internal_links_in: int = 0
    orphan_status: str = ""
    industry: str = ""
    page_authority_score: float = 0.0
    status: str = "active"
    http_status: int | None = None
    elapsed_ms: float = 0.0
    error: str = ""
    outbound_urls: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """True if the crawl completed without error and got an HTTP response."""
        return not self.error and self.http_status is not None


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Normalize a URL for canonical comparison and graph matching."""
    raw = (url or "").strip()
    if not raw or raw.lower().startswith(
        ("#", "mailto:", "tel:", "javascript:", "data:")
    ):
        return ""
    absolute = urljoin(base_url, raw) if base_url else raw
    parts = urlsplit(absolute)
    if parts.scheme.lower() not in {"http", "https"}:
        return ""
    host = (parts.hostname or "").lower()
    if not host:
        return ""
    if host in KEN_HOSTS:
        host = "www.kenresearch.com"
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(("https", host, path, "", ""))


def calculate_crawl_depth(url: str) -> int:
    """Calculate structural path depth required by the Day 4 specification."""
    return len([part for part in urlsplit(url).path.split("/") if part])


def extract_industry_from_breadcrumb(soup: BeautifulSoup) -> str:
    """Read industry directly from page breadcrumb. Returns empty string if not found."""
    # Try JSON-LD structured data first (most reliable)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            # kenresearch uses @graph wrapper — flatten it
            if isinstance(data, dict) and "@graph" in data:
                candidates = data["@graph"]
            elif isinstance(data, list):
                candidates = data
            else:
                candidates = [data]
            for node in candidates:
                if not isinstance(node, dict):
                    continue
                if node.get("@type") == "BreadcrumbList":
                    items = node.get("itemListElement", [])
                    for item in items:
                        if item.get("position") == 2:
                            name = (item.get("name") or "").strip()
                            if name and name.lower() != "home":
                                return _match_industry(name) or name
        except Exception:
            pass
    # Try HTML breadcrumb elements
    breadcrumb = soup.find(attrs={"aria-label": lambda v: v and "breadcrumb" in v.lower()})
    if not breadcrumb:
        breadcrumb = soup.find(
            class_=lambda c: c and "breadcrumb" in (c if isinstance(c, str) else " ".join(c)).lower()
        )
    if breadcrumb:
        texts = [el.get_text(strip=True) for el in breadcrumb.find_all(["a", "span", "li"]) if el.get_text(strip=True)]
        # texts[0] = Home, texts[1] = industry, texts[2] = report title
        if len(texts) > 1 and texts[1].lower() != "home":
            return texts[1]
    return ""


_INDUSTRY_NORM = {
    ind.lower().replace(" & ", " and "): ind
    for ind in [
        "Agriculture & Animal Care",
        "Automotive, Transportation & Logistics",
        "BFSI",
        "Consumer Products & Retail",
        "Defense & Security",
        "Education & Recruitment",
        "Energy & Utilities",
        "Food, Beverage & Tobacco",
        "Healthcare",
        "Metal, Mining and Chemicals",
        "Manufacturing & Construction",
        "Media & Entertainment",
        "Public Sector and Administration",
        "Technology & Telecom",
    ]
}


def _match_industry(raw: str) -> str:
    """Map a raw tag or breadcrumb value to a standard industry name."""
    key = raw.lower().replace(" & ", " and ").strip()
    if key in _INDUSTRY_NORM:
        return _INDUSTRY_NORM[key]
    # Prefix match — handles "Automotive, Transportation and Warehousing" → our standard label
    for norm_key, label in _INDUSTRY_NORM.items():
        prefix = " ".join(norm_key.split()[:2])
        if len(prefix) > 5 and key.startswith(prefix):
            return label
    return ""


_AI_CLASSIFY_LOCK = __import__("threading").Lock()
_AI_LAST_CALL_TIME: list[float] = [0.0]
_AI_MIN_INTERVAL = 2.0  # seconds between API calls to avoid 429


def _classify_industry_with_ai(tags: list[str], title: str = "") -> str:
    """Use NVIDIA AI to map case study tags or title to the closest of 14 industries."""
    if not os.getenv("NVIDIA_API_KEY"):
        return ""
    if not tags and not title:
        return ""
    if tags:
        user_content = f"Tags from case study page: {', '.join(tags)}"
    else:
        user_content = f"Case study page title: {title}"
    user_content += "\n\nWhich ONE of the 14 industries does this belong to? Reply with ONLY the exact industry name."
    messages = [
        {
            "role": "system",
            "content": (
                "You are an industry classifier for Ken Research. "
                "Given tags or a title from a case study page, pick the single best matching industry. "
                "Reply with ONLY the exact industry name from the list below. Nothing else.\n\n"
                f"Industries:\n{_INDUSTRIES_LIST}"
            ),
        },
        {"role": "user", "content": user_content},
    ]
    for attempt in range(4):
        try:
            with _AI_CLASSIFY_LOCK:
                elapsed = time.time() - _AI_LAST_CALL_TIME[0]
                if elapsed < _AI_MIN_INTERVAL:
                    time.sleep(_AI_MIN_INTERVAL - elapsed)
                _AI_LAST_CALL_TIME[0] = time.time()
            response = _NVIDIA_CLIENT.chat.completions.create(
                model=_NVIDIA_MODEL,
                messages=messages,
                temperature=0.0,
                max_tokens=20,
            )
            answer = response.choices[0].message.content.strip()
            for industry in _INDUSTRIES_LIST.split("\n"):
                if industry.lower() == answer.lower():
                    return industry
            return ""  # Unknown answer → leave blank, never save garbage
        except Exception as exc:
            wait = 5 * (2 ** attempt)
            logging.warning("NVIDIA API attempt %d failed (%s) — retry in %ds", attempt + 1, exc, wait)
            time.sleep(wait)
    return ""


def extract_industry_from_related_tags(soup: BeautifulSoup, title: str = "") -> str:
    """Extract industry from Related tags section on case study pages.
    Falls back to AI classification using page title if tags are missing or ambiguous."""
    heading = next(
        (h for h in soup.find_all(["h2", "h3", "h4"])
         if "related tag" in h.get_text().lower()),
        None,
    )
    tags = []
    if heading:
        container = heading.find_next_sibling()
        if container:
            tags = [p.get_text(strip=True) for p in container.find_all("p") if p.get_text(strip=True)]
    # Try exact/prefix match first (free, instant)
    for tag in tags:
        matched = _match_industry(tag)
        if matched:
            return matched
    # AI: use tags if available, else fall back to title
    return _classify_industry_with_ai(tags, title=title)


def classify_content_type(
    url: str, existing_type: str = "", soup: BeautifulSoup | None = None
) -> str:
    """Classify using URL/template evidence, then trusted inventory fallback."""
    segments = [part for part in urlsplit(url).path.lower().split("/") if part]
    if any(part in {"case-study", "case-studies", "casestudy"} for part in segments):
        return "case_study"
    if any(part in {"article", "articles", "blog", "blogs"} for part in segments):
        return "article"
    if any(part in {"service", "services", "consulting"} for part in segments):
        return "service_page"
    existing = (existing_type or "").strip().lower()
    aliases = {"report_page": "report", "case-study": "case_study"}
    existing = aliases.get(existing, existing)
    allowed = {
        "report", "article", "market_page", "industry_page", "country_page",
        "case_study", "service_page",
    }
    # Existing sitemap/database provenance is stronger than generic page text.
    if existing in allowed:
        return existing
    if soup is not None:
        evidence = " ".join(
            node.get_text(" ", strip=True)
            for node in soup.select(
                "[aria-label*='breadcrumb' i], .breadcrumb, "
                "script[type='application/ld+json']"
            )
        ).lower()
        if "case study" in evidence:
            return "case_study"
        if "article" in evidence or "blog" in evidence:
            return "article"
        if "service" in evidence or "consulting" in evidence:
            return "service_page"
    return "report" if len(segments) == 1 else "market_page"


def determine_orphan_status(incoming_links: int) -> str:
    """Classify a page by incoming link count: 0 -> orphan, 1-2 -> under_linked,
    3-5 -> normal, 6+ -> well_linked."""
    if incoming_links <= 0:
        return "orphan"
    if incoming_links <= 2:
        return "under_linked"
    if incoming_links <= 5:
        return "normal"
    return "well_linked"


def calculate_authority_scores(results: list[PageResult]) -> None:
    """Calculate reproducible 0-100 scores: 80% incoming, 20% outgoing."""
    successful = [result for result in results if result.succeeded]
    max_in = max((result.internal_links_in for result in successful), default=0)
    max_out = max((result.internal_links_out for result in successful), default=0)
    for result in successful:
        incoming = (
            math.log1p(result.internal_links_in) / math.log1p(max_in)
            if max_in else 0.0
        )
        outgoing = (
            math.log1p(result.internal_links_out) / math.log1p(max_out)
            if max_out else 0.0
        )
        result.page_authority_score = round(
            min(100.0, incoming * 80.0 + outgoing * 20.0), 2
        )


class ContentInventoryAgent:
    """Crawls every URL in content_nodes and enriches it with title, H1,
    classification, canonical URL, link counts, orphan status, and authority
    score. See docs/ARCHITECTURE.md for the full pipeline this fits into."""

    def __init__(self, db_path=DEFAULT_DB, workers=20, timeout=12.0, logger=None):
        """db_path: sqlite file to read/write. workers: concurrent crawl
        threads (5 is the tested-safe value against Ken's rate limiting).
        timeout: per-request seconds."""
        self.db_path = Path(db_path)
        self.workers = max(1, workers)
        self.timeout = timeout
        self.logger = logger or logging.getLogger("content_inventory_agent")

    @staticmethod
    def _session() -> requests.Session:
        """Build a requests.Session with a browser User-Agent for crawling."""
        session = requests.Session()
        retry = Retry(
            total=2, connect=2, read=2, backoff_factor=0.35,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session

    def load_nodes(self, limit: int | None = None) -> list[dict[str, str]]:
        """Read node_id/url/content_type for every row in content_nodes
        (read-only connection), optionally capped at `limit` rows."""
        conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            sql = (
                "SELECT node_id,url,COALESCE(content_type,'') content_type "
                "FROM content_nodes ORDER BY rowid"
            )
            params = ()
            if limit is not None:
                sql += " LIMIT ?"
                params = (limit,)
            return [dict(row) for row in conn.execute(sql, params)]
        finally:
            conn.close()

    def process_url(self, node: dict[str, str]) -> PageResult:
        """Crawl one URL live and extract everything for its PageResult:
        title, H1, meta, canonical, content type, industry, hub-redirect
        detection, and outbound content links. Never raises — any failure is
        captured in result.error instead."""
        started = time.perf_counter()
        requested = normalize_url(node["url"])
        result = PageResult(node_id=node["node_id"], requested_url=requested)
        session = self._session()
        try:
            response = session.get(
                requested,
                timeout=(min(5.0, self.timeout), self.timeout),
                allow_redirects=True,
            )
            result.http_status = response.status_code
            result.final_url = normalize_url(response.url)
            header = response.headers.get("Content-Type", "").lower()
            if "html" not in header:
                raise ValueError(f"unexpected content type: {header or 'missing'}")
            soup = BeautifulSoup(response.content, "html.parser")
            result.content_type = classify_content_type(
                result.final_url or requested, node.get("content_type", ""), soup
            )
            result.crawl_depth = calculate_crawl_depth(result.final_url or requested)
            result.title = soup.title.get_text(" ", strip=True) if soup.title else ""
            description = soup.find(
                "meta", attrs={"name": lambda value: value and value.lower() == "description"}
            )
            if description is None:
                description = soup.find(
                    "meta", attrs={"property": lambda value: value and value.lower() == "og:description"}
                )
            result.meta_description = description.get("content", "").strip() if description else ""
            h1 = soup.find("h1")
            result.h1 = h1.get_text(" ", strip=True) if h1 else ""
            if result.content_type == "case_study":
                result.industry = extract_industry_from_related_tags(soup, title=result.h1 or result.title)
            else:
                result.industry = extract_industry_from_breadcrumb(soup)
            canonical = soup.find("link", rel=lambda value: value and "canonical" in str(value).lower())
            result.canonical_url = (
                normalize_url(canonical.get("href", ""), result.final_url)
                if canonical else ""
            ) or result.final_url or requested
            landed_path = urlsplit(result.final_url or requested).path.rstrip("/")
            requested_path = urlsplit(requested).path.rstrip("/")
            is_hub_redirect = landed_path in HUB_REDIRECT_PATHS and landed_path != requested_path
            if is_hub_redirect:
                # Report was discontinued and now redirects to a generic hub
                # page. Keep the alias scoped to this URL itself so it never
                # inherits the hub's own sitewide incoming-link count.
                result.status = "removed"
                result.canonical_url = requested
            robots = " ".join(
                tag.get("content", "").lower()
                for tag in soup.find_all(
                    "meta", attrs={"name": lambda value: value and value.lower() in {"robots", "googlebot"}}
                )
            )
            if is_hub_redirect:
                result.indexability_status = "redirected_removed"
            elif response.status_code >= 400:
                result.indexability_status = f"http_{response.status_code}"
            elif "noindex" in robots:
                result.indexability_status = "noindex"
            else:
                result.indexability_status = "indexable"
            # Count only editorial/content links: sitewide chrome (header menus,
            # nav bars, footers) repeats on every page and would inflate counts.
            for chrome in soup.find_all(["header", "nav", "footer"]):
                chrome.decompose()
            for chrome in soup.find_all(attrs={"role": "navigation"}):
                chrome.decompose()
            # Ken's header/footer are Tailwind divs, not semantic tags: the whole
            # menu block sits in a sticky container pinned to the viewport top.
            for chrome in soup.find_all(
                "div",
                class_=lambda classes: classes and "sticky" in classes and "top-0" in classes,
            ):
                chrome.decompose()
            outbound = {
                normalized
                for anchor in soup.find_all("a", href=True)
                if (normalized := normalize_url(anchor.get("href", ""), result.final_url))
                and (urlsplit(normalized).hostname or "").lower() in KEN_HOSTS
                and not urlsplit(normalized).path.startswith(UTILITY_PATH_PREFIXES)
            }
            outbound.discard(result.canonical_url)
            result.outbound_urls = tuple(sorted(outbound))
            result.internal_links_out = len(outbound)
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            self.logger.error("%s: %s", requested, result.error)
        finally:
            session.close()
            result.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return result

    def process_all_urls(self, limit=None, dry_run=False, incoming_snapshot=None):
        """Crawl every node concurrently, compute incoming links (scoped to
        this batch, or from a sitewide `incoming_snapshot` JSON file if
        given), calculate authority scores, and write results to the
        database unless dry_run is True. Returns (results, summary dict)."""
        nodes = self.load_nodes(limit)
        total = len(nodes)
        if not total:
            raise RuntimeError("No content_nodes found")
        print("Starting Content Inventory Agent")
        print(f"Processing {total} URLs with {self.workers} workers...")
        started = time.perf_counter()
        results = []
        progress_step = max(1, total // 5)
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(self.process_url, node) for node in nodes]
            for completed, future in enumerate(as_completed(futures), 1):
                results.append(future.result())
                if completed % progress_step == 0 or completed == total:
                    print(f"Processed {completed}/{total} URLs ({completed * 100 // total}%)")
        results.sort(key=lambda result: result.requested_url)

        aliases = {}
        for result in results:
            if result.succeeded:
                for alias in {result.requested_url, result.final_url, result.canonical_url}:
                    if alias:
                        aliases[alias] = result.node_id
        incoming = {result.node_id: set() for result in results}
        for source in results:
            if source.succeeded:
                for target_url in source.outbound_urls:
                    target_id = aliases.get(target_url)
                    if target_id and target_id != source.node_id:
                        incoming[target_id].add(source.node_id)
        for result in results:
            if result.succeeded:
                result.internal_links_in = len(incoming[result.node_id])
                result.orphan_status = determine_orphan_status(result.internal_links_in)
        if incoming_snapshot:
            snapshot = json.loads(Path(incoming_snapshot).read_text(encoding="utf-8"))
            counts = snapshot.get("incoming_counts", {})
            for result in results:
                if result.succeeded:
                    aliases_for_page = {
                        result.requested_url, result.final_url, result.canonical_url
                    }
                    result.internal_links_in = max(
                        (int(counts.get(alias, 0)) for alias in aliases_for_page if alias),
                        default=0,
                    )
                    result.orphan_status = determine_orphan_status(result.internal_links_in)
        calculate_authority_scores(results)
        for result in results:
            if result.status == "removed":
                # Discontinued page redirecting to a generic hub: no real
                # link signal of its own, regardless of what the snapshot
                # or authority formula computed from its (self) alias.
                result.internal_links_in = 0
                result.orphan_status = "removed"
                result.page_authority_score = 0.0
        elapsed = round(time.perf_counter() - started, 2)
        summary = self._summary(results, elapsed, dry_run)
        if incoming_snapshot:
            summary["incoming_snapshot"] = str(incoming_snapshot)
            summary["incoming_source_coverage"] = {
                key: snapshot.get(key)
                for key in ("sources_total", "sources_successful", "sources_failed", "coverage_percent")
            }
            summary["methodology"]["incoming_links"] = (
                "unique source pages across official Ken Research sitemaps"
            )
        if not dry_run:
            self.update_database(results)
        return results, summary

    def update_database(self, results: list[PageResult]) -> None:
        """Write all successful results to content_nodes in a single
        transaction, and log each one in crawl_logs. Raises if there are no
        successful results at all — never leaves the database half-written."""
        successful = [result for result in results if result.succeeded]
        if not successful:
            raise RuntimeError("No successful results; database not updated")
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            timestamp = datetime.now(timezone.utc).isoformat()
            for result in successful:
                conn.execute(
                    """UPDATE content_nodes SET
                    canonical_url=?, title=COALESCE(NULLIF(?,''),title),
                    meta_title=?, meta_description=?, h1=?, content_type=?,
                    industry=CASE WHEN ? != '' THEN ? ELSE industry END,
                    indexability_status=?, crawl_depth=?, internal_links_in=?,
                    internal_links_out=?, orphan_status=?, page_authority_score=?,
                    status=?, updated_at=? WHERE node_id=?""",
                    (result.canonical_url, result.title, result.title,
                     result.meta_description, result.h1, result.content_type,
                     result.industry, result.industry,
                     result.indexability_status, result.crawl_depth,
                     result.internal_links_in, result.internal_links_out,
                     result.orphan_status, result.page_authority_score,
                     result.status, timestamp, result.node_id),
                )
                conn.execute(
                    """INSERT INTO crawl_logs
                    (url,node_id,operation,status,http_status,crawl_depth,error,notes,crawled_at)
                    VALUES (?,?, 'inventory_enrichment', 'success', ?, ?, NULL, ?, ?)""",
                    (result.requested_url, result.node_id, result.http_status,
                     result.crawl_depth,
                     "Agent 1 live HTML evidence; incoming links scoped to run",
                     timestamp),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def apply_cached_report(self, report_path, incoming_snapshot=None):
        """Apply previously collected page evidence without another live crawl."""
        started = time.perf_counter()
        payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
        allowed = set(PageResult.__dataclass_fields__)
        results = [
            PageResult(**{key: value for key, value in page.items() if key in allowed})
            for page in payload.get("pages", [])
        ]
        if len(results) != 500:
            raise RuntimeError(f"Cached report must contain 500 pages, found {len(results)}")
        snapshot = None
        if incoming_snapshot:
            snapshot = json.loads(Path(incoming_snapshot).read_text(encoding="utf-8"))
            counts = snapshot.get("incoming_counts", {})
            for result in results:
                aliases = {result.requested_url, result.final_url, result.canonical_url}
                result.internal_links_in = max(
                    (int(counts.get(alias, 0)) for alias in aliases if alias), default=0
                )
                result.orphan_status = determine_orphan_status(result.internal_links_in)
            calculate_authority_scores(results)
        summary = self._summary(
            results, round(time.perf_counter() - started, 3), False
        )
        summary["page_evidence_source"] = str(report_path)
        if snapshot:
            summary["incoming_snapshot"] = str(incoming_snapshot)
            summary["incoming_source_coverage"] = {
                key: snapshot.get(key)
                for key in ("sources_total", "sources_successful", "sources_failed", "coverage_percent")
            }
            summary["methodology"]["incoming_links"] = (
                "unique source pages across official Ken Research sitemaps"
            )
        self.update_database(results)
        return results, summary

    @staticmethod
    def _summary(results, elapsed, dry_run):
        """Build the run summary dict: counts by success/type/link-status,
        averages, failed URLs with their errors, and the methodology notes
        written into every report."""
        successful = [result for result in results if result.succeeded]
        failed = [result for result in results if not result.succeeded]
        types, statuses = {}, {}
        for result in successful:
            types[result.content_type] = types.get(result.content_type, 0) + 1
            statuses[result.orphan_status] = statuses.get(result.orphan_status, 0) + 1
        average = lambda field: round(sum(getattr(r, field) for r in successful) / len(successful), 2) if successful else 0
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "total_attempted": len(results), "successful": len(successful),
            "failed": len(failed), "elapsed_seconds": elapsed,
            "content_types": types, "link_statuses": statuses,
            "average_internal_links_in": average("internal_links_in"),
            "average_internal_links_out": average("internal_links_out"),
            "failed_urls": [{"url": r.requested_url, "error": r.error} for r in failed],
            "methodology": {
                "content_type": "URL and live template evidence with inventory fallback",
                "crawl_depth": "structural URL path depth",
                "incoming_links": "unique source pages within crawled run",
                "outgoing_links": "unique Ken Research URLs in live HTML",
                "authority_score": "80% normalized incoming + 20% normalized outgoing",
            },
        }


def configure_logging():
    """Set up a file logger at logs/content_inventory_agent.log and return it."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("content_inventory_agent")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_DIR / "content_inventory_agent.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def write_report(results, summary, output: Path):
    """Write the full run (summary + every page's result, minus the raw
    outbound_urls list) to a JSON file at `output`."""
    output.parent.mkdir(parents=True, exist_ok=True)
    pages = []
    for result in results:
        row = asdict(result)
        row.pop("outbound_urls", None)
        pages.append(row)
    output.write_text(
        json.dumps({"summary": summary, "pages": pages}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_args(argv=None):
    """Parse CLI arguments for the agent (--limit, --dry-run, --workers,
    --timeout, --db, --report, --incoming-snapshot, --apply-report)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--report")
    parser.add_argument("--incoming-snapshot")
    parser.add_argument(
        "--apply-report",
        help="Apply a verified 500-page evidence report without re-fetching pages",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """CLI entry point: run the agent (or apply a cached report), print a
    summary to stdout, and write the full JSON report to disk."""
    args = parse_args(argv)
    agent = ContentInventoryAgent(args.db, args.workers, args.timeout, configure_logging())
    report = Path(args.report) if args.report else REPORT_DIR / f"content_inventory_{datetime.now():%Y%m%d_%H%M%S}.json"
    try:
        if args.apply_report:
            if args.dry_run or args.limit:
                raise ValueError("--apply-report cannot be combined with --dry-run or --limit")
            results, summary = agent.apply_cached_report(
                args.apply_report, args.incoming_snapshot
            )
        else:
            results, summary = agent.process_all_urls(
                args.limit, args.dry_run, args.incoming_snapshot
            )
        write_report(results, summary, report)
    except Exception as exc:
        logging.getLogger("content_inventory_agent").exception("Agent failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Completed in {summary['elapsed_seconds']} seconds")
    print(f"Successful: {summary['successful']}/{summary['total_attempted']}")
    print(f"Failed: {summary['failed']}")
    print(f"Link statuses: {summary['link_statuses']}")
    print(f"Report: {report}")
    print("Database update: skipped" if args.dry_run else "Database update: committed")
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
