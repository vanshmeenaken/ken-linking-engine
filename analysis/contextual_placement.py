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


def _clean(text: str) -> str:
    """Normalise smart punctuation and drop stray replacement chars so stored
    sentences are clean ASCII-ish rather than mojibake."""
    repl = {"’": "'", "‘": "'", "“": '"', "”": '"',
            "–": "-", "—": "-", "…": "...", "�": "",
            " ": " "}
    for a, b in repl.items():
        text = text.replace(a, b)
    return text.strip()


def fetch_paragraphs(url: str, timeout: int = 20) -> list[str]:
    """Return the meaningful body paragraphs of a page (chrome stripped)."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding  # avoid mojibake
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "form"]):
        tag.decompose()
    paras = [_clean(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
    return [p for p in paras if len(p) > 60]


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


def target_keywords(market: str, country: str, region: str, title: str) -> set[str]:
    """The distinctive SUBJECT tokens that identify a target page.

    Built from the market and title (the subject), with geography removed. A
    paragraph must share the actual subject (e.g. "cold storage", "car rental")
    to be a genuine contextual home; sharing only a region does not qualify.
    `country`/`region` are accepted for signature stability but not used here.
    """
    return _tokens(" ".join(filter(None, [market, title]))) - GEO_WORDS


def _split_sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", paragraph)
    return [s.strip() for s in parts if len(s.strip()) > 30]


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
