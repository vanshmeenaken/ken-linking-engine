"""Ken Research sitemap index: fetch, cache, and find related pages.

The local inventory holds 500 pages; the live site has thousands. When the
manual workbench is given a report URL and the inventory has no good related
pages for it, this module supplies candidates from the public sitemap so the
answer is never "nothing found" merely because a page is outside the sample.

Cached into sitemap_urls (scripts/37 migration) - the index plus its child
sitemaps are ~4,700 relevant URLs and fetch in about a second each, but
re-fetching on every request would be rude to the site and slow for the
user. refresh_sitemap_cache() is the only network path.

Relevance uses the SAME subject gate as the automated pipeline
(analysis/subject_similarity.market_technology_relevance), so a manually
suggested candidate is held to the standard as an automated one: shared
market subject, compatible technology, geography noted but never sufficient
on its own.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests

from analysis.subject_similarity import market_technology_relevance
from analysis.tfidf_similarity import build_corpus
from config.taxonomy import COUNTRY_TO_REGION, REGIONS

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "ken_links.db"

SITEMAP_INDEX = "https://www.kenresearch.com/sitemap.xml"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Child sitemaps worth indexing, mapped to the content type they hold. The
# others in the index (home, staticpage, brandcomparison, ...) are not link
# targets for market interlinking.
SITEMAP_CONTENT_TYPES = {
    "product-sitemap.xml": "report",
    "article-sitemap.xml": "article",
    "casestudy-sitemap.xml": "case_study",
    "survey-sitemap.xml": "survey",
    "pov-sitemap.xml": "pov",
    "blog-sitemap.xml": "blog",
}

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)
_URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.I | re.S)
_LASTMOD_RE = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.I | re.S)


def slug_of(url: str) -> str:
    """The last meaningful path segment of a URL, hyphens intact."""
    return (url or "").rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


def slug_to_text(slug: str) -> str:
    """A slug as readable words, for subject comparison."""
    return re.sub(r"[-_]+", " ", slug or "").strip()


def _fetch(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_sitemap_entries() -> list[dict]:
    """Every indexed URL from the child sitemaps we care about.
    Network path; returns [{url, slug, content_type, sitemap_source, lastmod}]."""
    index_xml = _fetch(SITEMAP_INDEX)
    children = _LOC_RE.findall(index_xml)
    entries: list[dict] = []
    for child in children:
        name = child.rstrip("/").split("/")[-1]
        content_type = SITEMAP_CONTENT_TYPES.get(name)
        if not content_type:
            continue
        try:
            xml = _fetch(child)
        except Exception:
            continue  # one bad child sitemap must not lose the others
        for block in _URL_BLOCK_RE.findall(xml) or []:
            loc = _LOC_RE.search(block)
            if not loc:
                continue
            url = loc.group(1)
            lastmod = _LASTMOD_RE.search(block)
            entries.append({
                "url": url, "slug": slug_of(url), "content_type": content_type,
                "sitemap_source": name,
                "lastmod": lastmod.group(1) if lastmod else None,
            })
        if not _URL_BLOCK_RE.search(xml):
            # some sitemaps list bare <loc> without <url> wrappers
            for url in _LOC_RE.findall(xml):
                entries.append({
                    "url": url, "slug": slug_of(url),
                    "content_type": content_type,
                    "sitemap_source": name, "lastmod": None})
    return entries


def refresh_sitemap_cache(db_path: Path = DEFAULT_DB) -> int:
    """Fetch the sitemap and upsert into sitemap_urls. Returns rows written."""
    entries = fetch_sitemap_entries()
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            """INSERT INTO sitemap_urls
               (url, slug, content_type, sitemap_source, lastmod, fetched_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET
                   slug=excluded.slug, content_type=excluded.content_type,
                   sitemap_source=excluded.sitemap_source,
                   lastmod=excluded.lastmod, fetched_at=excluded.fetched_at""",
            [(e["url"], e["slug"], e["content_type"], e["sitemap_source"],
              e["lastmod"], now) for e in entries])
        conn.commit()
    finally:
        conn.close()
    return len(entries)


def cache_status(db_path: Path = DEFAULT_DB) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM sitemap_urls").fetchone()[0]
        by_type = dict(conn.execute(
            "SELECT content_type, COUNT(*) FROM sitemap_urls "
            "GROUP BY content_type").fetchall())
        last = conn.execute(
            "SELECT MAX(fetched_at) FROM sitemap_urls").fetchone()[0]
    finally:
        conn.close()
    return {"total": total, "by_content_type": by_type, "last_fetched": last}


def geography_of(text: str) -> tuple[str | None, str | None]:
    """(country, region) guessed from slug words, or (None, None)."""
    words = slug_to_text(text).lower()
    country = next((c for c in COUNTRY_TO_REGION if c.lower() in words), None)
    region = COUNTRY_TO_REGION.get(country) if country else next(
        (r for r in REGIONS if r.lower() in words), None)
    return country, region


def classify_relation(source_text: str, candidate_text: str) -> str:
    """A plain label for how two pages relate, by subject and geography:
    regional (same subject, different place), adjacent (related subject),
    or adjacent_regional (related subject AND different place)."""
    s_country, s_region = geography_of(source_text)
    c_country, c_region = geography_of(candidate_text)
    different_place = bool(s_country and c_country and s_country != c_country)
    s_subject = re.sub(r"\b(" + "|".join(
        re.escape(c) for c in COUNTRY_TO_REGION) + r")\b", "",
        slug_to_text(source_text), flags=re.I).strip()
    c_subject = re.sub(r"\b(" + "|".join(
        re.escape(c) for c in COUNTRY_TO_REGION) + r")\b", "",
        slug_to_text(candidate_text), flags=re.I).strip()
    same_subject = s_subject.lower() == c_subject.lower()
    if same_subject and different_place:
        return "regional"
    if different_place:
        return "adjacent_regional"
    return "adjacent"


def find_related_in_sitemap(source_url: str, limit: int = 25,
                            db_path: Path = DEFAULT_DB) -> list[dict]:
    """Candidate related pages for `source_url` from the cached sitemap.

    Held to the same subject gate as the automated pipeline, so a candidate
    that only shares a geography (or only a generic word) is not returned.
    """
    source_slug = slug_of(source_url)
    source_text = slug_to_text(source_slug)
    if not source_text:
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT url, slug, content_type FROM sitemap_urls "
            "WHERE slug != ?", (source_slug,)).fetchall()
    finally:
        conn.close()
    if not rows:
        return []
    texts = [slug_to_text(r["slug"]) for r in rows]
    corpus = build_corpus([source_text] + texts)
    out = []
    for row, text in zip(rows, texts):
        rel = market_technology_relevance(corpus, source_text, text)
        if not rel.accepted:
            continue
        out.append({
            "url": row["url"], "content_type": row["content_type"],
            "title_guess": slug_to_text(row["slug"]).title(),
            "market_match_score": rel.market_score,
            "technology_match_score": rel.technology_score,
            "combined_score": rel.combined_score,
            "relation_label": classify_relation(source_text, text),
            "found_via": "sitemap",
            "reason": rel.reason,
        })
    out.sort(key=lambda c: -c["combined_score"])
    return out[:limit]
