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


# relationship_type -> a trailing connector CLAUSE (comma-led, lowercase,
# no terminal punctuation) that weaves the anchor into an EXISTING sentence
# instead of composing a whole new one. Deliberately fact-free for the same
# reason as _TEMPLATES: it only connects the existing sentence to the
# target, asserting nothing new about either market.
_WEAVE_CLAUSES = {
    "same_market": "a pattern also seen in the {anchor}",
    "global_local": "consistent with the wider trend covered in the {anchor}",
    "adjacent_market": "a dynamic also shaping the {anchor}",
    "country_region": "in line with regional coverage in the {anchor}",
    "report_article_support": "as detailed further in the {anchor}",
    "case_study_support": "as demonstrated in the {anchor}",
}
_DEFAULT_WEAVE_CLAUSE = "a trend also relevant to the {anchor}"


def weave_anchor_into_sentence(sentence: str, anchor: str,
                               relationship_type: str) -> str:
    """Rewrite an EXISTING sentence to carry the anchor inline, instead of
    just naming the sentence and leaving the editor to guess where the link
    goes. The original sentence's wording and facts are kept byte-for-byte;
    only a short connector clause naming the anchor is appended before the
    final punctuation - so nothing already on the page can be changed by
    this rewrite, only extended.
    """
    sentence = (sentence or "").strip()
    anchor = (anchor or "").strip()
    if not sentence or not anchor:
        return sentence
    clause = _WEAVE_CLAUSES.get(relationship_type, _DEFAULT_WEAVE_CLAUSE).format(
        anchor=anchor)
    trailing = sentence[-1] if sentence[-1] in ".!?" else "."
    body = sentence[:-1] if sentence[-1] in ".!?" else sentence
    return f"{body}, {clause}{trailing}"
