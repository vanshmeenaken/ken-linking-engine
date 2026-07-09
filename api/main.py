import sqlite3
import os
import sys
import time
from dataclasses import asdict
from typing import Optional

# Must run before any project-local import (config, agents) — when this file
# is executed directly (`python api/main.py`, not `-m`), Python only puts
# api/'s own directory on sys.path, not the project root, so those imports
# fail. pytest masked this bug (it sets rootdir on sys.path itself).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from config.settings import API_HOST, API_PORT
from agents.agent_10_seo_validation import SEOValidationAgent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "ken_links.db")
DASHBOARD_PATH = os.path.join(ROOT, "dashboard", "index.html")

app = FastAPI(
    title="Ken Intelligence Linking Engine",
    description="Phase 1: Foundation & Data Layer",
    version="1.0.0",
)


def get_db():
    """Open a new sqlite3 connection to ken_links.db with row-as-dict access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── 1. Health check ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health check — confirms the API process is up and reachable."""
    return {"status": "ok", "message": "Ken Intelligence Linking Engine Phase 1"}


# ── Human-friendly dashboard (no raw JSON) ───────────────────────────────────

@app.get("/dashboard")
def dashboard():
    """Serve the self-contained visual dashboard (dashboard/index.html)."""
    return FileResponse(DASHBOARD_PATH)


# ── 2. Database statistics ───────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    """Return top-level summary metrics: totals, orphan count, link/authority averages."""
    start = time.time()
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM content_nodes").fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status = 'active'"
    ).fetchone()[0]
    orphan = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE orphan_status = 'orphan'"
    ).fetchone()[0]
    avg_links = conn.execute(
        "SELECT ROUND(AVG(internal_links_in), 2) FROM content_nodes"
    ).fetchone()[0] or 0.0
    avg_authority = conn.execute(
        "SELECT ROUND(AVG(page_authority_score), 2) FROM content_nodes "
        "WHERE page_authority_score IS NOT NULL"
    ).fetchone()[0] or 0.0

    conn.close()
    return {
        "total_pages": total,
        "active_pages": active,
        "orphan_pages": orphan,
        "avg_links_in": avg_links,
        "avg_authority_score": avg_authority,
        "response_time_ms": round((time.time() - start) * 1000, 1),
    }


# ── 2b. Detailed metrics ─────────────────────────────────────────────────────

@app.get("/api/metrics")
def get_metrics():
    """Return the full database breakdown: content types, industries, countries,
    incoming/outgoing link distribution, and orphan-status analysis."""
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM content_nodes").fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status = 'active'"
    ).fetchone()[0]

    content_types = {
        row["content_type"]: row["n"]
        for row in conn.execute(
            """SELECT COALESCE(NULLIF(content_type,''), 'unknown') AS content_type,
                      COUNT(*) AS n
               FROM content_nodes GROUP BY content_type ORDER BY n DESC"""
        )
    }
    industries = {
        row["industry"]: row["n"]
        for row in conn.execute(
            """SELECT industry, COUNT(*) AS n FROM content_nodes
               WHERE industry IS NOT NULL AND industry != ''
               GROUP BY industry ORDER BY n DESC"""
        )
    }
    countries = {
        row["country"]: row["n"]
        for row in conn.execute(
            """SELECT country, COUNT(*) AS n FROM content_nodes
               WHERE country IS NOT NULL AND country != ''
               GROUP BY country ORDER BY n DESC"""
        )
    }

    link_row = conn.execute(
        """SELECT ROUND(AVG(internal_links_in),2) AS avg_in,
                  MIN(internal_links_in) AS min_in,
                  MAX(internal_links_in) AS max_in,
                  ROUND(AVG(internal_links_out),2) AS avg_out,
                  MIN(internal_links_out) AS min_out,
                  MAX(internal_links_out) AS max_out
           FROM content_nodes"""
    ).fetchone()
    link_distribution = {
        "internal_links_in": {
            "avg": link_row["avg_in"], "min": link_row["min_in"], "max": link_row["max_in"],
        },
        "internal_links_out": {
            "avg": link_row["avg_out"], "min": link_row["min_out"], "max": link_row["max_out"],
        },
    }

    orphan_analysis = {
        row["orphan_status"]: row["n"]
        for row in conn.execute(
            """SELECT COALESCE(NULLIF(orphan_status,''), 'unknown') AS orphan_status,
                      COUNT(*) AS n
               FROM content_nodes GROUP BY orphan_status ORDER BY n DESC"""
        )
    }
    orphan_analysis["orphan_percent"] = round(
        100.0 * orphan_analysis.get("orphan", 0) / total, 1
    ) if total else 0.0

    conn.close()
    return {
        "total_pages": total,
        "active_pages": active,
        "content_types": content_types,
        "industries": industries,
        "countries": countries,
        "link_distribution": link_distribution,
        "orphan_analysis": orphan_analysis,
    }


