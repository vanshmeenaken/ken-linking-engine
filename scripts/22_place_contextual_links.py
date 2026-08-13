"""Enrich link recommendations with real contextual placement and varied anchors.

Two PRD-mandated improvements applied in one pass over the existing
recommendations:

  1. Contextual placement (PRD 18.6 placement priority #1: relevant body
     paragraph), using the vector-search foundation (analysis/vector_store.py)
     as the PRIMARY ranking method, with the geography-excluded keyword method
     as a fallback for short paragraphs where TF-IDF vectors are too sparse to
     score well. Reads each source page's body, finds the sentence where the
     target genuinely belongs, and stores it as suggested_sentence with
     placement_type='contextual_body'. Paragraph text and vectors are persisted
     to paragraph_embeddings so a future run does not need to recrawl or
     re-embed. Successfully crawled links with no genuine contextual home go to
     placement_type='related_reports_block' (an end-of-page block, like Search
     Engine Journal's "Suggested Articles"), never forced into an unrelated
     sentence. A crawl failure leaves the planned placement untouched and marks
     placement_status='unresolved' for a later retry.

  2. Anchor variation (PRD 18.4: no single exact-match anchor should dominate).
     When several pages link to the same target, their anchors are rotated
     from that target's anchor bank (Agent 7) so they are not all identical.

Read-only crawl of the source pages (the ones that have recommendations).
Idempotent: re-running recomputes placement and anchors from scratch.

Usage:
    python scripts/22_place_contextual_links.py --dry-run
    python scripts/22_place_contextual_links.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid

from agents.agent_9_section_purpose import (EXCLUDED_PLACEMENT_PURPOSES,
                                            classify_heading)
from agents.agent_10_seo_validation import SEOValidationAgent
from analysis.anchor_text import pick_anchor_for_context
from analysis.contextual_placement import (_normalise_sentence, best_placement,
                                          best_placement_semantic, fetch_sections,
                                          subject_text, target_keywords)
from analysis.sentence_composer import compose_link_sentence
from analysis.vector_store import VectorStore

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "ken_links.db"

PLACEMENT_SECTION = {  # fallback label when the matched paragraph has no heading
    "same_market": "Market Overview",
    "adjacent_market": "Related Markets",
    "country_region": "Regional Coverage",
    "global_local": "Global Context",
    "report_article_support": "Supporting Analysis",
    "case_study_support": "Case Study Evidence",
}

# When no single sentence matches, recommend the page's most fitting REAL
# section for a manual mention (Agent 9 purposes, best first per relationship).
SECTION_PREFS = {
    "same_market": ("regional", "market_size", "overview"),
    "global_local": ("regional", "overview", "market_size"),
    "adjacent_market": ("industry_analysis", "overview", "segmentation"),
    "country_region": ("regional", "overview"),
    "report_article_support": ("industry_analysis", "overview"),
    "case_study_support": ("competitive", "market_size", "industry_analysis"),
}


def best_section_for(sections: list[dict], relationship_type: str) -> str | None:
    """The heading of the page's best real section for this link, or None.

    Only sections with actual prose (paragraphs) qualify - recommending an
    empty section would be as dishonest as forcing a sentence.
    """
    prefs = SECTION_PREFS.get(relationship_type, ("overview",))
    for wanted in prefs:
        for sec in sections:
            if sec["purpose"] == wanted and sec["n_paras"] > 0 and sec["heading"]:
                return sec["heading"]
    return None


def anchor_options(bank: sqlite3.Row) -> list[str]:
    """Ordered, de-duplicated anchor choices for a target, primary first."""
    if bank is None:
        return []
    out, seen = [], set()
    def add(vals):
        for v in vals:
            if v and v.lower() not in seen:
                seen.add(v.lower()); out.append(v)
    add([bank["primary_anchor"]])
    for col in ("secondary_anchors", "long_tail_anchors",
                "market_specific_anchors", "country_specific_anchors"):
        add(json.loads(bank[col]) if bank[col] else [])
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    db_path = Path(args.db)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    recs = conn.execute(
        """SELECT r.recommendation_id, r.source_node_id, r.target_node_id,
                  r.relationship_type, r.link_score, r.anchor_text,
                  r.placement_type AS current_placement_type,
                  r.placement_section AS current_placement_section,
                  r.suggested_sentence AS current_suggested_sentence,
                  r.validation_status AS current_validation_status,
                  r.risk_flag AS current_risk_flag,
                  r.risk_reason AS current_risk_reason,
                  s.url AS source_url,
                  t.market AS t_market, t.country AS t_country,
                  t.region AS t_region, t.title AS t_title
           FROM link_recommendations r
           JOIN content_nodes s ON s.node_id = r.source_node_id
           JOIN content_nodes t ON t.node_id = r.target_node_id
           WHERE r.status='pending'
             AND COALESCE(r.placement_status, 'planned') != 'confirmed'
           ORDER BY r.source_node_id, r.link_score DESC"""
    ).fetchall()

    if not recs:
        print("No unresolved/planned pending placements to process.")
        conn.close()
        return 0

    # ── crawl each distinct source page once (with real section structure) ───
    source_urls = {r["source_node_id"]: r["source_url"] for r in recs}
    paragraphs: dict[str, list[str]] = {}
    para_heading: dict[str, list[str | None]] = {}  # aligned with paragraphs
    page_sections: dict[str, list[dict]] = {}
    unresolved_sources: set[str] = set()
    print(f"Crawling {len(source_urls)} source pages for body text...")
    placeable: dict[str, list[str]] = {}          # paragraphs links may live in
    placeable_heading: dict[str, list[str | None]] = {}  # aligned headings
    for i, (nid, url) in enumerate(source_urls.items(), 1):
        try:
            sections = fetch_sections(url)
            paragraphs[nid] = [p for s in sections for p in s["paragraphs"]]
            para_heading[nid] = [s["heading"] for s in sections
                                 for _ in s["paragraphs"]]
            page_sections[nid] = [
                {"heading": s["heading"], "purpose": classify_heading(s["heading"]),
                 "n_paras": len(s["paragraphs"])} for s in sections]
            # contextual links may only be placed in content sections - never
            # in author bios, FAQs, TOCs, CTAs and similar structural areas
            placeable[nid], placeable_heading[nid] = [], []
            for s in sections:
                if classify_heading(s["heading"]) in EXCLUDED_PLACEMENT_PURPOSES:
                    continue
                for p in s["paragraphs"]:
                    placeable[nid].append(p)
                    placeable_heading[nid].append(s["heading"])
            if not paragraphs[nid]:
                unresolved_sources.add(nid)
                print(f"  [{i}] unresolved {url.split('/')[-1]}: no usable body text")
        except Exception as exc:
            paragraphs[nid] = []
            para_heading[nid] = []
            page_sections[nid] = []
            placeable[nid] = []
            placeable_heading[nid] = []
            unresolved_sources.add(nid)
            print(f"  [{i}] skip {url.split('/')[-1]}: {exc}")
        time.sleep(0.3)  # be polite to the server
    print("  done.\n")

    # ── decide placement per recommendation: vector first, keyword fallback ──
    updates = []
    contextual = weak_paragraphs = related = 0
    by_method = {"vector": 0, "keyword": 0}
    # Two links from the SAME source page must never land in the identical
    # sentence - reusing one sentence for two different targets reads as
    # duplicated spam on the live page. recs is ordered by source_node_id
    # then link_score DESC, so the stronger link claims a sentence first and
    # weaker ones from the same page are pushed to their next-best DISTINCT
    # sentence (or a distinct weak match, never the same one twice).
    # Seeded with sentences already claimed by APPROVED/deployed contextual
    # links per source, so a pending sibling steers away from those too -
    # this script never touches an approved row's placement, but a pending
    # row re-placed without this seed would still collide with it.
    used_sentences: dict[str, set[str]] = {}
    for row in conn.execute(
            """SELECT source_node_id, suggested_sentence
               FROM link_recommendations
               WHERE status IN ('approved', 'deployed')
                 AND placement_type = 'contextual_body'
                 AND suggested_sentence IS NOT NULL"""):
        used_sentences.setdefault(row["source_node_id"], set()).add(
            _normalise_sentence(row["suggested_sentence"]))
    for r in recs:
        nid = r["source_node_id"]
        if nid in unresolved_sources:
            updates.append({
                "id": r["recommendation_id"],
                "source": nid,
                "target": r["target_node_id"],
                "score": r["link_score"],
                "placement_type": r["current_placement_type"],
                "placement_section": r["current_placement_section"],
                "suggested_sentence": r["current_suggested_sentence"],
                "placement_status": "unresolved",
                "validation_status": r["current_validation_status"],
                "risk_flag": r["current_risk_flag"],
                "risk_reason": r["current_risk_reason"],
            })
            continue
        page_paras = placeable.get(nid, [])
        query = subject_text(r["t_market"], r["t_title"])
        claimed = used_sentences.setdefault(nid, set())
        placed = best_placement_semantic(page_paras, query,
                                         exclude_sentences=claimed)
        method = "vector"
        if placed is None:
            kws = target_keywords(r["t_market"], r["t_country"], r["t_region"], r["t_title"])
            placed = best_placement(page_paras, kws, exclude_sentences=claimed)
            method = "keyword"
        if placed:
            # tag the REAL section the matched paragraph sits under; the old
            # static relationship-type label is only a fallback for headingless
            # intro paragraphs
            ptype, sentence = "contextual_body", placed["sentence"]
            headings = placeable_heading.get(nid, [])
            idx = placed["paragraph_index"]
            real = headings[idx] if idx < len(headings) else None
            section = real or PLACEMENT_SECTION.get(
                r["relationship_type"], "Market Overview")
            contextual += 1
            by_method[method] += 1
        else:
            # No STRONG sentence match. The generic Related Reports block is
            # not an acceptable default (the site may drop that section), so
            # name the best AVAILABLE paragraph instead - honestly labelled
            # as a weak match for the editor to judge. Related-block survives
            # only for pages with no usable paragraphs at all.
            weak = best_placement_semantic(page_paras, query, min_score=0.0,
                                           exclude_sentences=claimed)
            if weak:
                # suggested_sentence = the existing line the placement anchors
                # to; proposed_sentence (set below, after anchors rotate) = a
                # composed, claim-free sentence carrying the anchor, to be
                # inserted right after that line
                ptype, sentence = "best_available_paragraph", weak["sentence"]
                headings = placeable_heading.get(nid, [])
                idx = weak["paragraph_index"]
                real = headings[idx] if idx < len(headings) else None
                section = real or best_section_for(
                    page_sections.get(nid, []), r["relationship_type"]) \
                    or PLACEMENT_SECTION.get(r["relationship_type"],
                                             "Market Overview")
                weak_paragraphs += 1
            else:
                ptype, sentence = "related_reports_block", None
                real_related = next(
                    (s["heading"] for s in page_sections.get(nid, [])
                     if s["purpose"] == "related_reports" and s["heading"]),
                    None)
                section = real_related or "Related Reports"
                related += 1
        if sentence:
            claimed.add(_normalise_sentence(sentence))
        updates.append({"id": r["recommendation_id"], "source": nid,
                        "target": r["target_node_id"],
                        "relationship_type": r["relationship_type"],
                        "score": r["link_score"], "placement_type": ptype,
                        "placement_section": section, "suggested_sentence": sentence})
        updates[-1]["placement_status"] = "confirmed"

    # ── rotate anchors: vary anchors across inbound links to the same target ──
    by_target: dict[str, list[dict]] = {}
    for u in updates:
        if u["placement_status"] == "confirmed":
            by_target.setdefault(u["target"], []).append(u)
    anchor_assigned = 0
    batch_ids = {u["id"] for u in updates}
    for tid, group in by_target.items():
        bank = conn.execute(
            "SELECT * FROM anchor_banks WHERE target_node_id = ?", (tid,)).fetchone()
        options = anchor_options(bank)
        if not options:
            continue
        # anchors already held by this target's OTHER active rows (approved,
        # deployed, or pending rows outside this batch) are taken - reusing
        # one would recreate the exact duplication this rotation exists to
        # prevent (caught by test_recommendations_have_placement_and_varied_anchors)
        taken = {
            row["anchor_text"].lower()
            for row in conn.execute(
                """SELECT recommendation_id, anchor_text FROM link_recommendations
                   WHERE target_node_id = ? AND status != 'rejected'
                     AND COALESCE(anchor_text, '') != ''""", (tid,))
            if row["recommendation_id"] not in batch_ids
        }
        free = [o for o in options if o.lower() not in taken] or options
        # strongest inbound link picks first; each pick is intent-aware (the
        # variant matching the link's sentence/section goes first) and never
        # repeats an anchor already assigned within this target's group
        group.sort(key=lambda u: -u["score"])
        assigned: set[str] = set()
        for idx, u in enumerate(group):
            ordered = pick_anchor_for_context(
                free, u.get("suggested_sentence"), u.get("placement_section"))
            choice = next((c for c in ordered if c.lower() not in assigned),
                          ordered[idx % len(ordered)])
            assigned.add(choice.lower())
            u["anchor_text"] = choice
            anchor_assigned += 1

    # ── compose ready-to-insert sentences for weak-match placements ──────────
    # done AFTER rotation so the composed sentence carries the FINAL anchor.
    # The sentence is claim-free by construction (analysis/sentence_composer):
    # it points the reader at the target without asserting any market fact.
    composed = 0
    for u in updates:
        if (u["placement_status"] == "confirmed"
                and u["placement_type"] == "best_available_paragraph"
                and u.get("anchor_text")):
            u["proposed_sentence"] = compose_link_sentence(
                u["anchor_text"], u.get("relationship_type", ""))
            composed += 1

    print(f"Contextual placements (in body): {contextual}")
    print(f"  via vector search  : {by_method['vector']}")
    print(f"  via keyword fallback: {by_method['keyword']}")
    print(f"Best-available paragraph (weak match): {weak_paragraphs}")
    print(f"  with composed insert sentence : {composed}")
    print(f"Routed to Related Reports block : {related}")
    print(f"Placement unresolved (crawl/body): {len(unresolved_sources)} source pages")
    print(f"Anchors rotated from bank       : {anchor_assigned}")

    # ── re-validate against the FINAL placement + anchor ─────────────────────
    # Agent 10 ran once already, inside Agent 6, against the placeholder
    # placement_type Agent 6 assigns at generation time. Placement and anchor
    # both changed above (real sentence found, anchor rotated), so the stored
    # risk_flag / risk_reason / validation_status is stale until re-checked
    # against what will actually ship. Without this, an approved-looking
    # recommendation could carry a risk note describing a placement it no
    # longer has.
    validator = SEOValidationAgent(db_path)
    revalidated = {"approved_for_review": 0, "needs_revision": 0, "rejected": 0}
    for u in updates:
        if u["placement_status"] == "unresolved":
            continue
        v = validator.validate(
            u["source"], u["target"], u.get("anchor_text", ""), u["placement_type"])
        u["validation_status"] = v.overall_status
        u["risk_flag"] = ("high" if v.overall_status == "rejected" else
                          "medium" if v.overall_status == "needs_revision" else "low")
        u["risk_reason"] = "; ".join(
            f"{rf.rule}: {rf.description}" for rf in v.risk_flags) or None
        revalidated[v.overall_status] = revalidated.get(v.overall_status, 0) + 1
    print(f"Re-validated against final placement: {revalidated}")

    if args.dry_run:
        print("\nDRY RUN - nothing written. Samples:")
        for u in updates[:6]:
            if u["placement_status"] == "unresolved":
                print(f'  [unresolved] source {u["source"]}')
            elif u["placement_type"] == "contextual_body":
                print(f'  [body] anchor "{u.get("anchor_text","?")}" '
                      f'(section: {u["placement_section"]})')
                print(f'         in: "{u["suggested_sentence"][:110]}..."')
            elif u["placement_type"] == "section_block":
                print(f'  [section] anchor "{u.get("anchor_text","?")}" '
                      f'-> add in section "{u["placement_section"]}"')
            else:
                print(f'  [related-block] anchor "{u.get("anchor_text","?")}"')
        conn.close()
        return 0

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        conn.execute("BEGIN IMMEDIATE")
        for u in updates:
            sets = ["placement_type=?", "placement_section=?",
                    "suggested_sentence=?", "proposed_sentence=?",
                    "placement_status=?", "validation_status=?",
                    "risk_flag=?", "risk_reason=?", "updated_at=?"]
            params = [u["placement_type"], u["placement_section"],
                      u["suggested_sentence"], u.get("proposed_sentence"),
                      u["placement_status"], u["validation_status"],
                      u["risk_flag"], u["risk_reason"], now]
            if "anchor_text" in u:
                sets.append("anchor_text=?"); params.append(u["anchor_text"])
            # a link the final validation rejects must never sit as 'pending'
            if u["validation_status"] == "rejected":
                sets.append("status=?"); params.append("rejected")
            params.append(u["id"])
            conn.execute(f"UPDATE link_recommendations SET {', '.join(sets)} "
                         "WHERE recommendation_id=?", params)

        # Persist crawled paragraphs + their vectors (paragraph_embeddings), so
        # a future run/search can reuse them without recrawling or re-embedding.
        para_rows = 0
        for nid, paras in paragraphs.items():
            if not paras:
                continue
            store = VectorStore.fit([(str(i), p) for i, p in enumerate(paras)])
            for i, p in enumerate(paras):
                vec = store._vectors[str(i)]
                conn.execute(
                    """INSERT INTO paragraph_embeddings
                       (paragraph_id, node_id, paragraph_index, paragraph_text,
                        embedding_model, embedding_vector, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT (node_id, paragraph_index) DO UPDATE SET
                           paragraph_text=excluded.paragraph_text,
                           embedding_vector=excluded.embedding_vector,
                           updated_at=excluded.updated_at""",
                    (str(uuid.uuid4()), nid, i, p, "tfidf-v1",
                     json.dumps(vec), now, now),
                )
                para_rows += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    conn.close()
    print(f"Paragraph vectors stored          : {para_rows}")
    print("\nDatabase update: committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
