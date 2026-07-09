"""TF-IDF semantic similarity engine (Phase 2, Day 2 — the plan's MVP method).

Stdlib only — no scikit-learn / numpy dependency. Deterministic and
reproducible: the same corpus always yields the same vectors and scores, so
similarity is explainable (you can point at the shared terms driving a score).

A page's "document" is built from its title + H1 + meta description + the
names of its extracted entities (markets, industries, regions). TF-IDF
naturally downweights boilerplate that appears on nearly every page
("market", "report", "forecast" → high document frequency → ~0 IDF), so the
score is driven by the distinctive subject words.

Public API:
    build_corpus(documents)      -> Corpus            (fit IDF over all pages)
    Corpus.vector(text)          -> dict[str, float]  (unit-normalized TF-IDF)
    cosine(vec_a, vec_b)         -> float 0.0-1.0
    Corpus.similarity(a, b)      -> float 0.0-1.0
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

# Minimal English stopwords + a few domain boilerplate words. TF-IDF already
# neutralizes ubiquitous terms via IDF; this just trims obvious noise so the
# stored vectors stay small.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "by", "with",
    "at", "from", "as", "is", "are", "be", "this", "that", "its", "it", "into",
    "amp", "vs", "via", "per", "ken", "research",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and length-1 tokens."""
    if not text:
        return []
    return [
        tok for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) > 1 and tok not in _STOPWORDS
    ]


@dataclass
class Corpus:
    """Fitted IDF weights over a document collection."""

    idf: dict[str, float]
    n_docs: int

    def vector(self, text: str) -> dict[str, float]:
        """Unit-normalized sparse TF-IDF vector for a piece of text.
        Terms unseen in the corpus (idf missing) are ignored."""
        counts = Counter(tokenize(text))
        if not counts:
            return {}
        total = sum(counts.values())
        vec = {
            term: (count / total) * self.idf[term]
            for term, count in counts.items()
            if term in self.idf
        }
        norm = math.sqrt(sum(w * w for w in vec.values()))
        if norm == 0:
            return {}
        return {term: w / norm for term, w in vec.items()}

    def similarity(self, text_a: str, text_b: str) -> float:
        return cosine(self.vector(text_a), self.vector(text_b))


def build_corpus(documents: list[str]) -> Corpus:
    """Fit IDF over the document collection.

    idf(term) = ln((N + 1) / (df + 1)) + 1   (smoothed, always positive)
    """
    n_docs = len(documents)
    doc_freq: Counter[str] = Counter()
    for doc in documents:
        for term in set(tokenize(doc)):
            doc_freq[term] += 1
    idf = {
        term: math.log((n_docs + 1) / (df + 1)) + 1.0
        for term, df in doc_freq.items()
    }
    return Corpus(idf=idf, n_docs=n_docs)


def cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity of two unit-normalized sparse vectors (0.0-1.0).
    Iterates the smaller vector for speed."""
    if not vec_a or not vec_b:
        return 0.0
    if len(vec_b) < len(vec_a):
        vec_a, vec_b = vec_b, vec_a
    dot = sum(w * vec_b.get(term, 0.0) for term, w in vec_a.items())
    # Both inputs are unit vectors, so cosine == dot product. Clamp for safety.
    return max(0.0, min(1.0, dot))
