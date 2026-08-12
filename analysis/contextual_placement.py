"""Contextual link placement: find the real sentence in a source page's body
where a recommended link genuinely belongs.

For AI search / GEO, a link embedded in a relevant sentence teaches the engine
how two topics relate, which a footer "related" box does not. This module
reads a source page's actual paragraphs and, for a given target, finds the
paragraph and sentence most topically relevant to that target.

Deterministic and explainable: relevance is token overlap between the source
paragraph and the target's identity (its market, country, region, title
words), minus generic filler. If no paragraph clears the threshold, the caller
should route the link to an end-of-page related block rather than force it into
an unrelated sentence (the project quality bar: never pad).
"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from analysis.vector_store import VectorStore

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Words too generic to signal genuine topical relevance.
STOP = {
    "the", "and", "of", "in", "to", "for", "a", "an", "is", "are", "with",
    "market", "report", "size", "share", "growth", "trends", "forecast",
    "analysis", "outlook", "industry", "by", "on", "as", "at", "from", "this",
    "that", "various", "including", "such", "other", "its", "their", "which",
}

# Minimum overlap score for a paragraph to count as a genuine contextual home.
CONTEXTUAL_THRESHOLD = 2

# Ken's report pages end with a standard "why work with us" company-pitch
# block (consultant methodology, "syndicated and customized", "if you need
# any support"). It is never genuine market content, but its promotional
# language ("insights", "market research", "growth") overlaps with target
# TITLES enough to occasionally outscore the real content paragraphs in a
# small per-page TF-IDF fit (found via manual review: a Brazil pharma page's
# boilerplate outscored its own Brazil-pharma content paragraph for a
# pharma-market target). Filtered out before ranking, not after - it should
# never be a placement candidate regardless of ranking method.
BOILERPLATE_MARKERS = (
    "what makes us stand out", "we have set a benchmark",
    "syndicated and customized", "our consultants follows",
    "we pride ourselves", "if you need any support",
    "our research team constantly", "while we don't replace",
    "instant access to the answers", "with one step in the future",
)


def is_boilerplate(paragraph: str) -> bool:
    p = (paragraph or "").lower()
    return any(marker in p for marker in BOILERPLATE_MARKERS)


# Report pages render their Table of Contents as <p> tags, e.g.
# "5.3 Indonesia Online Grocery Market Segmentation By Mode of Payment,
# 2021P and 2026F" or "9.1.1 Cross Comparison Matrix of Major Players (...)".
# These are heading LABELS, not prose - found via manual review of the
# highest-scoring "contextual" placements: a TOC line's heading literally
# repeats the target's market name, so it vector-matches well despite being
# unusable as a sentence to embed a link in. Matches "N", "N.N", or "N.N.N"
# followed by whitespace at the very start of the paragraph. "5.3% growth..."
# is not matched (no whitespace immediately after the digits), so genuine
# sentences that happen to start with a number/percentage are unaffected.
_TOC_HEADING_RE = re.compile(r"^\d+(\.\d+){0,3}\s")


def is_toc_or_heading(paragraph: str) -> bool:
    return bool(_TOC_HEADING_RE.match((paragraph or "").strip()))


def _clean(text: str) -> str:
    """Normalise smart punctuation and drop stray replacement chars so stored
    sentences are clean ASCII-ish rather than mojibake."""
    repl = {"’": "'", "‘": "'", "“": '"', "”": '"',
            "–": "-", "—": "-", "…": "...", "�": "",
            " ": " "}
    for a, b in repl.items():
        text = text.replace(a, b)
    return text.strip()


def _is_internal_href(href: str) -> bool:
    href = (href or "").strip().lower()
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return False
    return "kenresearch.com" in href or href.startswith("/")


def fetch_sections(url: str, timeout: int = 20) -> list[dict]:
    """Return the page's real section structure, in document order.

    Each section: {"heading": str | None, "order": int, "paragraphs": [str],
    "internal_link_count": int}. A section starts at each <h2> (<h3> when a
    page has no <h2> at all); paragraphs before the first heading form a
    heading-less intro section. Paragraph filtering matches fetch_paragraphs
    (length, boilerplate, TOC-line rules), but internal links are counted on
    EVERY <p> in the section, filtered or not, because a link list of short
    lines is still evidence the section already links somewhere.

    The crawler reports the page as it is - chapter banner headings
    ("CHAPTER 4 - Market Size & Growth") and empty sections are kept, and
    interpreting them is Agent 9's job, not the crawler's.
    """
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding  # avoid mojibake
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "form"]):
        tag.decompose()
    level = "h2" if soup.find("h2") else "h3"
    sections = [{"heading": None, "order": 0, "paragraphs": [],
                 "internal_link_count": 0}]
    # walk <a> directly (not via <p>) so links in list items and divs are
    # counted too - several report templates render related-report links as
    # <li>, which a p-only walk would miss entirely
    for el in soup.find_all([level, "p", "a"]):
        sec = sections[-1]
        if el.name == level:
            heading = _clean(el.get_text(" ", strip=True))
            if heading:
                sections.append({"heading": heading, "order": len(sections),
                                 "paragraphs": [], "internal_link_count": 0})
            continue
        if el.name == "a":
            if el.has_attr("href") and _is_internal_href(el["href"]):
                sec["internal_link_count"] += 1
            continue
        text = _clean(el.get_text(" ", strip=True))
        if len(text) > 60 and not is_boilerplate(text) and not is_toc_or_heading(text):
            sec["paragraphs"].append(text)
    if not sections[0]["paragraphs"] and not sections[0]["internal_link_count"]:
        sections = sections[1:]
        for i, s in enumerate(sections):
            s["order"] = i
    return sections


def fetch_paragraphs(url: str, timeout: int = 20) -> list[str]:
    """Return the meaningful body paragraphs of a page (chrome stripped)."""
    return [p for s in fetch_sections(url, timeout) for p in s["paragraphs"]]


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if w not in STOP and len(w) > 2}


# Geography tokens must never, on their own, justify a contextual placement:
# "both mention the Middle East" is not a topical link. Kept out of the match
# set so only SUBJECT overlap (the market itself) can place a link in the body.
GEO_WORDS = {
    "global", "apac", "asia", "pacific", "middle", "east", "africa", "europe",
    "america", "latin", "north", "south", "gcc", "mena", "asean", "eu",
    "india", "china", "japan", "korea", "vietnam", "indonesia", "thailand",
    "malaysia", "singapore", "philippines", "uae", "ksa", "saudi", "arabia",
    "qatar", "kuwait", "bahrain", "oman", "turkey", "brazil", "mexico",
    "nigeria", "kenya", "egypt", "russia", "germany", "france", "italy",
    "spain", "usa", "uk", "canada", "australia",
}


def subject_text(market: str, title: str) -> str:
    """The geography-stripped subject phrase for a target, e.g. "Cold Storage
    Market UAE Cold Storage Market" -> "Cold Storage Market Cold Storage
    Market". Used as the vector-search query so a match can only come from
    shared SUBJECT, never from sharing a region alone."""
    words = re.findall(r"[a-zA-Z0-9]+", " ".join(filter(None, [market, title])))
    return " ".join(w for w in words if w.lower() not in GEO_WORDS)


def target_keywords(market: str, country: str, region: str, title: str) -> set[str]:
    """The distinctive SUBJECT tokens that identify a target page.

    Built from the market and title (the subject), with geography removed. A
    paragraph must share the actual subject (e.g. "cold storage", "car rental")
    to be a genuine contextual home; sharing only a region does not qualify.
    `country`/`region` are accepted for signature stability but not used here.
    """
    return _tokens(subject_text(market, title))


def _split_sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", paragraph)
    return [s.strip() for s in parts if len(s.strip()) > 30]


def best_placement_semantic(paragraphs: list[str], query_text: str,
                            min_score: float = 0.12) -> dict | None:
    """Vector-search based placement: rank a page's paragraphs by cosine
    similarity to the target's subject text (geography-stripped, so a match
    can only come from shared subject) and return the closest one.

    This is the "vector search foundation" applied to contextual placement:
    a small VectorStore is built over just this page's paragraphs (a handful
    of items, so brute-force cosine is instant) and searched with the query.
    The interface is identical to the whole-catalogue case in
    analysis/vector_store.py; only the item count differs.

    Returns {paragraph_index, sentence, score, method:'vector'}, or None if
    nothing clears min_score (the caller should then try the stricter keyword
    method, and failing that, route the link to the related-block).
    """
    if not paragraphs or not query_text.strip():
        return None
    store = VectorStore.fit([(str(i), p) for i, p in enumerate(paragraphs)])
    results = store.search(query_text, top_k=1)
    if not results or results[0].score < min_score:
        return None
    idx = int(results[0].item_id)
    para = paragraphs[idx]
    sentences = _split_sentences(para) or [para]
    q_tokens = _tokens(query_text)
    sentence = max(sentences, key=lambda s: len(_tokens(s) & q_tokens))
    return {"paragraph_index": idx, "sentence": sentence[:300],
            "score": round(results[0].score, 4), "method": "vector"}


def best_placement(paragraphs: list[str], keywords: set[str]) -> dict | None:
    """Find the paragraph/sentence most relevant to `keywords`.

    Returns {paragraph_index, sentence, score} for the best match at or above
    the threshold, or None when nothing is genuinely relevant (route to the
    related block instead).
    """
    best = None
    for i, para in enumerate(paragraphs):
        overlap = _tokens(para) & keywords
        score = len(overlap)
        if score < CONTEXTUAL_THRESHOLD:
            continue
        # within the winning paragraph, pick the sentence that carries the
        # most target keywords (the natural spot for the link)
        sentences = _split_sentences(para) or [para]
        sentence = max(sentences, key=lambda s: len(_tokens(s) & keywords))
        if best is None or score > best["score"]:
            best = {"paragraph_index": i, "sentence": sentence[:300],
                    "score": score, "matched": sorted(overlap)}
    return best