# ── 3. List all pages (paginated) ────────────────────────────────────────────

@app.get("/api/pages")
def list_pages(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    country: Optional[str] = Query(None, description="Filter by country"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    search: Optional[str] = Query(None, description="Search term matched against URL and title"),
):
    """List pages, paginated and optionally filtered by industry, country,
    content_type (all case-insensitive exact match) and/or a search substring
    matched against URL and title. Ordered by page_authority_score descending."""
    conn = get_db()
    where_clauses = []
    params: list = []

    if industry:
        where_clauses.append("LOWER(industry) = LOWER(?)")
        params.append(industry)
    if country:
        where_clauses.append("LOWER(country) = LOWER(?)")
        params.append(country)
    if content_type:
        where_clauses.append("LOWER(content_type) = LOWER(?)")
        params.append(content_type)
    if search:
        where_clauses.append("(url LIKE ? OR title LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) FROM content_nodes {where_sql}", params
    ).fetchone()
    total_count = count_row[0]

    rows = conn.execute(
        f"""SELECT node_id, url, title, content_type, industry, country, region,
                   orphan_status, internal_links_in, internal_links_out,
                   page_authority_score, status
            FROM content_nodes {where_sql}
            ORDER BY page_authority_score DESC
            LIMIT ? OFFSET ?""",
        params + [limit, skip],
    ).fetchall()
    conn.close()

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "pages": [dict(r) for r in rows],
    }


# ── 4. Orphan pages ── MUST be defined before /api/pages/{node_id} ──────────

