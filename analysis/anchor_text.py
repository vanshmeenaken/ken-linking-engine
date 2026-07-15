"""Shared anchor-text helpers used by Agent 6 (link recommendations) and
Agent 7 (anchor banks).

Anchor rules (master PRD 18.3): descriptive anchors only, built from
country + market / region + market / market + intent. Never generic
("click here", "read more"). Geographic acronyms stay upper-case.
"""
from __future__ import annotations

# Geographic acronyms that .title() would mangle (Uae -> UAE).
GEO_ACRONYMS = {
    "uae": "UAE", "usa": "USA", "ksa": "KSA", "uk": "UK", "us": "US",
    "eu": "EU", "gcc": "GCC", "apac": "APAC", "mena": "MENA", "asean": "ASEAN",
}

# master PRD 18.3 anchors to never emit.
GENERIC_ANCHORS = {
    "click here", "read more", "this report", "learn more", "best report",
    "market research report", "here", "more info", "find out more", "read this",
}


def format_geo(country: str) -> str:
    """Title-case a country/region, keeping acronyms upper (uae -> UAE)."""
    return " ".join(GEO_ACRONYMS.get(w.lower(), w.title())
                    for w in (country or "").split())


def with_market_suffix(market: str) -> str:
    """Append ' Market' only if the value does not already end in it, so we
    never produce '... Market Market'."""
    market = (market or "").strip()
    if not market:
        return ""
    return market if market.lower().endswith("market") else f"{market} Market"


def build_primary_anchor(market: str, country: str, title: str = "") -> tuple[str, float]:
    """Return (anchor, quality 0-1). Prefers 'Country Market'; falls back to a
    cleaned title with a lower quality score to reflect the uncertainty."""
    market = (market or "").strip()
    country = (country or "").strip()
    if market and country:
        return f"{format_geo(country)} {with_market_suffix(market)}", 1.0
    if market:
        return with_market_suffix(market), 0.9
    title = (title or "").strip()
    for sep in (" Market Size", " Market Share", " Market Analysis",
                " Market Report", " Market,", " | ", " Report "):
        i = title.find(sep)
        if i > 0:
            title = title[:i] + (" Market" if "Market" in sep else "")
            break
    return (title[:70] or "Market Report"), 0.6


def is_generic(anchor: str) -> bool:
    return (anchor or "").strip().lower() in GENERIC_ANCHORS
