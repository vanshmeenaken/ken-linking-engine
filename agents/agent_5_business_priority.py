"""Agent 5 — Business Priority (master PRD §23, Phase 2 foundation).

Scores every active page's commercial priority and writes the High/Medium/Low
band to content_nodes.business_priority (master PRD §23.2). The band drives how
aggressively later phases push internal links to a page: High = push from
authority pages, Medium = normal contextual links, Low = only where highly
relevant.

Master PRD §23.1 lists many inputs (revenue potential, report sales priority,
consulting/survey/expert-panel/procurement relevance, industry priority,
country priority, sales-team demand, search demand, lead-conversion
potential). Most need business data this project doesn't have yet, so they are
CONFIGURABLE PLACEHOLDER WEIGHTS (config below) — real values plug in later
without touching the model. The factors computable now from Phase 1/2 data:

    content_type / intent   report(decision) > case_study(consideration) > article(awareness)
    page authority          normalized 0-1
    search opportunity      Agent 4's search_opportunity_score (bigger SEO gap = more to gain)
    industry priority       configurable; MVP-scope industries weighted up (§31.2)
    country priority        configurable; MVP-scope geographies weighted up (§31.2)

Usage:
    python agents/agent_5_business_priority.py --dry-run
    python agents/agent_5_business_priority.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"

# ── Factor weights (sum = 1.0). All computable now. ──────────────────────────
# Deliberately excludes search_opportunity_score: that measures an SEO GAP,
# not commercial value. Mixing it in made every orphan look "high business
# priority" (0 pages landed in Low). Business value and SEO opportunity are
# separate axes — Agent 6's link score (master PRD §17) combines them
# explicitly (8% business value + 5% crawl priority + ...). Keeping them
# separate here keeps each signal honest.
WEIGHTS = {
    "intent": 0.35,          # commercial intent of the content type
    "authority": 0.25,       # existing page authority (proxy for established value)
    "industry_priority": 0.20,
    "country_priority": 0.20,
}

INTENT_SCORE = {"decision": 1.0, "consideration": 0.6, "awareness": 0.3}

# ── CONFIGURABLE PLACEHOLDERS (master PRD §23.1 / MVP scope §31.2) ────────────
# Real business inputs (revenue, sales/search demand, lead conversion) are not
# available yet; these stand in and are trivially editable when they are.
# MVP-scope industries and geographies (§31.2) are weighted up; everything
# else gets a neutral baseline so no page is zeroed out.
BASELINE_PRIORITY = 0.5
INDUSTRY_PRIORITY = {
    "Healthcare": 1.0,
    "Automotive, Transportation & Logistics": 1.0,
    "Technology & Telecom": 1.0,
}
COUNTRY_PRIORITY = {
    "india": 1.0, "saudi arabia": 1.0, "uae": 1.0,
}

# Business-data-dependent inputs, kept as named placeholders so the model
# documents exactly what's missing rather than silently omitting it.
BUSINESS_DATA_PLACEHOLDERS = {
    "revenue_potential": None, "report_sales_priority": None,
    "consulting_relevance": None, "survey_relevance": None,
    "expert_panel_relevance": None, "procurement_relevance": None,
    "sales_team_demand": None, "search_demand": None,
    "lead_conversion_potential": None,
}


def band(score: float) -> str:
    return "High" if score >= 0.66 else "Medium" if score >= 0.4 else "Low"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    nodes = conn.execute(
        "SELECT node_id, industry, country, intent_stage, page_authority_score "
        "FROM content_nodes WHERE status='active'"
    ).fetchall()
    max_auth = max((n["page_authority_score"] or 0 for n in nodes), default=0) or 1.0

    now = datetime.now(timezone.utc).isoformat()
    bands = {"High": 0, "Medium": 0, "Low": 0}
    updates = []
    for n in nodes:
        f_intent = INTENT_SCORE.get(n["intent_stage"] or "", 0.3)
        f_auth = (n["page_authority_score"] or 0) / max_auth
        f_ind = INDUSTRY_PRIORITY.get(n["industry"] or "", BASELINE_PRIORITY)
        f_country = COUNTRY_PRIORITY.get((n["country"] or "").lower(), BASELINE_PRIORITY)
        score = round(
            WEIGHTS["intent"] * f_intent
            + WEIGHTS["authority"] * f_auth
            + WEIGHTS["industry_priority"] * f_ind
            + WEIGHTS["country_priority"] * f_country, 3
        )
        b = band(score)
        bands[b] += 1
        updates.append((b, now, n["node_id"]))

    if not args.dry_run:
        conn.executemany(
            "UPDATE content_nodes SET business_priority=?, updated_at=? WHERE node_id=?",
            updates,
        )
        conn.commit()
    conn.close()

    print(f"Pages processed: {len(nodes)}")
    print(f"Business priority bands: {bands}")
    print(f"Placeholder business inputs (documented, not yet fed): "
          f"{list(BUSINESS_DATA_PLACEHOLDERS)}")
    print("Dry run — nothing written." if args.dry_run else "Committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