@app.get("/api/pages/orphans")
def get_orphans(
    limit: int = Query(100, ge=1, le=500, description="Max orphan pages to return"),
):
    """List pages with zero incoming internal links, highest authority first.
    Registered before /api/pages/{node_id} so the literal path 'orphans' is
    never mistaken for a page ID."""
    conn = get_db()
    rows = conn.execute(
        """SELECT node_id, url, title, content_type, industry, country,
                  internal_links_in, internal_links_out, page_authority_score
           FROM content_nodes
           WHERE orphan_status = 'orphan'
           ORDER BY page_authority_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return {"count": len(rows), "orphans": [dict(r) for r in rows]}


# ── 5. Get specific page by node_id ─────────────────────────────────────────

@app.get("/api/pages/{node_id}")
def get_page(node_id: str):
    """Return full details for one page, looked up by node_id; falls back to
    a partial URL match so a slug/fragment also works. Raises 404 if neither matches."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM content_nodes WHERE node_id = ?", (node_id,)
    ).fetchone()
    if row is None:
        # Also try matching by URL fragment (last part of URL)
        row = conn.execute(
            "SELECT * FROM content_nodes WHERE url LIKE ?", (f"%{node_id}%",)
        ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    return dict(row)


# ── 6. Taxonomy: industries ──────────────────────────────────────────────────

@app.get("/api/taxonomy/industries")
def get_industries():
    """Return every distinct industry with its page count, ordered highest first.
    Used to populate dashboard filter dropdowns."""
    conn = get_db()
    rows = conn.execute(
        """SELECT industry, COUNT(*) as page_count
           FROM content_nodes
           WHERE industry IS NOT NULL AND industry != ''
           GROUP BY industry
           ORDER BY page_count DESC"""
    ).fetchall()
    conn.close()
    return {
        "count": len(rows),
        "industries": [{"name": r["industry"], "page_count": r["page_count"]} for r in rows],
    }


# ── 7. Taxonomy: countries ───────────────────────────────────────────────────

@app.get("/api/taxonomy/countries")
def get_countries():
    """Return every distinct country with its page count, ordered highest first.
    Used to populate dashboard filter dropdowns."""
    conn = get_db()
    rows = conn.execute(
        """SELECT country, COUNT(*) as page_count
           FROM content_nodes
           WHERE country IS NOT NULL AND country != ''
           GROUP BY country
           ORDER BY page_count DESC"""
    ).fetchall()
    conn.close()
    return {
        "count": len(rows),
        "countries": [{"name": r["country"], "page_count": r["page_count"]} for r in rows],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Phase 2 — Entity intelligence endpoints (Day 5)
# ═════════════════════════════════════════════════════════════════════════════

# ── 8. List entities (paginated, filterable) ─────────────────────────────────

@app.get("/api/entities")
def list_entities(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    entity_type: Optional[str] = Query(None, description="Filter: industry | country | region | market | time_period"),
    search: Optional[str] = Query(None, description="Substring match on entity name"),
):
    """List extracted entities with page counts, most-used first."""
    conn = get_db()
    where, params = [], []
    if entity_type:
        where.append("LOWER(ce.entity_type) = LOWER(?)")
        params.append(entity_type)
    if search:
        where.append("(ce.entity_name LIKE ? OR ce.normalized_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = conn.execute(
        f"""SELECT ce.entity_id, ce.entity_name, ce.entity_type,
                   ce.normalized_name, ce.industry, ce.country, ce.region,
                   ce.confidence_score,
                   COUNT(ne.node_entity_id) AS page_count
            FROM content_entities ce
            LEFT JOIN node_entities ne
                   ON ne.entity_id = ce.entity_id AND ne.status != 'rejected'
            {where_sql}
            GROUP BY ce.entity_id
            HAVING page_count > 0
            ORDER BY page_count DESC, ce.entity_name
            LIMIT ? OFFSET ?""",
        params + [limit, skip],
    ).fetchall()
    # total must reflect the same "has an active mapping" filter as the rows,
    # or pagination math goes wrong (e.g. an orphaned entity like a fully
    # rejected extraction still counting toward `total`)
    total = conn.execute(
        f"""SELECT COUNT(*) FROM (
                SELECT ce.entity_id FROM content_entities ce
                LEFT JOIN node_entities ne
                       ON ne.entity_id = ce.entity_id AND ne.status != 'rejected'
                {where_sql}
                GROUP BY ce.entity_id
                HAVING COUNT(ne.node_entity_id) > 0
            )""",
        params,
    ).fetchone()[0]
    conn.close()
    return {"total": total, "skip": skip, "limit": limit,
            "entities": [dict(r) for r in rows]}


# ── 9. Low-confidence review queue ── MUST precede /api/entities/{entity_id} ─

@app.get("/api/entities/low-confidence")
def get_low_confidence_entities(
    threshold: float = Query(0.70, ge=0.0, le=1.0, description="Confidence cutoff"),
    limit: int = Query(200, ge=1, le=1000),
):
    """Page-to-entity mappings below the confidence threshold that still await
    review (status='extracted'), least confident first. The manual-review queue."""
    conn = get_db()
    rows = conn.execute(
        """SELECT ne.node_entity_id, n.url, ce.entity_type, ce.entity_name,
                  ne.entity_role, ne.source_field, ne.extracted_value,
                  ne.normalized_value, ne.confidence_score,
                  ne.extraction_method, ne.status
           FROM node_entities ne
           JOIN content_nodes n ON n.node_id = ne.node_id
           JOIN content_entities ce ON ce.entity_id = ne.entity_id
           WHERE ne.confidence_score < ? AND ne.status = 'extracted'
           ORDER BY ne.confidence_score ASC, n.url
           LIMIT ?""",
        (threshold, limit),
    ).fetchall()
    conn.close()
    return {"threshold": threshold, "count": len(rows),
            "mappings": [dict(r) for r in rows]}


# ── 10. Entity detail with its pages ─────────────────────────────────────────

@app.get("/api/entities/{entity_id}")
def get_entity(entity_id: str):
    """One entity plus every page mapped to it. 404 if unknown."""
    conn = get_db()
    entity = conn.execute(
        "SELECT * FROM content_entities WHERE entity_id = ?", (entity_id,)
    ).fetchone()
    if entity is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    pages = conn.execute(
        """SELECT n.node_id, n.url, n.title, n.content_type,
                  ne.entity_role, ne.confidence_score, ne.status
           FROM node_entities ne
           JOIN content_nodes n ON n.node_id = ne.node_id
           WHERE ne.entity_id = ?
           ORDER BY ne.confidence_score DESC""",
        (entity_id,),
    ).fetchall()
    conn.close()
    return {**dict(entity), "pages": [dict(r) for r in pages],
            "page_count": len(pages)}


# ── 11. Entities of one page ─────────────────────────────────────────────────

@app.get("/api/pages/{node_id}/entities")
def get_page_entities(node_id: str):
    """Every entity extracted for one page, with confidence and provenance."""
    conn = get_db()
    page = conn.execute(
        "SELECT node_id, url, title FROM content_nodes WHERE node_id = ?",
        (node_id,),
    ).fetchone()
    if page is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    rows = conn.execute(
        """SELECT ce.entity_id, ce.entity_name, ce.entity_type,
                  ne.entity_role, ne.source_field, ne.confidence_score,
                  ne.extraction_method, ne.status
           FROM node_entities ne
           JOIN content_entities ce ON ce.entity_id = ne.entity_id
           WHERE ne.node_id = ?
           ORDER BY ne.confidence_score DESC""",
        (node_id,),
    ).fetchall()
    conn.close()
    return {**dict(page), "entities": [dict(r) for r in rows],
            "entity_count": len(rows)}


# ── 12. Taxonomy: markets ────────────────────────────────────────────────────

@app.get("/api/taxonomy/markets")
def get_markets():
    """Every distinct market entity with its page count, most-covered first."""
    conn = get_db()
    rows = conn.execute(
        """SELECT ce.entity_name AS name, ce.entity_id,
                  COUNT(ne.node_entity_id) AS page_count
           FROM content_entities ce
           LEFT JOIN node_entities ne
                  ON ne.entity_id = ce.entity_id AND ne.status != 'rejected'
           WHERE ce.entity_type = 'market'
           GROUP BY ce.entity_id
           HAVING page_count > 0
           ORDER BY page_count DESC, name""",
    ).fetchall()
    conn.close()
    return {"count": len(rows), "markets": [dict(r) for r in rows]}


# ── 13. Taxonomy: regions ────────────────────────────────────────────────────

@app.get("/api/taxonomy/regions")
def get_regions():
    """Every distinct region entity with its page count."""
    conn = get_db()
    rows = conn.execute(
        """SELECT ce.entity_name AS name, ce.entity_id,
                  COUNT(ne.node_entity_id) AS page_count
           FROM content_entities ce
           LEFT JOIN node_entities ne
                  ON ne.entity_id = ce.entity_id AND ne.status != 'rejected'
           WHERE ce.entity_type = 'region'
           GROUP BY ce.entity_id
           HAVING page_count > 0
           ORDER BY page_count DESC, name""",
    ).fetchall()
    conn.close()
    return {"count": len(rows), "regions": [dict(r) for r in rows]}


# ── 14. Intelligence: entity coverage stats ──────────────────────────────────

@app.get("/api/intelligence/entity-coverage")
def get_entity_coverage():
    """Coverage summary: how much of the inventory has extracted entities,
    by entity type and confidence band. Backs the Day 5 coverage report."""
    conn = get_db()
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status='active'"
    ).fetchone()[0]

    def covered(entity_types: tuple[str, ...]) -> int:
        placeholders = ",".join("?" * len(entity_types))
        return conn.execute(
            f"""SELECT COUNT(DISTINCT ne.node_id) FROM node_entities ne
                JOIN content_entities ce ON ce.entity_id = ne.entity_id
                JOIN content_nodes n ON n.node_id = ne.node_id
                WHERE ce.entity_type IN ({placeholders})
                  AND ne.status != 'rejected' AND n.status = 'active'""",
            entity_types,
        ).fetchone()[0]

    pct = lambda n: round(100.0 * n / active, 1) if active else 0.0
    any_entity = conn.execute(
        """SELECT COUNT(DISTINCT ne.node_id) FROM node_entities ne
           JOIN content_nodes n ON n.node_id = ne.node_id
           WHERE ne.status != 'rejected' AND n.status = 'active'"""
    ).fetchone()[0]
    confidence_bands = {
        row["band"]: row["n"]
        for row in conn.execute(
            """SELECT CASE WHEN confidence_score>=0.9 THEN 'high_0.9_plus'
                           WHEN confidence_score>=0.7 THEN 'good_0.7_to_0.9'
                           WHEN confidence_score>=0.5 THEN 'review_0.5_to_0.7'
                           ELSE 'low_below_0.5' END AS band, COUNT(*) AS n
               FROM node_entities GROUP BY band"""
        )
    }
    statuses = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM node_entities GROUP BY status"
        )
    }
    entity_totals = {
        row["entity_type"]: row["n"]
        for row in conn.execute(
            "SELECT entity_type, COUNT(*) AS n FROM content_entities "
            "GROUP BY entity_type ORDER BY n DESC"
        )
    }
    # covered() uses `conn` — must run before it closes
    geo = covered(("country", "region"))
    ind_market = covered(("industry", "market"))
    market = covered(("market",))
    conn.close()
    return {
        "active_pages": active,
        "coverage": {
            "pages_with_any_entity": {"count": any_entity, "pct": pct(any_entity), "target_pct": 95.0},
            "pages_with_geography": {"count": geo, "pct": pct(geo), "target_pct": 90.0},
            "pages_with_industry_or_market": {"count": ind_market, "pct": pct(ind_market), "target_pct": 80.0},
            "pages_with_market": {"count": market, "pct": pct(market)},
        },
        "unique_entities_by_type": entity_totals,
        "mapping_confidence_bands": confidence_bands,
        "mapping_statuses": statuses,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Phase 2 — SEO validation endpoint (Agent 10, master PRD §29.2)
# ═════════════════════════════════════════════════════════════════════════════

class LinkValidationRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    anchor_text: str
    placement: str = "body_paragraph"
    proposed_target_url: Optional[str] = None


@app.post("/api/internal-linking/validate")
def validate_internal_link(request: LinkValidationRequest):
    """Run a proposed internal link through Agent 10's SEO validation rules
    (canonical target, indexability, crawlability, anchor quality, faceted
    URL risk, link count, placement, self-link). Never modifies data —
    read-only against content_nodes. See agents/agent_10_seo_validation.py
    for the full rule set and its documented deferred checks."""
    agent = SEOValidationAgent(DB_PATH)
    result = agent.validate(
        request.source_node_id, request.target_node_id,
        request.anchor_text, request.placement, request.proposed_target_url,
    )
    return asdict(result)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
