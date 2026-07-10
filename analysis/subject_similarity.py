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
from config.taxonomy import COUNTRY_ALIASES, COUNTRY_TO_REGION, INDUSTRIES, REGIONS, SCOPE_VALUES

# ── geography tokens to exclude entirely ──────────────────────────────────
# A country/region name carries WHERE, never WHAT — real regression found
# two different-subject reports sharing a country ("Saudi Arabia Cloud-Based
# AIOps Platforms Market" vs "Saudi Arabia Cloud-Based Warehouse Robotics
# Market") scored 0.59 similar almost entirely on "saudi"+"arabia"+"based"
# (all full-weight, none in GENERIC_TERMS). Same failure class as the year-
# token problem below: common enough across the catalog (many "Saudi Arabia
# X Market" titles) to add spurious similarity, not rare enough for
# corpus-wide IDF alone to neutralize. Built from Ken's own taxonomy
# (config/taxonomy.py) rather than a separate list, so it stays in sync with
# the country/region data Agent 2 already trusts.
GEO_TERMS: set[str] = set()
for _name in (
    list(COUNTRY_TO_REGION) + list(COUNTRY_ALIASES) + list(COUNTRY_ALIASES.values())
    + REGIONS + list(SCOPE_VALUES) + list(SCOPE_VALUES.values())
):
    GEO_TERMS.update(tokenize(_name))

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
    # connector words joining a tech qualifier to a domain ("Cloud-Based",
    # "AI-Driven", "Blockchain-Powered") — carry no subject information of
    # their own; found contributing real weight in the Cloud AIOps/Warehouse
    # Robotics regression ("based" had high IDF, ~5.6, since it's not
    # boilerplate-common, but it's still not a subject noun)
    "based", "driven", "powered", "enabled",
    # broad sector/material umbrella words found dominating false-positive
    # matches in a full live audit: "UK Automotive Carbon Fiber Market" vs
    # "Europe Automotive Exhaust Market" scored 0.26 almost entirely on
    # "automotive" (carbon fiber is a material, exhaust is a system — not
    # the same subject); "Asia Pacific Injection Molding Plastic Market" vs
    # "India Plastic Pipes Market" on "plastic" alone (a process vs a
    # product); "Japan Food Antioxidants Market" vs "Asia Pacific Halal
    # Food Market" on "food" alone (an ingredient category vs a compliance
    # angle). Same root cause as GENERIC_TERMS above, at the industry-
    # umbrella level instead of the market-research-boilerplate level —
    # this is Shrey's explicit rule "same industry alone is never enough,"
    # just leaking through a bare word instead of the node_industries gate.
    "oil", "gas", "plastic", "electric", "finance", "auto", "vision",
    # missed inflection: "strategy"/"strategies" were already generic but
    # "strategic" (different token, exact-match list doesn't stem) was not —
    # found solely driving a match between "Global Electric Switch Market
    # Strategy" and "India Pump Market, Growth Opportunities" (dominance
    # 0.99: literally nothing else shared)
    "strategic",
    # mechanism/device-type words that name HOW something works, not WHAT
    # it's for — two products can share the mechanism and be unrelated.
    # Real live false positives: "MEA Insulin Pumps Market" vs "Indonesia
    # Breast Pumps Market" (insulin delivery vs infant feeding, sharing only
    # "pumps"); "Retail Core Banking Solution" vs "Retail Banking Market"
    # (a fintech product vs the sector itself, sharing only "banking");
    # "Radiology Information Systems" vs "Hospital Information Systems"
    # (two different healthcare IT products sharing only "information",
    # with "systems" already generic); "Luxury Fashion" vs "Luxury
    # Hospitality" ("luxury" is a segment qualifier that attaches to almost
    # any consumer category, not a subject); "Acute Hospital Care" vs
    # "Hospital Information Systems" (a clinical service vs IT software,
    # sharing only "hospital").
    "pumps", "banking", "information", "luxury", "hospital",
    # broad qualifier words that attach to almost any product/service
    # ("commercial", "residential", "home" describe WHO/WHERE, not WHAT) —
    # same failure class as "luxury". Found dominating (dominance 1.00,
    # meaning ZERO other shared context) real false positives: "Coin
    # Operated Commercial Laundry" vs "Commercial Cleaning Products"
    # (services vs retail products); "KSA Residential Market Shift" (real
    # estate) vs "UAE Furniture Market Growth: Residential Demand"
    # (furniture retail); "India Home Furniture" vs "Vietnam Home Water
    # Filtration" (furniture vs water treatment equipment).
    "commercial", "residential", "home",
    # "car"/"vehicle" span genuinely different value-chain segments
    # (retail sales, rental, financing, leasing) that are NOT the same
    # market just because they both involve a car. Six separate live false
    # positives, all different pairs of segment: car rental <-> car loan
    # (x3), car rental <-> passenger car sales, car rental <-> used-car
    # platform, off-road vehicle sales <-> vehicle leasing. Contrast with
    # "taxi", "leasing", "dealer" etc., which stayed specific enough to be
    # trustworthy on their own.
    "car", "vehicle",
    # "facility" is a generic location/operations word (same class as
    # already-generic "management", "provider") — "Skilled Nursing Facility
    # Rehabilitation" (clinical care) vs "Facility Management in Hospitals"
    # (a support-services contract) share only "facility".
    "facility",
    # "OEM" (Original Equipment Manufacturer) is cross-industry automotive/
    # manufacturing jargon, not a subject — "KSA Automotive Market: OEM
    # Shifts" vs "UAE Lubricants Market: OEM Access" share only "oem".
    "oem",
    # case-study marketing boilerplate verb, not a subject at all — "How a
    # B2B Packaging Marketplace Boosted Revenue" vs "How Ken Research
    # Boosted IPO Readiness for an Asian Manufacturing Firm" shared nothing
    # but "boosted".
    "boosted",
    # confirmed with Shrey: broad mechanism/sector words, same reasoning as
    # the rest of this block — "Global Blood Screening Market" (diagnostic
    # testing) vs "Saudi Arabia Blood IV Warmers Market" (medical equipment)
    # share only "blood"; "Kuwait Military Radar Market" (detection
    # hardware) vs "Oman Military Simulation And Virtual Training Market"
    # (training software) share only "military".
    "blood", "military",
}
GENERIC_TERM_WEIGHT = 0.15

