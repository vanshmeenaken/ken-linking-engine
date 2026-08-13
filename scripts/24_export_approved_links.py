"""Manual deployment export (master PRD MVP capability, section 17): turn
editorially-approved link recommendations into a CSV the web team can apply
by hand, since this system has no live CMS write access (Phase 4, not built).

Only recommendations with status='approved' are exported - the human
approval recorded via PATCH /api/recommendations/{id} (Agent 11's review
note is what the editor reads to decide). Nothing here approves anything;
this only packages decisions already made.

Usage:
    python scripts/24_export_approved_links.py
    python scripts/24_export_approved_links.py --out reports/my_export.csv
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.agent_11_editorial_review import build_review_note

DB_PATH = "ken_links.db"

COLUMNS = [
    "recommendation_id", "source_url", "target_url", "anchor_text",
    "placement_type", "placement_section", "suggested_sentence",
    # the ready-to-paste rewrite: the existing sentence with the anchor woven
    # in (scripts/36, LLM with template fallback), plus which path produced it
    "woven_sentence", "woven_sentence_source", "proposed_sentence",
    "relationship_type", "relationship_class", "market_match_score",
    "technology_match_score", "link_score", "score_band", "approved_by",
    "recommendation_reason", "editorial_note", "updated_at",
]


def export_approved_links(db_path: str, out_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT lr.*, s.title AS source_title, t.title AS target_title
           FROM link_recommendations lr
           JOIN content_nodes s ON s.node_id = lr.source_node_id
           JOIN content_nodes t ON t.node_id = lr.target_node_id
           WHERE lr.status = 'approved'
           ORDER BY lr.link_score DESC"""
    ).fetchall()
    conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for row in rows:
            rec = dict(row)
            note = build_review_note(
                rec, rec.get("source_title", ""), rec.get("target_title", ""))
            values = []
            for column in COLUMNS:
                if column == "editorial_note":
                    values.append(note.plain_summary)
                else:
                    values.append(rec.get(column, ""))
            writer.writerow(values)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=DB_PATH)
    parser.add_argument(
        "--out", default=None,
        help="Output CSV path (default: reports/approved_links_export_<timestamp>.csv)")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path(
        f"reports/approved_links_export_{time.strftime('%Y%m%d_%H%M%S')}.csv")

    count = export_approved_links(args.db_path, out_path)
    if count == 0:
        print(f"No approved recommendations yet. Wrote an empty file to {out_path}.")
        print("Approve links via PATCH /api/recommendations/{id} or the dashboard first.")
    else:
        print(f"Exported {count} approved link(s) to {out_path}")


if __name__ == "__main__":
    main()
