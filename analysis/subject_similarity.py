"""Subject-aware similarity engine — Shrey's proven 4-layer adjacency method
(validated at zero-wrong-URLs on the earlier kr-interlink project),
re-implemented here for Agent 3's adjacent_market / country_region edges.

The core problem plain TF-IDF cannot solve on its own: two reports can share
a generic function/tech word ("Healthcare", "3PL", "AI") while being about
completely unrelated subjects (Bone Growth Stimulator vs Microscope — both
just "Healthcare"; automotive 3PL vs pharma 3PL — both just "3PL"). Fixing
this needs to know WHICH words in a title carry the actual subject and which
are generic scaffolding — that's a judgment TF-IDF's corpus-frequency
weighting alone doesn't reliably make (a term can be generic in meaning
while still being statistically rare in a 500-page corpus).

Layer 1 (domain-first classification) is already satisfied by Ken's own
site-assigned industry field (breadcrumb-sourced, 0.95 confidence) — that IS
the domain classification; no rebuild needed there.

Layer 2 — subject-weighting: generic/function/tech words are downweighted
    (~0.15x) relative to their normal TF-IDF weight; specific subject nouns
    keep full weight. Fixes: "automotive 3PL" matching "pharma 3PL" on the
    shared generic word alone.

Layer 3 — tech-intersection: for a compound "[tech qualifier] + [domain]"
    topic ("AI in Medicine"), a candidate match must share BOTH halves, not
    just one. Fixes: "AI in Medicine" wrongly matching "AI in Robotics"
    (tech matches, domain doesn't) or "Herbal Medicine" (domain matches,
    tech doesn't).

Layer 4 (LLM final judge) lives in analysis/llm_subject_judge.py — kept
separate since it's optional/credential-gated, not always available.
"""

from __future__ import annotations

import re

from analysis.tfidf_similarity import Corpus, cosine, tokenize

# ── Layer 2: generic/function/tech words to downweight ───────────────────────
# Curated, not corpus-derived — a word can be generic in MEANING while still
# being statistically rare across only 500 titles (TF-IDF's IDF wouldn't
# catch "aftermarket" or "3pl" as generic on rarity alone). This list is the
# direct encoding of Shrey's Layer 2 rule.
GENERIC_TERMS = {
    # market-research boilerplate
    "market", "markets", "industry", "size", "share", "forecast", "forecasts",
    "outlook", "trends", "trend", "growth", "analysis", "report", "reports",
    "insights", "overview", "opportunities", "opportunity", "drivers", "driver",
    "challenges", "challenge", "companies", "company", "players", "player",
    "landscape", "strategy", "strategies", "value", "chain", "demand", "supply",
    "revenue", "sales", "future", "global", "regional", "competitive",
    # generic function / service words that attach to many different subjects
    "logistics", "3pl", "services", "service", "solutions", "solution",
    "management", "systems", "system", "platform", "platforms", "provider",
    "providers", "outsourcing", "consulting", "distribution",
    # generic tech qualifiers (handled with more nuance by Layer 3, but
    # downweighted here too so they never dominate a Layer-2-only match)
    "ai", "iot", "blockchain", "cloud", "digital", "smart", "automation",
    "robotics", "software", "technology", "tech", "app", "apps", "online",
}
GENERIC_TERM_WEIGHT = 0.15

# ── Layer 3: compound "[tech] in/for [domain]" detection ─────────────────────
# Same word list as the tech-downweighted set above — these are the terms
# that, when present, mark a topic as a compound tech-in-domain report
# rather than a plain single-subject one.
TECH_QUALIFIERS = {
    "ai", "iot", "blockchain", "cloud", "digital", "smart", "automation",
    "robotics", "machine learning", "ml", "ar", "vr", "saas", "5g",
    "big data", "cybersecurity",
}

_COMPOUND_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(TECH_QUALIFIERS, key=len, reverse=True))
    + r")\b.{0,20}?\b(in|for|driven|based|enabled|powered)\b", re.I,
)


def detect_tech_qualifier(text: str) -> str:
    """Return the tech qualifier present in text (lowercase), or "" if none.
    Only meaningful when the qualifier appears alongside a domain word
    (checked separately by has_compound_structure) — a bare "AI" isn't
    treated as compound on its own."""
    lowered = text.lower()
    for term in sorted(TECH_QUALIFIERS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            return term
    return ""


def has_compound_structure(text: str) -> bool:
    """True if text follows a '[tech] in/for/driven/based/powered [domain]'
    pattern — e.g. 'AI in Medicine', 'Blockchain-based Supply Chain',
    'Cloud-powered Logistics'. Bare mentions of a tech word alone (no
    domain-linking construction) don't count."""
    return bool(_COMPOUND_PATTERN.search(text))


_YEAR_TOKEN = re.compile(r"^(19|20)\d{2}$")  # 1900-2099, forecast-year noise


def weighted_vector(corpus: Corpus, text: str) -> dict[str, float]:
    """Same as Corpus.vector(), but every GENERIC_TERMS token is downweighted
    to GENERIC_TERM_WEIGHT of its normal TF-IDF weight, and bare year tokens
    ("2030", "2019") are dropped entirely — found via testing: 30% of titles
    share a forecast year (149/498 contain "2030"), frequent enough to add
    spurious similarity between two otherwise-unrelated reports but not
    frequent enough for corpus-wide IDF alone to fully zero it out. Years
    carry no subject information regardless of how common they are.
    This is Layer 2: a shared generic word/year contributes far less (or
    nothing) to the similarity score than a shared subject-specific word."""
    base = corpus.vector(text)
    if not base:
        return base
    adjusted = {
        term: weight * GENERIC_TERM_WEIGHT if term in GENERIC_TERMS else weight
        for term, weight in base.items()
        if not _YEAR_TOKEN.match(term)
    }
    norm = sum(w * w for w in adjusted.values()) ** 0.5
    if norm == 0:
        return {}
    return {term: w / norm for term, w in adjusted.items()}


def tech_intersection_ok(text_a: str, text_b: str) -> bool:
    """Layer 3 gate. If EITHER title has compound tech-in-domain structure,
    a match requires BOTH sides to share the same tech qualifier — a bare
    domain-only page never satisfies a compound page's tech half, and two
    compound pages with different tech qualifiers don't count as adjacent
    either ('AI in Medicine' vs 'Blockchain in Medicine' — same domain,
    different tech, not the intended match).

    If NEITHER title is compound, this gate doesn't apply (returns True) —
    Layer 3 only constrains compound-topic cases.
    """
    a_compound = has_compound_structure(text_a)
    b_compound = has_compound_structure(text_b)
    if not a_compound and not b_compound:
        return True
    qual_a = detect_tech_qualifier(text_a) if a_compound else ""
    qual_b = detect_tech_qualifier(text_b) if b_compound else ""
    if a_compound and not b_compound:
        return False  # domain-only page can't satisfy a compound page's tech half
    if b_compound and not a_compound:
        return False
    return qual_a == qual_b and qual_a != ""


def subject_similarity(corpus: Corpus, text_a: str, text_b: str) -> float:
    """Layers 2+3 combined: subject-weighted cosine similarity, gated to 0.0
    if the tech-intersection rule (Layer 3) is violated."""
    if not tech_intersection_ok(text_a, text_b):
        return 0.0
    va = weighted_vector(corpus, text_a)
    vb = weighted_vector(corpus, text_b)
    return cosine(va, vb)