# Ken's own 14 canonical industry categories (config/taxonomy.py), tokenized
# and folded into the same downweight set for the same reason — "Bahrain
# Healthcare Analytics" vs "Saudi Arabia Healthcare Claims Management" vs
# "Philippines Healthcare Wearables" all scored 0.30-0.38 similar almost
# entirely on the bare word "healthcare", three genuinely different IT
# sub-segments sharing only their industry label. Derived from the taxonomy
# rather than hand-picked, same technique as GEO_TERMS below.
for _industry in INDUSTRIES:
    GENERIC_TERMS.update(tokenize(_industry))

# ── Layer 3: compound "[tech] + [domain]" detection ───────────────────────────
# Same word list as the tech-downweighted set above — these are the terms
# that, when present, mark a topic as a compound tech-in-domain report
# rather than a plain single-subject one.
TECH_QUALIFIERS = {
    "ai", "iot", "blockchain", "cloud", "digital", "smart", "automation",
    "robotics", "machine learning", "ml", "ar", "vr", "saas", "5g",
    "big data", "cybersecurity",
}


def detect_tech_qualifier(text: str) -> str:
    """Return the tech qualifier present in text (lowercase), or "" if none."""
    lowered = text.lower()
    for term in sorted(TECH_QUALIFIERS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            return term
    return ""


def has_compound_structure(text: str) -> bool:
    """True if a tech qualifier appears anywhere in the title.

    Originally this required an explicit linking word ("AI in Medicine",
    "Cloud-powered Logistics"). Real regression against the live catalog
    found that fails on the common "[Domain] [Tech] Market" naming
    convention with no linking word at all — e.g. "Cold Storage Automation
    & Robotics Market" — which the old pattern let through as
    non-compound, so Layer 2 alone (which downweights "automation"/
    "robotics" as generic tech words) scored it 0.62 similar to a plain
    "Cold Storage Market" page. Those are different markets: one is cold
    storage broadly, the other specifically the automation/robotics
    technology layer within it — a half-subject match Shrey's rules reject.
    A bare tech-qualifier mention is now sufficient to mark a title
    compound; tech_intersection_ok() then requires BOTH sides to be
    compound, or NEITHER — not that they share the same qualifier (see
    tech_intersection_ok's own docstring for why exact-match was too
    strict)."""
    return bool(detect_tech_qualifier(text))


_YEAR_TOKEN = re.compile(r"^(19|20)\d{2}$")  # 1900-2099, forecast-year noise


def weighted_vector(corpus: Corpus, text: str) -> dict[str, float]:
    """Same as Corpus.vector(), but every GENERIC_TERMS token is downweighted
    to GENERIC_TERM_WEIGHT of its normal TF-IDF weight, and bare year tokens
    ("2030", "2019") and geography tokens (GEO_TERMS — country/region names)
    are dropped entirely.

    Years: found via testing that 30% of titles share a forecast year
    (149/498 contain "2030"), frequent enough to add spurious similarity
    between two otherwise-unrelated reports but not frequent enough for
    corpus-wide IDF alone to fully zero it out. Geography: same failure
    class, found via a live regression — two DIFFERENT-subject reports
    sharing a country ("Saudi Arabia Cloud-Based AIOps Platforms" vs "Saudi
    Arabia Cloud-Based Warehouse Robotics") scored 0.59 similar almost
    entirely on the shared country name. Neither years nor geography carry
    subject information regardless of how common they are — this is Layer
    2's core rule: a shared generic/non-subject word contributes far less
    (or nothing) to the score than a shared subject-specific word."""
    base = corpus.vector(text)
    if not base:
        return base
    adjusted = {
        term: weight * GENERIC_TERM_WEIGHT if term in GENERIC_TERMS else weight
        for term, weight in base.items()
        if not _YEAR_TOKEN.match(term) and term not in GEO_TERMS
    }
    norm = sum(w * w for w in adjusted.values()) ** 0.5
    if norm == 0:
        return {}
    return {term: w / norm for term, w in adjusted.items()}


def tech_intersection_ok(text_a: str, text_b: str) -> bool:
    """Layer 3 gate: a tech-qualified title can only match another
    tech-qualified title; a bare domain-only page never satisfies a
    compound page's tech half. This is the real Cold Storage bug fix — "Cold
    Storage Market" (no tech qualifier, broad) vs "Cold Storage Automation &
    Robotics Market" (qualified, narrower) are DIFFERENT markets despite
    sharing "cold storage"; the asymmetry itself is the signal.

    Does NOT require both sides to carry the SAME qualifier when both are
    compound. Regression found requiring exact-qualifier-match rejected a
    real good pair — "Brazil Smart Agriculture and Agri Drones Market" vs
    "Germany Agri Drones Robotics Market" — where "smart" and "robotics" are
    just different words for the same automation-adjacent tech layer on an
    identical core subject ("agri drones"), not two competing technologies.
    Distinguishing "different tech, same domain, actually unrelated"
    ('AI in Medicine' vs 'Blockchain in Medicine') from "different tech
    words, same domain, actually the same report" (the Agri Drones case) is
    exactly the judgment call Layer 4 (the LLM judge) exists for — a fixed
    qualifier-equality rule can't reliably tell them apart, and a live
    example proved it gets it wrong. Left to Layer 2's own weighted cosine
    (tech words already downweighted there) plus the optional Layer 4 judge
    to sort out the remaining domain-word overlap.
    """
    return has_compound_structure(text_a) == has_compound_structure(text_b)


def subject_similarity(corpus: Corpus, text_a: str, text_b: str) -> float:
    """Layers 2+3 combined: subject-weighted cosine similarity, gated to 0.0
    if the tech-intersection rule (Layer 3) is violated."""
    if not tech_intersection_ok(text_a, text_b):
        return 0.0
    va = weighted_vector(corpus, text_a)
    vb = weighted_vector(corpus, text_b)
    return cosine(va, vb)
