"""Entity taxonomy and normalization rules for the Phase 2 intelligence layer.

Stdlib only — importable from both Python environments (global and venv).
Used by Agent 2 (entity extraction), Agent 3 (relationship mapping), and tests.

Design: docs/03-DATABASE/04-PHASE2-SCHEMA-DESIGN.md, Module 2.2.
"""

from __future__ import annotations

import re
import unicodedata

# ── Entity types (master PRD section 14.2) ───────────────────────────────────

ENTITY_TYPES = [
    "industry", "sub_industry", "market", "segment", "country", "region",
    "company", "product", "technology", "service", "persona", "regulation",
    "claim", "evidence", "time_period",
]

# ── Canonical industries (the 14 Ken Research industries, from Agent 1) ──────

INDUSTRIES = [
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

_INDUSTRY_LOOKUP = {ind.lower().replace(" & ", " and "): ind for ind in INDUSTRIES}

# Non-canonical industry labels observed in Phase 1 data -> canonical industry.
# Only unambiguous mappings belong here. Known-but-unmapped labels (left out
# deliberately): 'Articles' (content type, not an industry), 'Consulting' and
# 'Consumer Services' (no clean match in the 14 — mapping would guess).
INDUSTRY_ALIASES = {
    "banking financial services and insurance": "BFSI",
    "educational services": "Education & Recruitment",
}

# ── Regions (canonical) ──────────────────────────────────────────────────────

REGIONS = [
    "Asia Pacific", "Middle East", "Africa", "Europe", "North America",
    "Latin America", "Global",
]

# ── Country → region map ─────────────────────────────────────────────────────
# Keys are canonical lowercase country names as normalized by normalize_country().

COUNTRY_TO_REGION = {
    # Asia Pacific
    "india": "Asia Pacific", "vietnam": "Asia Pacific", "indonesia": "Asia Pacific",
    "philippines": "Asia Pacific", "malaysia": "Asia Pacific", "thailand": "Asia Pacific",
    "singapore": "Asia Pacific", "south korea": "Asia Pacific", "japan": "Asia Pacific",
    "china": "Asia Pacific", "australia": "Asia Pacific", "new zealand": "Asia Pacific",
    "bangladesh": "Asia Pacific", "sri lanka": "Asia Pacific", "pakistan": "Asia Pacific",
    "myanmar": "Asia Pacific", "cambodia": "Asia Pacific", "taiwan": "Asia Pacific",
    "hong kong": "Asia Pacific", "nepal": "Asia Pacific",
    # Middle East
    "saudi arabia": "Middle East", "uae": "Middle East", "qatar": "Middle East",
    "kuwait": "Middle East", "bahrain": "Middle East", "oman": "Middle East",
    "iran": "Middle East", "iraq": "Middle East", "israel": "Middle East",
    "jordan": "Middle East", "lebanon": "Middle East", "turkey": "Middle East",
    "yemen": "Middle East",
    # Africa
    "south africa": "Africa", "nigeria": "Africa", "kenya": "Africa",
    "egypt": "Africa", "morocco": "Africa", "ethiopia": "Africa",
    "ghana": "Africa", "tanzania": "Africa", "algeria": "Africa",
    "tunisia": "Africa", "uganda": "Africa",
    # Europe
    "germany": "Europe", "france": "Europe", "italy": "Europe", "spain": "Europe",
    "uk": "Europe", "netherlands": "Europe", "poland": "Europe", "sweden": "Europe",
    "norway": "Europe", "denmark": "Europe", "finland": "Europe", "belgium": "Europe",
    "switzerland": "Europe", "austria": "Europe", "portugal": "Europe",
    "ireland": "Europe", "greece": "Europe", "russia": "Europe", "ukraine": "Europe",
    "czech republic": "Europe", "romania": "Europe", "hungary": "Europe",
    # North America
    "usa": "North America", "canada": "North America", "mexico": "North America",
    # Latin America
    "brazil": "Latin America", "argentina": "Latin America", "chile": "Latin America",
    "colombia": "Latin America", "peru": "Latin America", "ecuador": "Latin America",
}

# ── Country aliases → canonical lowercase name ───────────────────────────────

COUNTRY_ALIASES = {
    "united arab emirates": "uae",
    "u.a.e": "uae",
    "u.a.e.": "uae",
    "ksa": "saudi arabia",
    "kingdom of saudi arabia": "saudi arabia",
    "united states": "usa",
    "united states of america": "usa",
    "u.s.": "usa",
    "u.s.a.": "usa",
    "us": "usa",
    "america": "usa",
    "united kingdom": "uk",
    "great britain": "uk",
    "england": "uk",
    "korea": "south korea",
    "republic of korea": "south korea",
    "viet nam": "vietnam",
    "turkiye": "turkey",
    "czechia": "czech republic",
    "holland": "netherlands",
}

# ── Scope/region values that appear in content_nodes.country but are NOT
#    countries (Day 1 audit finding #3). Mapped to their canonical region
#    entity, or "Global" scope. ────────────────────────────────────────────────

SCOPE_VALUES = {
    "global": "Global",
    "worldwide": "Global",
    "international": "Global",
    "gcc": "Middle East",
    "mena": "Middle East",
    "middle east": "Middle East",
    "middle east and north africa": "Middle East",
    "asia": "Asia Pacific",
    "apac": "Asia Pacific",
    "asia pacific": "Asia Pacific",
    "asia-pacific": "Asia Pacific",
    "asean": "Asia Pacific",
    "southeast asia": "Asia Pacific",
    "europe": "Europe",
    "eu": "Europe",
    "africa": "Africa",
    "north america": "North America",
    "latin america": "Latin America",
    "latam": "Latin America",
    "south america": "Latin America",
}

# ── Market-name cleanup rules ────────────────────────────────────────────────
# Applied in order to a page title/H1 to isolate the market name.
# Handles the observed Ken title patterns (Day 1 audit section 3) plus the
# sitemap-slug suffixes from the earlier kr-interlink work.

_MARKET_STRIP_PATTERNS = [
    # "| 2019-2030 | Ken Research", "| 2019 - 2030 | Ken Research" (any dash char)
    re.compile(r"\|.*$"),
    # "Market Share, Companies & Trends Report 2025-2031" → keep "Market"
    re.compile(r"\bmarket\s+share,?\s+companies\s*&\s*trends\s+report\s*[\d\s\-–—]*$", re.I),
    # "Market Size, Share & Trends ..." variants → keep "Market"
    re.compile(r"\bmarket\s+(size|share|growth|trends|outlook|analysis|report|forecast)\b.*$", re.I),
    # "Industry Outlook to 2030", "Outlook to 2030"
    re.compile(r"\b(industry\s+)?outlook\s+to\s+\d{4}.*$", re.I),
    # trailing year ranges: "2025-2031", "2019 to 2030"
    re.compile(r"\b\d{4}\s*(?:[-–—]|to)\s*\d{4}\b.*$", re.I),
    # trailing standalone years
    re.compile(r"\b\d{4}\s*$"),
]

_WHITESPACE = re.compile(r"\s+")

# Words that open a narrative/editorial title, not a market name
# ("How Ken Research Helped...", "Top Players in...", "Why X is...").
_NARRATIVE_LEADS = {
    "how", "why", "what", "when", "top", "best", "is", "are", "can",
    "will", "the", "a", "an", "from", "inside", "understanding",
}

# Keep everything up to and including the first standalone "Market" word:
# "API Market Shift from Import Dependence" -> "API Market".
_FIRST_MARKET_WORD = re.compile(r"^(.*?\bmarkets?\b)", re.I)

_MAX_MARKET_WORDS = 8  # longer names are junk narrative, reject (precision-first)


def _clean_text(value: str) -> str:
    """Unicode-normalize, replace mojibake/exotic dashes, collapse whitespace."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    # Replacement char (mojibake, e.g. "2019 � 2030") and exotic dashes → "-"
    text = text.replace("�", "-").replace("–", "-").replace("—", "-")
    return _WHITESPACE.sub(" ", text).strip()


def normalize_country(raw: str) -> str:
    """Map a raw country string to its canonical lowercase name.

    Returns "" if the value is a scope/region (use classify_geo for those)
    or unrecognized.
    """
    key = _clean_text(raw).lower().rstrip(".")
    if not key:
        return ""
    key = COUNTRY_ALIASES.get(key, key)
    return key if key in COUNTRY_TO_REGION else ""


def classify_geo(raw: str) -> tuple[str, str]:
    """Classify a raw geography string from content_nodes.country.

    Returns (entity_type, canonical_value):
      ("country", "india")          — real country, canonical lowercase
      ("region", "Middle East")     — scope/region value (gcc, mena, europe…)
      ("", "")                      — unrecognized
    """
    key = _clean_text(raw).lower().rstrip(".")
    if not key:
        return "", ""
    if key in SCOPE_VALUES:
        return "region", SCOPE_VALUES[key]
    country = normalize_country(key)
    if country:
        return "country", country
    return "", ""


def region_for_country(country: str) -> str:
    """Canonical region for a canonical country name, or ""."""
    return COUNTRY_TO_REGION.get(normalize_country(country) or country.lower(), "")


def normalize_industry(raw: str) -> str:
    """Map a raw industry string to one of the 14 canonical industries, or ""."""
    key = _clean_text(raw).lower().replace(" & ", " and ")
    if key in INDUSTRY_ALIASES:
        return INDUSTRY_ALIASES[key]
    if key in _INDUSTRY_LOOKUP:
        return _INDUSTRY_LOOKUP[key]
    # Prefix match — same tolerance as Agent 1's _match_industry
    for norm_key, label in _INDUSTRY_LOOKUP.items():
        prefix = " ".join(norm_key.split()[:2])
        if len(prefix) > 5 and key.startswith(prefix):
            return label
    return ""


def extract_market_from_title(title: str, geography_words: list[str] | None = None) -> str:
    """Isolate the market name from a Ken page title/H1.

    'Bahrain Pectin Market Share, Companies & Trends Report 2025-2031'
        → 'Pectin Market' (with geography_words=['bahrain'])
    'Qatar Aviation Cybersecurity Market | 2019-2030 | Ken Research'
        → 'Aviation Cybersecurity Market'

    Returns "" when no market name can be isolated.
    """
    text = _clean_text(title)
    if not text:
        return ""
    # Data-corruption guard: a handful of Phase 1 titles are literally the
    # string "nan" (a pandas NaN that leaked into the title field during an
    # earlier data step) glued to the real template suffix, e.g.
    # "nan Market Analysis, Trends & Forecast 2025-2031". "nan" must never
    # be treated as a real market-name word — reject outright so the caller
    # falls back to H1.
    if re.match(r"^nan\b", text, re.I):
        return ""
    # Narrative titles put the market name mid-sentence or nowhere —
    # truncate at the first colon or comma before any pattern work.
    text = re.split(r"[:,]", text, maxsplit=1)[0].strip()
    for pattern in _MARKET_STRIP_PATTERNS:
        replacement = "Market" if "market" in pattern.pattern.lower() else ""
        text = pattern.sub(replacement, text).strip(" ,-|")
    # Keep only up to the first "Market" word: trailing narrative
    # ("API Market Shift from Import Dependence") carries no entity value.
    match = _FIRST_MARKET_WORD.match(text)
    if match:
        text = match.group(1)
    # Drop leading geography phrases ("Bahrain Pectin Market" → "Pectin Market").
    # Full-phrase prefix matching, longest first — never strips ordinary words
    # that merely appear inside a geography name (e.g. the "New" of
    # "New Energy Vehicle Market" survives even though "New Zealand" is known).
    if geography_words:
        phrases = sorted(
            {_clean_text(g).lower() for g in geography_words if g},
            key=len, reverse=True,
        )
        stripped = True
        while stripped:
            stripped = False
            lowered = text.lower()
            for phrase in phrases:
                if phrase and lowered.startswith(phrase + " "):
                    text = text[len(phrase):].lstrip(" ,-")
                    stripped = True
                    break
    text = _WHITESPACE.sub(" ", text).strip(" ,-")
    # Precision guards: reject anything that is not a clean market name.
    words = text.split()
    lowered = text.lower()
    # Standalone word only — "Automotive Aftermarket" must not pass as market
    if not re.search(r"\bmarkets?\b", lowered):
        return ""
    if not 2 <= len(words) <= _MAX_MARKET_WORDS:
        return ""
    if words[0].lower().rstrip(",") in _NARRATIVE_LEADS:
        return ""
    if words[0][0].isdigit() or words[0].startswith(("%", "$")):
        return ""
    if "ken research" in lowered:
        return ""
    # Narrative tells mid-name ("Shimizu Margin Recovery in Japan ... Market",
    # "Benchmarking of Indonesia ... Market") — real market names don't
    # contain these. " in " is allowed only for short compound topics
    # ("AI in Medicine Market").
    if any(tell in lowered for tell in (" of ", " for ", " with ", " by ",
                                        "'s ", "-s ", " via ", " through ",
                                        " driving ", " driven ")):
        return ""
    if " in " in lowered and len(words) > 5:
        return ""
    return text


def _depluralize(word: str) -> str:
    """Fold a simple English plural for dedup keys ('tools' -> 'tool').
    Conservative: leaves short words and -ss/-us/-is endings alone so
    'gas', 'glass', 'analysis' survive unchanged."""
    if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def normalize_market_name(raw: str) -> str:
    """Normalized market name used as the dedup key.

    Lowercased, cleaned, and depluralized word-by-word so singular/plural
    variants collapse to one entity: 'Power Tools Market' and
    'Power Tool Market' both key to 'power tool market'
    (Day 4 verification finding: 4 such pairs existed after Day 3).
    """
    cleaned = _clean_text(raw).lower()
    return " ".join(_depluralize(w) for w in cleaned.split())
