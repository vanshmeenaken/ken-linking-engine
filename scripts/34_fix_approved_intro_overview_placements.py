"""One-off correction: move already-APPROVED links out of the intro/overview
sections banned by the 2026-08-13 editorial rule (scripts/22).

scripts/22 never rewrites an approved row's placement - by design, since a
machine rebuild must not overwrite a human decision. That correctly left 26
approved links sitting in the exact spots the new rule bans (the report's
own opening hero stat or its Market Overview section). Shrey reviewed one
live on the site and explicitly authorized fixing these: "if I have
approved any of the such link in such places than that is wrong please
correct them."

This script touches PLACEMENT ONLY for the affected approved rows:
  - status stays 'approved', approved_by stays whoever approved it
  - anchor_text is left untouched (the human approved that anchor)
  - placement_type / placement_section / suggested_sentence /
    proposed_sentence / placement_status / validation_status / risk_flag /
    risk_reason are recomputed against the SAME rules scripts/22 uses:
    NEVER_CROSS_REPORT_LINK_PURPOSES excluded, and the sentence-collision
    guard (a source page's other active links, approved or pending, are
    treated as already-claimed so this pass never creates a NEW duplicate).

Pending/rejected rows and every other approved row are untouched.

Usage:
    python scripts/34_fix_approved_intro_overview_placements.py --dry-run
    python scripts/34_fix_approved_intro_overview_placements.py
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agent_9_section_purpose import (NEVER_CROSS_REPORT_LINK_PURPOSES,
                                            classify_heading)
from agents.agent_10_seo_validation import SEOValidationAgent
from analysis.contextual_placement import (_normalise_sentence, best_placement, is_boilerplate,
                                          best_placement_semantic, fetch_sections,
                                          subject_text, target_keywords)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "ken_links.db"

PLACEMENT_SECTION_FALLBACK = {
    "same_market": "Market Overview",
    "adjacent_market": "Related Markets",
    "country_region": "Regional Coverage",
    "global_local": "Global Context",
    "report_article_support": "Supporting Analysis",
    "case_study_support": "Case Study Evidence",
}


def find_offenders(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Approved contextual links whose CURRENT placement breaks a rule the
    pipeline now enforces: a banned section (the report's own hero stat or
    Market Overview), or a sentence since recognised as boilerplate
    (company pitch, catalogue promo, or a template section-descriptor blurb
    repeated verbatim across many report pages)."""
    rows = conn.execute(
        """SELECT recommendation_id, source_node_id, target_node_id,
                  relationship_type, anchor_text, placement_section,
                  suggested_sentence, placement_status
           FROM link_recommendations
           WHERE status = 'approved' AND placement_type = 'contextual_body'"""
    ).fetchall()
    offenders = []
    for r in rows:
        section = conn.execute(
            "SELECT purpose FROM section_purpose_map WHERE node_id=? AND heading=?",
            (r["source_node_id"], r["placement_section"])).fetchone()
        purpose = section["purpose"] if section else "intro"
        # an approved row left 'unresolved' by an earlier pass (transient
        # crawl failure, e.g. a 503 from the live site) still needs a real
        # placement - re-running this script is the retry path
        if (purpose in ("intro", "overview")
                or is_boilerplate(r["suggested_sentence"] or "")
                or r["placement_status"] == "unresolved"):
            offenders.append(r)
    return offenders


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    db_path = Path(args.db)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    offenders = find_offenders(conn)
    if not offenders:
        print("No approved links sit in intro/overview. Nothing to do.")
        conn.close()
        return 0
    print(f"Approved links needing a new placement: {len(offenders)}")

    # target details for the search query, and each affected source's URL
    target_ids = {r["target_node_id"] for r in offenders}
    targets = {row["node_id"]: row for row in conn.execute(
        f"""SELECT node_id, market, country, region, title FROM content_nodes
           WHERE node_id IN ({','.join('?' * len(target_ids))})""",
        list(target_ids))}
    source_ids = {r["source_node_id"] for r in offenders}
    sources = {row["node_id"]: row["url"] for row in conn.execute(
        f"""SELECT node_id, url FROM content_nodes
           WHERE node_id IN ({','.join('?' * len(source_ids))})""",
        list(source_ids))}

    # every OTHER active link from an affected source already claims its
    # sentence, so the fix can never create a fresh duplicate
    claimed: dict[str, set[str]] = {}
    for row in conn.execute(
            """SELECT source_node_id, suggested_sentence FROM link_recommendations
               WHERE status != 'rejected' AND placement_type = 'contextual_body'
                 AND suggested_sentence IS NOT NULL"""):
        claimed.setdefault(row["source_node_id"], set()).add(
            _normalise_sentence(row["suggested_sentence"]))

    validator = SEOValidationAgent(db_path)
    updates, unresolved, failures = [], [], []
    for i, off in enumerate(offenders, 1):
        nid = off["source_node_id"]
        url = sources[nid]
        target = targets[off["target_node_id"]]
        print(f"  [{i}/{len(offenders)}] {url.split('/')[-1]}")
        try:
            sections = fetch_sections(url)
        except Exception as exc:
            unresolved.append((off["recommendation_id"], f"crawl failed: {exc}"))
            continue
        placeable, placeable_heading = [], []
        for s in sections:
            if classify_heading(s["heading"]) in NEVER_CROSS_REPORT_LINK_PURPOSES:
                continue
            for p in s["paragraphs"]:
                placeable.append(p)
                placeable_heading.append(s["heading"])
        if not placeable:
            # a genuinely empty-shell page (same category as the earlier
            # "no usable body text" pages) - honestly unresolved, never left
            # silently sitting in the now-banned intro/overview spot
            unresolved.append((off["recommendation_id"], "page has no eligible paragraphs"))
            continue

        query = subject_text(target["market"], target["title"])
        exclude = claimed.setdefault(nid, set())
        placed = best_placement_semantic(placeable, query, exclude_sentences=exclude)
        if placed is None:
            kws = target_keywords(target["market"], target["country"],
                                  target["region"], target["title"])
            placed = best_placement(placeable, kws, exclude_sentences=exclude)
        if placed is None:
            placed = best_placement_semantic(placeable, query, min_score=0.0,
                                             exclude_sentences=exclude)
        if placed is None:
            unresolved.append((off["recommendation_id"],
                              "no distinct paragraph found even at weak match"))
            continue

        sentence = placed["sentence"]
        idx = placed["paragraph_index"]
        section = placeable_heading[idx] or PLACEMENT_SECTION_FALLBACK.get(
            off["relationship_type"], "Market Overview")
        exclude.add(_normalise_sentence(sentence))

        v = validator.validate(nid, off["target_node_id"],
                               off["anchor_text"], "contextual_body")
        updates.append({
            "id": off["recommendation_id"], "section": section,
            "sentence": sentence,
            "validation_status": v.overall_status,
            "risk_flag": ("high" if v.overall_status == "rejected" else
                         "medium" if v.overall_status == "needs_revision" else "low"),
            "risk_reason": "; ".join(
                f"{rf.rule}: {rf.description}" for rf in v.risk_flags) or None,
        })
        print(f'      -> "{section}": {sentence[:90]}...')

    print(f"\nFixed with a real sentence: {len(updates)}   "
          f"Marked unresolved (needs retry/manual review): {len(unresolved)}")
    for rec_id, reason in unresolved:
        print(f"  UNRESOLVED {rec_id}: {reason}")
    still_rejected = [u for u in updates if u["validation_status"] == "rejected"]
    if still_rejected:
        print(f"\nWARNING: {len(still_rejected)} re-validated as REJECTED at "
              "their new spot. Status is left 'approved' - review manually:")
        for u in still_rejected:
            print(f"  {u['id']}: {u['risk_reason']}")

    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        conn.close()
        return 0

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        conn.execute("BEGIN IMMEDIATE")
        for u in updates:
            conn.execute(
                """UPDATE link_recommendations
                   SET placement_section=?, suggested_sentence=?,
                       placement_status='confirmed', validation_status=?,
                       risk_flag=?, risk_reason=?, updated_at=?
                   WHERE recommendation_id=?""",
                (u["section"], u["sentence"], u["validation_status"],
                 u["risk_flag"], u["risk_reason"], now, u["id"]))
        for rec_id, reason in unresolved:
            conn.execute(
                """UPDATE link_recommendations
                   SET placement_status='unresolved', suggested_sentence=NULL,
                       risk_flag='medium', risk_reason=?, updated_at=?
                   WHERE recommendation_id=?""",
                (f"placement needs manual review: {reason}", now, rec_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    conn.close()
    print("\nDatabase update: committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
