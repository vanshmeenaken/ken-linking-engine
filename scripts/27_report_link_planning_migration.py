"""Add report-level link planning and placement verification fields."""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

RECOMMENDATION_COLUMNS = {
    "placement_status": "TEXT DEFAULT 'planned'",
    "plan_category": "TEXT",
    "source_plan_rank": "INTEGER",
}

PLAN_TABLE = """
CREATE TABLE IF NOT EXISTS report_link_plans (
    report_node_id TEXT PRIMARY KEY REFERENCES content_nodes(node_id),
    report_url TEXT NOT NULL,
    existing_outgoing_links INTEGER DEFAULT 0,
    minimum_outgoing_links INTEGER DEFAULT 10,
    maximum_outgoing_links INTEGER DEFAULT 25,
    recommended_outgoing_links INTEGER DEFAULT 0,
    approved_outgoing_links INTEGER DEFAULT 0,
    pending_outgoing_links INTEGER DEFAULT 0,
    incoming_opportunities INTEGER DEFAULT 0,
    total_opportunities INTEGER DEFAULT 0,
    projected_outgoing_links INTEGER DEFAULT 0,
    remaining_gap INTEGER DEFAULT 0,
    remaining_capacity INTEGER DEFAULT 0,
    regional_report_opportunities INTEGER DEFAULT 0,
    adjacent_report_opportunities INTEGER DEFAULT 0,
    supporting_content_opportunities INTEGER DEFAULT 0,
    hub_opportunities INTEGER DEFAULT 0,
    plan_status TEXT,
    opportunity_status TEXT,
    gap_reason TEXT,
    created_at TEXT,
    updated_at TEXT
)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_report_link_plans_status "
    "ON report_link_plans(plan_status)",
    "CREATE INDEX IF NOT EXISTS ix_report_link_plans_opportunity_status "
    "ON report_link_plans(opportunity_status)",
]


def migrate(db_path: Path) -> tuple[Path | None, list[str]]:
    conn = sqlite3.connect(db_path)
    changes: list[str] = []
    try:
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(link_recommendations)")
        }
        missing = [
            (name, definition)
            for name, definition in RECOMMENDATION_COLUMNS.items()
            if name not in existing
        ]
        plan_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='report_link_plans'"
        ).fetchone() is not None
        if not missing and plan_exists:
            for statement in INDEXES:
                conn.execute(statement)
            conn.commit()
            return None, []

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(
            f"{db_path.stem}_backup_report_planning_{stamp}.db"
        )
        shutil.copy2(db_path, backup)

        for name, definition in missing:
            conn.execute(
                f"ALTER TABLE link_recommendations ADD COLUMN {name} {definition}"
            )
            changes.append(f"link_recommendations.{name}")
        if not plan_exists:
            conn.execute(PLAN_TABLE)
            changes.append("report_link_plans")
        for statement in INDEXES:
            conn.execute(statement)
        conn.execute(
            """UPDATE link_recommendations
               SET placement_status = CASE
                   WHEN placement_type='contextual_body'
                        AND COALESCE(suggested_sentence, '') != '' THEN 'confirmed'
                   WHEN placement_type IN
                        ('related_reports_block', 'hub_link', 'evidence_block')
                        THEN 'confirmed'
                   ELSE 'planned'
               END
               WHERE placement_status IS NULL OR placement_status='planned'"""
        )
        conn.commit()
        return backup, changes
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    backup, changes = migrate(Path(args.db))
    if changes:
        print(f"Backup: {backup}")
        print("Added: " + ", ".join(changes))
    else:
        print("Schema already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
