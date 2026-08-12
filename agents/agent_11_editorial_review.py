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
from dataclasses import dataclass

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


@dataclass
class ReviewNote:
    recommendation_id: str
    headline: str
    why: str
    where: str
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

    why = (f'Recommended with a score of {rec["link_score"]:.0f} out of 100 '
          f'({rec["score_band"]}). {relationship}')

    headline = (f'Link "{source_title}" to "{target_title}" '
               f'using the anchor "{rec["anchor_text"]}"')

    plain_summary = (
        f'{headline}. {where}. '
        f'SEO value: {seo_val}. Business value: {biz_val}. {risk_val}.'
    )
    if rec.get("risk_reason"):
        plain_summary += f' Note: {rec["risk_reason"]}.'

    return ReviewNote(
        recommendation_id=rec["recommendation_id"],
        headline=headline,
        why=why,
        where=where,
        anchor=rec["anchor_text"],
        relationship=relationship,
        seo_value=seo_val,
        business_value=biz_val,
        risk=risk_val,
        plain_summary=plain_summary,
    )
