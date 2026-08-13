"""Agent 11 - Editorial Review Agent (master PRD 13.11; Phase 3).

Turns a link_recommendations row into a plain-English review note for a human
editor: why the link is recommended, where it goes, what anchor it uses, what
relationship it supports, its SEO/business value, and its risk. This agent
never approves or rejects anything (master PRD section 26: new contextual
body links always require human approval). It only prepares what a human
needs to make that call quickly, without reading raw scores or JSON.

Deterministic and template-based (Phase 2/3 discipline: deterministic before
LLM), built entirely from data already computed by Agents 6, 7, and 10 - no
new scoring, no new crawling, no new judgement. It is a translation layer,
not a decision layer.

Usage (library, not a CLI - called from the API):
    from agents.agent_11_editorial_review import build_review_note
    note = build_review_note(recommendation_row, source_node, target_node)
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.contextual_placement import _tokens, subject_text

# Stored titles carry site branding and formatting noise an editor doesn't
# need in a review note, e.g. "Qatar Nordic Regulatory Affairs Market |
# 2019-2030 | Ken Research" or "India Online Grocery Market,  E-groceries:
# Ken Research" (the double space is genuine stale data from Phase 1
# ingestion). This is DISPLAY-ONLY cleanup for the review note; the stored
# content_nodes.title is left untouched.
_KEN_RESEARCH_SUFFIX_RE = re.compile(r"[\s:,|-]*ken research\s*$", re.IGNORECASE)
_KEN_RESEARCH_PREFIX_RE = re.compile(
    r"^ken research(?: *[-:|] *| +)", re.IGNORECASE
)


def clean_title(title: str) -> str:
    title = (title or "").strip()
    title = _KEN_RESEARCH_PREFIX_RE.sub("", title)
    if "|" in title:
        title = title.split("|", 1)[0]
    else:
        title = _KEN_RESEARCH_SUFFIX_RE.sub("", title)
    return re.sub(r"\s+", " ", title).strip()


def _value_word(score: float | None) -> str:
    if score is None:
        return "Unknown"
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def _risk_word(risk_flag: str | None) -> str:
    return {"low": "Low risk", "medium": "Needs a second look",
            "high": "High risk, review carefully"}.get(risk_flag, "Unknown")


def _placement_sentence(rec: dict) -> str:
    if rec["placement_type"] == "contextual_body" and rec.get("suggested_sentence"):
        return (f'Inside the existing "{rec.get("placement_section", "body")}" '
                f'text, in the sentence: "{rec["suggested_sentence"]}"')
    if rec["placement_type"] == "best_available_paragraph" and rec.get("suggested_sentence"):
        return (f'In the "{rec.get("placement_section", "body")}" section, in '
                f'the best available paragraph: "{rec["suggested_sentence"]}" '
                '(no sentence on the page strongly covers the target - this '
                'is the closest one, so judge whether the link reads '
                'naturally there)')
    if rec["placement_type"] == "section_block":
        return (f'In the page\'s real "{rec.get("placement_section", "body")}" '
                'section (no single sentence stood out, so add it as a natural '
                'mention anywhere in that section)')
    if rec["placement_type"] == "related_reports_block":
        return ('In a "Related Reports" block at the end of the page '
                '(no single sentence was a strong enough match to place it in the body)')
    section = rec.get("placement_section") or rec["placement_type"].replace("_", " ")
    return f'In the "{section}" section of the page'


def _relationship_sentence(relationship_type: str, source_title: str, target_title: str) -> str:
    labels = {
        "same_market": f'Both pages cover the same market ("{target_title}"), in different countries.',
        "adjacent_market": f'"{source_title}" and "{target_title}" cover closely related markets in the same industry.',
        "country_region": f'"{target_title}" is the regional hub that "{source_title}" belongs under.',
        "global_local": f'"{target_title}" is the global overview of the same market "{source_title}" covers locally.',
        "report_article_support": f'"{source_title}" is an article that discusses the market "{target_title}" reports on in depth.',
        "case_study_support": f'"{source_title}" is a case study that demonstrates the market covered by "{target_title}".',
    }
    return labels.get(relationship_type,
                      f'These pages are related by a "{relationship_type}" connection.')


def _placement_reason(rec: dict, target_title: str) -> str:
    """WHY this exact spot is right - the editor's approve/reject hinges on
    seeing the placement justified, not just named.

    Deterministic and honest: for contextual placements the reason is the
    actual subject overlap between the chosen sentence and the target (the
    same signal that chose the spot); for section/related placements it
    explains the fallback truthfully.
    """
    sentence = rec.get("suggested_sentence") or ""
    section = rec.get("placement_section") or "body"
    if rec["placement_type"] == "contextual_body" and sentence:
        target_subject = subject_text(rec.get("anchor_text", ""), target_title)
        shared = sorted(_tokens(sentence) & _tokens(target_subject))
        if shared:
            terms = ", ".join(f'"{w}"' for w in shared[:5])
            return (f"This sentence already discusses {terms} - the exact "
                    f"subject the target report covers. A reader mid-sentence "
                    f"here is actively thinking about this topic, so the link "
                    f"answers a question they already have. That is what makes "
                    f"a contextual link valuable to both readers and search "
                    f"engines, versus a generic list at the page bottom.")
        return (f'This sentence was the closest topical match to the target '
                f'in the whole "{section}" text. Verify the fit when '
                f'approving - no single strong shared term stood out.')
    if rec["placement_type"] == "best_available_paragraph" and sentence:
        target_subject = subject_text(rec.get("anchor_text", ""), target_title)
        shared = sorted(_tokens(sentence) & _tokens(target_subject))
        overlap = (", ".join(f'"{w}"' for w in shared[:5])
                   if shared else "no strong shared subject terms")
        return (f'No sentence on this page strongly covers the target\'s '
                f'subject, so this is the CLOSEST available paragraph '
                f'({overlap}). Approve only if the link reads naturally '
                f'here; otherwise reject - the generic Related Reports '
                f'block is not used as a default because that section may '
                f'be removed from the site.')
    if rec["placement_type"] == "section_block":
        return (f'No single sentence on the page matched the target strongly '
                f'enough to embed the link honestly. The "{section}" section '
                f'is the best real home by purpose: its content type fits '
                f'this link, so add the anchor as a natural mention anywhere '
                f'in that section.')
    if rec["placement_type"] == "related_reports_block":
        return ("No sentence in the page body genuinely covers the target's "
                "subject - forcing the link into unrelated prose would read "
                "as spam to users and search engines. The Related Reports "
                "area is the honest placement: readers finishing this page "
                "get the target as a next step.")
    if rec["placement_type"] == "hub_link":
        return (f'This is a hub listing link: the target belongs in the '
                f'"{section}" listing so readers can navigate down from the '
                f'hub to it.')
    return (f'Placed in "{section}" - review the fit manually; this '
            f'placement type carries no automatic justification.')


@dataclass
class ReviewNote:
    recommendation_id: str
    headline: str
    why: str
    where: str
    placement_reason: str
    anchor: str
    relationship: str
    seo_value: str
    business_value: str
    risk: str
    plain_summary: str


def build_review_note(rec: dict, source_title: str, target_title: str) -> ReviewNote:
    """Build the full human-readable review note for one recommendation.

    `rec` is a link_recommendations row (as a dict); `source_title` and
    `target_title` are the two pages' titles, for readable sentences instead
    of raw URLs.
    """
    source_title = clean_title(source_title)
    target_title = clean_title(target_title)
    seo_val = _value_word(rec.get("seo_score"))
    biz_val = _value_word(rec.get("business_score"))
    risk_val = _risk_word(rec.get("risk_flag"))
    relationship = _relationship_sentence(
        rec["relationship_type"], source_title, target_title)
    relationship_class = (rec.get("relationship_class") or rec["relationship_type"]).replace("_", " ")
    market_score = float(rec.get("market_match_score") or 0.0)
    technology_score = float(rec.get("technology_match_score") or 0.0)
    relationship = (
        f"Classification: {relationship_class}. Market relevance: "
        f"{market_score:.0%}; technology relevance: {technology_score:.0%}. "
        f"{relationship}"
    )
    where = _placement_sentence(rec)
    placement_reason = _placement_reason(rec, target_title)

    why = (f'Recommended with a score of {rec["link_score"]:.0f} out of 100 '
          f'({rec["score_band"]}). {relationship}')

    headline = (f'Link "{source_title}" to "{target_title}" '
               f'using the anchor "{rec["anchor_text"]}"')

    plain_summary = (
        f'{headline}. {where}. Why this spot: {placement_reason} '
        f'SEO value: {seo_val}. Business value: {biz_val}. {risk_val}.'
    )
    if rec.get("risk_reason"):
        plain_summary += f' Note: {rec["risk_reason"]}.'

    return ReviewNote(
        recommendation_id=rec["recommendation_id"],
        headline=headline,
        why=why,
        where=where,
        placement_reason=placement_reason,
        anchor=rec["anchor_text"],
        relationship=relationship,
        seo_value=seo_val,
        business_value=biz_val,
        risk=risk_val,
        plain_summary=plain_summary,
    )
