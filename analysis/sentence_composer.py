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


# Framings offered in the manual workbench. Each puts the anchor in a
# DIFFERENT position, because a single shape repeated across a site is
# detectable (the exact problem Shrey identified in the automated pass):
#   front    - the comparison opens the sentence
#   mid      - an appositive interrupts the original clause
#   subject  - the anchor becomes what the sentence is about
#   trailing - the classic add-on, offered last and labelled as weakest
SUGGESTION_STYLES = ("front", "mid", "subject", "trailing")

_FRONT_LEADS = {
    "same_market": "Mirroring the pattern in the {anchor},",
    "global_local": "Consistent with the global view in the {anchor},",
    "adjacent_market": "As in the {anchor},",
    "adjacent_regional": "Much as in the {anchor},",
    "regional": "Alongside the {anchor},",
    "country_region": "In line with regional coverage in the {anchor},",
    "report_article_support": "As detailed in the {anchor},",
    "case_study_support": "As demonstrated in the {anchor},",
}
_MID_APPOSITIVES = {
    "same_market": ", a pattern the {anchor} tracks in another geography,",
    "global_local": ", set against the global picture in the {anchor},",
    "adjacent_market": ", a dynamic shared with the {anchor},",
    "adjacent_regional": ", much as in the {anchor},",
    "regional": ", as also covered in the {anchor},",
    "country_region": ", in line with the {anchor},",
    "report_article_support": ", examined further in the {anchor},",
    "case_study_support": ", as evidenced in the {anchor},",
}
_DEFAULT_FRONT = "As in the {anchor},"
_DEFAULT_MID = ", a trend shared with the {anchor},"


# Safe to fold into a subordinate clause when they open a sentence. Anything
# else keeps its capital, because lowercasing the first word of a proper term
# mangles it ("Distribution Channel" became "distribution Channel" before this
# was narrowed).
_FOLDABLE_OPENERS = {
    "the", "this", "these", "those", "a", "an", "its", "their", "his", "her",
    "as", "with", "among", "despite", "however", "currently", "recently",
    "approximately", "taken",
}


def _lower_first(text: str) -> str:
    """Lowercase the opening word only when it is a plain function word AND
    the following word is not itself capitalised - so proper terms and
    multi-word product names survive being folded into a clause."""
    if not text:
        return text
    words = text.split(" ", 1)
    first = words[0]
    if first.lower().strip(",") not in _FOLDABLE_OPENERS:
        return text
    rest = words[1] if len(words) > 1 else ""
    if rest[:1].isupper():
        return text          # next word is a proper noun: leave case alone
    return first.lower() + (" " + rest if rest else "")


# Inserting an appositive directly before the main verb is grammatical
# regardless of how many commas the sentence contains. Splitting on the first
# comma is not: in a sentence listing "brand websites, applications,
# marketplaces..." it dropped the clause inside the list.
_MAIN_VERBS = (" is ", " are ", " was ", " were ", " has ", " have ",
               " remains ", " remain ", " continues ", " continue ",
               " accounted ", " ranks ", " commands ", " includes ",
               " provides ", " drives ", " adds ", " demonstrates ")


def _mid_insertion_point(core: str) -> int | None:
    """Index of the main verb to insert an appositive before, or None."""
    best = None
    for verb in _MAIN_VERBS:
        i = core.find(verb)
        if i > 0 and (best is None or i < best):
            best = i
    # require a subject of at least two words so the clause is not stranded
    if best is not None and len(core[:best].split()) >= 2:
        return best
    return None


def suggest_sentence_framings(sentence: str, anchor: str,
                              relationship_type: str = "") -> list[dict]:
    """Several ways to place `anchor` inside `sentence`, for a human to choose
    from or edit. Returns [{style, label, sentence}] - never invents a fact,
    only rearranges the original wording and adds a connector naming the
    target. The workbench shows these as options; the user can always write
    their own instead.
    """
    sentence = (sentence or "").strip()
    anchor = (anchor or "").strip()
    if not sentence or not anchor:
        return []
    body = sentence.rstrip()
    terminal = body[-1] if body[-1] in ".!?" else "."
    core = body.rstrip(".!?").strip()

    front_lead = _FRONT_LEADS.get(relationship_type, _DEFAULT_FRONT).format(
        anchor=anchor)
    mid_clause = _MID_APPOSITIVES.get(relationship_type, _DEFAULT_MID).format(
        anchor=anchor)

    out = [{
        "style": "front",
        "label": "Comparison first (anchor opens the sentence)",
        "sentence": f"{front_lead} {_lower_first(core)}{terminal}",
    }]

    # mid: insert the appositive before the main verb, which stays
    # grammatical even when the sentence contains a list
    cut = _mid_insertion_point(core)
    if cut is not None:
        out.append({
            "style": "mid",
            "label": "Woven mid-sentence (interrupts the original clause)",
            "sentence": f"{core[:cut]}{mid_clause}{core[cut:]}{terminal}",
        })

    out.append({
        "style": "subject",
        "label": "Anchor as the subject (rewrites the opening)",
        "sentence": (f"The {anchor} shows the same pattern: "
                     f"{_lower_first(core)}{terminal}"),
    })
    out.append({
        "style": "trailing",
        "label": "Trailing mention (weakest: reads as an add-on)",
        "sentence": weave_anchor_into_sentence(sentence, anchor,
                                               relationship_type),
    })
    # de-duplicate while keeping order
    seen, unique = set(), []
    for o in out:
        if o["sentence"] and o["sentence"] not in seen:
            seen.add(o["sentence"])
            unique.append(o)
    return unique


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
    # Strip ANY trailing punctuation before appending the clause. Only
    # stripping .!? produced malformed output on real page text: a sentence
    # ending in a colon ("Ken Research deployed a three-phase engagement:")
    # became "... engagement :, a dynamic also shaping ...". Sentences ending
    # in a colon or semicolon introduce a list, so a clause cannot simply be
    # appended - those become a separate following sentence instead.
    body = sentence.rstrip()
    if body[-1] in ":;?!":
        # A colon/semicolon introduces a list, and a clause tacked onto a
        # question or exclamation reads wrong ("Is now the right time to
        # enter, a pattern also seen in..."). Keep the original line intact
        # and add the link as its own following sentence.
        return f"{body} {clause[0].upper()}{clause[1:]}."
    body = body.rstrip(".,;: ")
    return f"{body}, {clause}."
