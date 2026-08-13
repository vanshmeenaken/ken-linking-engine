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


# Junk placeholder values that must never reach an anchor. Ken's source data
# carried a pandas NaN for four pages as the literal string "nan", which
# produced the anchor "Philippines nan Market" before this guard existed.
_JUNK_MARKETS = {"nan", "none", "null", "n/a", "na", "nan market"}


def with_market_suffix(market: str) -> str:
    """Append ' Market' only if the value does not already end in it, so we
    never produce '... Market Market'. Placeholder junk ("nan", "none")
    counts as empty."""
    market = (market or "").strip()
    if not market or market.lower() in _JUNK_MARKETS:
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


# Intent cues -> the anchor suffix that matches them (master PRD 13.7 "align
# anchor with target page intent"). Checked in order; first cue found in the
# surrounding sentence wins. Suffixes match the variants Agent 7 builds
# ("<base> Outlook", "<base> Size", "<base> Trends and Forecast", ...).
_INTENT_CUES = [
    (("outlook", "forecast", "projected", "expected to reach", "future"),
     ("outlook", "trends and forecast")),
    (("growth", "grew", "growing", "cagr", "expand", "rising", "opportunit"),
     ("growth and opportunities", "outlook")),
    (("valued at", "worth", "usd", "size", "revenue", "billion", "million"),
     ("size",)),
    (("trend", "shift", "changing", "evolving"),
     ("trends and forecast", "analysis")),
    (("analysis", "landscape", "competitive", "players", "share"),
     ("analysis",)),
]


def pick_anchor_for_context(options: list[str], sentence: str | None = None,
                            section: str | None = None) -> list[str]:
    """Reorder anchor options so variants matching the surrounding context
    come first (the sentence the link sits in, or its section name).

    Returns a NEW ordered list, never drops options - the caller still
    rotates through it for diversity and skips anchors already taken. With
    no contextual cue, the original order is preserved (primary first).
    """
    options = list(options or [])
    if len(options) < 2:
        return options
    context = f"{sentence or ''} {section or ''}".lower()
    if not context.strip():
        return options
    for cues, suffixes in _INTENT_CUES:
        if any(cue in context for cue in cues):
            preferred: list[str] = []
            for s in suffixes:  # suffix order IS the preference order
                preferred += [o for o in options
                              if o.lower().endswith(s) and o not in preferred]
            if preferred:
                rest = [o for o in options if o not in preferred]
                return preferred + rest
            # cue found but no matching variant exists: keep original order
            return options
    return options
