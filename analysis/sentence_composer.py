"""Compose a ready-to-insert link sentence when no existing sentence fits.

The hard constraint (master PRD 12.3): the system must NEVER invent market
numbers, sources, or facts. So every composed sentence is a claim-free
reader pointer - it tells the reader where related coverage lives, framed by
the relationship type, and carries the anchor text. The web team pastes it
at the recommended position; nothing in it can be factually wrong because
it asserts nothing about the market itself.
"""
from __future__ import annotations

# relationship_type -> sentence template ({anchor} is replaced verbatim).
# All templates are deliberately fact-free: no numbers, no trends, no claims.
_TEMPLATES = {
    "same_market": ("A detailed picture of the same market in another "
                    "geography is available in the {anchor}."),
    "global_local": ("The wider global context for this market is covered "
                     "in the {anchor}."),
    "adjacent_market": ("Readers tracking adjacent opportunities can explore "
                        "the {anchor} for a closely related market."),
    "country_region": ("Regional context for this market is available in "
                       "the {anchor}."),
    "report_article_support": ("The full market data behind this analysis is "
                               "covered in the {anchor}."),
    "case_study_support": ("A real-world application of these dynamics is "
                           "documented in the {anchor}."),
}
_DEFAULT_TEMPLATE = "Related coverage is available in the {anchor}."


def compose_link_sentence(anchor: str, relationship_type: str) -> str:
    """A natural, claim-free sentence carrying the anchor, to be inserted
    at the recommended position on the source page."""
    template = _TEMPLATES.get(relationship_type, _DEFAULT_TEMPLATE)
    return template.format(anchor=(anchor or "").strip())
