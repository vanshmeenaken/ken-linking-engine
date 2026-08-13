import sqlite3
import os
import sys
import time
import uuid
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


@app.get("/users")
def users_workbench():
    """Serve the manual interlinking workbench (dashboard/users.html): paste a
    report URL, read its real content, and record link decisions by hand."""
    return FileResponse(os.path.join(ROOT, "dashboard", "users.html"))


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
# Phase 2 — Relationship, opportunity & intelligence endpoints (Day 9)
# ═════════════════════════════════════════════════════════════════════════════

# ── 15. Relationship types summary ── static path, defined before siblings ───

@app.get("/api/relationships/types")
def get_relationship_types():
    """Every relationship type in the graph with edge count and average
    confidence, most common first."""
    conn = get_db()
    rows = conn.execute(
        """SELECT relationship_type, COUNT(*) AS edge_count,
                  ROUND(AVG(confidence_score), 3) AS avg_confidence
           FROM relationship_edges
           GROUP BY relationship_type
           ORDER BY edge_count DESC"""
    ).fetchall()
    conn.close()
    return {"count": len(rows), "types": [dict(r) for r in rows]}


# ── 16. Pending review queue ─────────────────────────────────────────────────

@app.get("/api/relationships/pending")
def get_pending_relationships(
    limit: int = Query(100, ge=1, le=500),
):
    """Relationship edges awaiting human review (status='pending'),
    least confident first — the ones most worth a look."""
    conn = get_db()
    rows = conn.execute(
        """SELECT e.edge_id, e.relationship_type, e.confidence_score,
                  s.url AS source_url, t.url AS target_url
           FROM relationship_edges e
           JOIN content_nodes s ON s.node_id = e.source_node_id
           JOIN content_nodes t ON t.node_id = e.target_node_id
           WHERE e.status = 'pending'
           ORDER BY e.confidence_score ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return {"count": len(rows), "pending": [dict(r) for r in rows]}


# ── 17. List relationships (paginated, filterable) ───────────────────────────

@app.get("/api/relationships")
def list_relationships(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    relationship_type: Optional[str] = Query(None, description="e.g. same_market, adjacent_market, global_local"),
    status: Optional[str] = Query(None, description="pending | approved | rejected"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    """List relationship edges with source/target page context, highest
    confidence first. Filterable by type, review status and confidence floor."""
    conn = get_db()
    where = ["e.confidence_score >= ?"]
    params: list = [min_confidence]
    if relationship_type:
        where.append("LOWER(e.relationship_type) = LOWER(?)")
        params.append(relationship_type)
    if status:
        where.append("LOWER(e.status) = LOWER(?)")
        params.append(status)
    where_sql = "WHERE " + " AND ".join(where)

    total = conn.execute(
        f"SELECT COUNT(*) FROM relationship_edges e {where_sql}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT e.edge_id, e.relationship_type, e.relationship_direction,
                   e.confidence_score, e.semantic_similarity_score,
                   e.entity_overlap_score, e.geo_match_score,
                   e.market_match_score, e.status, e.created_by,
                   s.node_id AS source_node_id, s.url AS source_url,
                   s.title AS source_title,
                   t.node_id AS target_node_id, t.url AS target_url,
                   t.title AS target_title
            FROM relationship_edges e
            JOIN content_nodes s ON s.node_id = e.source_node_id
            JOIN content_nodes t ON t.node_id = e.target_node_id
            {where_sql}
            ORDER BY e.confidence_score DESC
            LIMIT ? OFFSET ?""",
        params + [limit, skip],
    ).fetchall()
    conn.close()
    return {"total": total, "skip": skip, "limit": limit,
            "relationships": [dict(r) for r in rows]}


# ── 18. Relationships of one page ─────────────────────────────────────────────

@app.get("/api/pages/{node_id}/relationships")
def get_page_relationships(node_id: str):
    """Every relationship edge touching one page, in either direction.
    Each edge is annotated with the OTHER page's details plus this page's
    role (source or target). 404 if the page is unknown."""
    conn = get_db()
    page = conn.execute(
        "SELECT node_id, url, title FROM content_nodes WHERE node_id = ?",
        (node_id,),
    ).fetchone()
    if page is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    # Exclude self-loop edges (source_node_id == target_node_id). Those are
    # industry_market edges that anchor an entity-to-entity relationship on a
    # single page; they are page metadata, not links to OTHER pages, and would
    # otherwise show up here as a page "related to itself". The page's own
    # entity relationships are available via /api/pages/{node_id}/entities.
    rows = conn.execute(
        """SELECT e.edge_id, e.relationship_type, e.relationship_direction,
                  e.confidence_score, e.status,
                  CASE WHEN e.source_node_id = ? THEN 'source' ELSE 'target' END
                      AS this_page_role,
                  o.node_id AS other_node_id, o.url AS other_url,
                  o.title AS other_title, o.content_type AS other_content_type
           FROM relationship_edges e
           JOIN content_nodes o
             ON o.node_id = CASE WHEN e.source_node_id = ?
                                 THEN e.target_node_id ELSE e.source_node_id END
           WHERE (e.source_node_id = ? OR e.target_node_id = ?)
             AND e.source_node_id != e.target_node_id
           ORDER BY e.confidence_score DESC""",
        (node_id, node_id, node_id, node_id),
    ).fetchall()
    conn.close()
    return {**dict(page), "relationship_count": len(rows),
            "relationships": [dict(r) for r in rows]}


# ── 19. Relationships of one entity ──────────────────────────────────────────

@app.get("/api/entities/{entity_id}/relationships")
def get_entity_relationships(entity_id: str):
    """Every relationship edge anchored to one entity (as source or target
    entity). Note: only ~87% of edges carry entity anchors — purely
    page-level edges won't appear here. 404 if the entity is unknown."""
    conn = get_db()
    entity = conn.execute(
        "SELECT entity_id, entity_name, entity_type FROM content_entities "
        "WHERE entity_id = ?", (entity_id,),
    ).fetchone()
    if entity is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    rows = conn.execute(
        """SELECT e.edge_id, e.relationship_type, e.confidence_score, e.status,
                  s.url AS source_url, t.url AS target_url
           FROM relationship_edges e
           JOIN content_nodes s ON s.node_id = e.source_node_id
           JOIN content_nodes t ON t.node_id = e.target_node_id
           WHERE e.source_entity_id = ? OR e.target_entity_id = ?
           ORDER BY e.confidence_score DESC""",
        (entity_id, entity_id),
    ).fetchall()
    conn.close()
    return {**dict(entity), "relationship_count": len(rows),
            "relationships": [dict(r) for r in rows]}


# ── 20. SEO opportunities: orphans ── static paths before /{...} siblings ────

@app.get("/api/opportunities/orphans")
def get_opportunity_orphans(limit: int = Query(100, ge=1, le=500)):
    """Orphan-page opportunities (no incoming links at all), highest
    business-score first — the classic recovery list."""
    return _list_opportunities_filtered(
        opportunity_types=("orphan_page",), limit=limit)


# ── 21. SEO opportunities: underlinked ───────────────────────────────────────

@app.get("/api/opportunities/underlinked")
def get_opportunity_underlinked(limit: int = Query(100, ge=1, le=500)):
    """Underlinked-page opportunities, including the high-priority-underlinked
    class (commercial pages starving for links)."""
    return _list_opportunities_filtered(
        opportunity_types=("underlinked_page", "high_priority_underlinked"),
        limit=limit)


# ── 22. SEO opportunities: the gold list ─────────────────────────────────────

@app.get("/api/opportunities/high-priority")
def get_opportunity_high_priority(limit: int = Query(100, ge=1, le=500)):
    """The fix-first list: open opportunities on pages whose business
    priority is High — valuable AND broken. This is the queue the Phase 3
    recommendation engine will work through first."""
    conn = get_db()
    rows = conn.execute(
        """SELECT o.opportunity_id, o.opportunity_type, o.priority, o.reason,
                  o.seo_score, o.business_score, o.status,
                  n.node_id, n.url, n.title, n.content_type,
                  n.business_priority, n.search_opportunity_score,
                  n.internal_links_in
           FROM seo_opportunities o
           JOIN content_nodes n ON n.node_id = o.node_id
           WHERE o.status = 'open' AND n.business_priority = 'High'
           ORDER BY o.business_score DESC, o.seo_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return {"count": len(rows), "opportunities": [dict(r) for r in rows]}


def _list_opportunities_filtered(opportunity_types: tuple, limit: int):
    """Shared query for the orphan/underlinked shortcut endpoints."""
    conn = get_db()
    placeholders = ",".join("?" * len(opportunity_types))
    rows = conn.execute(
        f"""SELECT o.opportunity_id, o.opportunity_type, o.priority, o.reason,
                   o.seo_score, o.business_score, o.status,
                   n.node_id, n.url, n.title, n.business_priority,
                   n.internal_links_in
            FROM seo_opportunities o
            JOIN content_nodes n ON n.node_id = o.node_id
            WHERE o.status = 'open' AND o.opportunity_type IN ({placeholders})
            ORDER BY o.business_score DESC, o.seo_score DESC
            LIMIT ?""",
        (*opportunity_types, limit),
    ).fetchall()
    conn.close()
    return {"count": len(rows), "opportunities": [dict(r) for r in rows]}


# ── 23. List SEO opportunities (paginated, filterable) ───────────────────────

@app.get("/api/opportunities")
def list_opportunities(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    opportunity_type: Optional[str] = Query(None, description="e.g. orphan_page, missing_relationships"),
    priority: Optional[str] = Query(None, description="high | medium | low"),
    status: Optional[str] = Query(None, description="open | resolved | dismissed"),
):
    """List SEO opportunities with page context, most valuable first.
    Filterable by type, priority and status."""
    conn = get_db()
    where, params = [], []
    if opportunity_type:
        where.append("LOWER(o.opportunity_type) = LOWER(?)")
        params.append(opportunity_type)
    if priority:
        where.append("LOWER(o.priority) = LOWER(?)")
        params.append(priority)
    if status:
        where.append("LOWER(o.status) = LOWER(?)")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM seo_opportunities o {where_sql}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT o.opportunity_id, o.node_id, o.opportunity_type, o.priority,
                   o.reason, o.evidence, o.seo_score, o.business_score,
                   o.status, n.url, n.title, n.business_priority
            FROM seo_opportunities o
            JOIN content_nodes n ON n.node_id = o.node_id
            {where_sql}
            ORDER BY o.business_score DESC, o.seo_score DESC
            LIMIT ? OFFSET ?""",
        params + [limit, skip],
    ).fetchall()
    conn.close()
    return {"total": total, "skip": skip, "limit": limit,
            "opportunities": [dict(r) for r in rows]}


# ── 24. Intelligence: overall stats ──────────────────────────────────────────

@app.get("/api/intelligence/stats")
def get_intelligence_stats():
    """One-call summary of the whole intelligence layer: entities, mappings,
    relationship edges, opportunities and Phase 2 scores. The dashboard's
    top-line numbers."""
    conn = get_db()
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status='active'"
    ).fetchone()[0]
    entities = conn.execute("SELECT COUNT(*) FROM content_entities").fetchone()[0]
    mappings = conn.execute(
        "SELECT COUNT(*) FROM node_entities WHERE status != 'rejected'"
    ).fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM relationship_edges").fetchone()[0]
    open_opps = conn.execute(
        "SELECT COUNT(*) FROM seo_opportunities WHERE status='open'"
    ).fetchone()[0]
    biz = {
        row["business_priority"]: row["n"]
        for row in conn.execute(
            """SELECT business_priority, COUNT(*) AS n FROM content_nodes
               WHERE status='active' AND business_priority IS NOT NULL
               GROUP BY business_priority"""
        )
    }
    intent = {
        row["intent_stage"]: row["n"]
        for row in conn.execute(
            """SELECT intent_stage, COUNT(*) AS n FROM content_nodes
               WHERE status='active' AND intent_stage IS NOT NULL
               GROUP BY intent_stage"""
        )
    }
    avg_ai = conn.execute(
        """SELECT ROUND(AVG(ai_readiness_score), 3) FROM content_nodes
           WHERE status='active' AND ai_readiness_score IS NOT NULL"""
    ).fetchone()[0]
    conn.close()
    return {
        "active_pages": active,
        "entities": entities,
        "page_entity_mappings": mappings,
        "relationship_edges": edges,
        "open_opportunities": open_opps,
        "business_priority_bands": biz,
        "intent_stages": intent,
        "avg_ai_readiness_score": avg_ai,
    }


# ── 25. Intelligence: relationship coverage ──────────────────────────────────

@app.get("/api/intelligence/relationship-coverage")
def get_relationship_coverage():
    """How connected the graph is: share of active pages linked to at least
    one OTHER page (the metric that matters for internal linking), judged
    against the Phase 2 70% target.

    relationship_edges holds only genuine page-to-page edges. Entity hierarchy
    (a market's parent industry) lives in content_entities.parent_entity_id,
    not here. `self_loop_edges` is a canary that must stay 0 — a non-zero value
    means page-scoped entity facts have leaked back into the links table.
    """
    conn = get_db()
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status='active'"
    ).fetchone()[0]
    connected = conn.execute(
        """SELECT COUNT(DISTINCT n.node_id) FROM content_nodes n
           JOIN relationship_edges e
             ON e.source_node_id = n.node_id OR e.target_node_id = n.node_id
           WHERE n.status = 'active'
             AND e.source_node_id != e.target_node_id"""
    ).fetchone()[0]
    by_type = {
        row["relationship_type"]: row["n"]
        for row in conn.execute(
            "SELECT relationship_type, COUNT(*) AS n FROM relationship_edges "
            "GROUP BY relationship_type ORDER BY n DESC"
        )
    }
    self_loops = conn.execute(
        "SELECT COUNT(*) FROM relationship_edges "
        "WHERE source_node_id = target_node_id"
    ).fetchone()[0]
    by_status = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM relationship_edges GROUP BY status"
        )
    }
    conf = conn.execute(
        """SELECT ROUND(AVG(confidence_score),3) AS avg,
                  ROUND(MIN(confidence_score),3) AS min,
                  ROUND(MAX(confidence_score),3) AS max
           FROM relationship_edges"""
    ).fetchone()
    conn.close()
    pct = round(100.0 * connected / active, 1) if active else 0.0
    return {
        "active_pages": active,
        "page_to_page_connectivity": {
            "count": connected, "pct": pct, "target_pct": 70.0,
            "note": "pages linked to at least one other page. Low on the 500-"
                    "page sample because most pages' real siblings (same market, "
                    "other geographies) are not in the sample; rises with the "
                    "full catalog.",
        },
        "total_edges": sum(by_type.values()),
        "self_loop_edges": self_loops,  # canary: must be 0
        "edges_by_type": by_type,
        "edges_by_status": by_status,
        "confidence": dict(conf),
    }


# ── 26. Intelligence: global/local segmentation ──────────────────────────────

@app.get("/api/intelligence/global-local")
def get_global_local():
    """Global vs local segmentation of active pages, plus the global_local
    relationship pairs found so far (a global page linked to its country
    versions)."""
    conn = get_db()
    segmentation = {
        row["global_or_local"]: row["n"]
        for row in conn.execute(
            """SELECT COALESCE(NULLIF(global_or_local,''),'unknown') AS global_or_local,
                      COUNT(*) AS n
               FROM content_nodes WHERE status='active'
               GROUP BY global_or_local"""
        )
    }
    pairs = conn.execute(
        """SELECT e.edge_id, e.confidence_score,
                  s.url AS global_url, t.url AS local_url
           FROM relationship_edges e
           JOIN content_nodes s ON s.node_id = e.source_node_id
           JOIN content_nodes t ON t.node_id = e.target_node_id
           WHERE e.relationship_type = 'global_local'
           ORDER BY e.confidence_score DESC"""
    ).fetchall()
    conn.close()
    return {"segmentation": segmentation,
            "global_local_pairs": [dict(r) for r in pairs],
            "pair_count": len(pairs)}


# ── 27. Intelligence: business priority breakdown ────────────────────────────

@app.get("/api/intelligence/business-priority")
def get_business_priority(
    top: int = Query(20, ge=1, le=100, description="How many top-priority pages to include"),
):
    """Business-priority view: band counts, band-by-content-type matrix, and
    the top High-priority pages with their opportunity flags — the pages
    leadership should care about most."""
    conn = get_db()
    bands = {
        row["business_priority"]: row["n"]
        for row in conn.execute(
            """SELECT business_priority, COUNT(*) AS n FROM content_nodes
               WHERE status='active' AND business_priority IS NOT NULL
               GROUP BY business_priority"""
        )
    }
    by_content_type: dict = {}
    for row in conn.execute(
        """SELECT content_type, business_priority, COUNT(*) AS n
           FROM content_nodes
           WHERE status='active' AND business_priority IS NOT NULL
           GROUP BY content_type, business_priority"""
    ):
        by_content_type.setdefault(row["content_type"], {})[row["business_priority"]] = row["n"]
    top_pages = conn.execute(
        """SELECT n.node_id, n.url, n.title, n.content_type,
                  n.business_priority, n.page_authority_score,
                  n.search_opportunity_score, n.internal_links_in,
                  COUNT(o.opportunity_id) AS open_opportunities
           FROM content_nodes n
           LEFT JOIN seo_opportunities o
                  ON o.node_id = n.node_id AND o.status = 'open'
           WHERE n.status='active' AND n.business_priority = 'High'
           GROUP BY n.node_id
           ORDER BY n.page_authority_score DESC
           LIMIT ?""",
        (top,),
    ).fetchall()
    conn.close()
    return {"bands": bands, "by_content_type": by_content_type,
            "top_high_priority_pages": [dict(r) for r in top_pages]}


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3 — Link recommendations (Agent 6) + editorial review queue
# ═════════════════════════════════════════════════════════════════════════════

# ── 31. Review queue ── static path, defined before /{...} siblings ──────────

@app.get("/api/recommendations/review-queue")
def get_review_queue(limit: int = Query(50, ge=1, le=500)):
    """The editorial review queue: pending recommendations that passed
    validation, highest link score first. This is the list a human works down
    to approve or reject links (master PRD 24.4). EVERY row carries its
    placement_reason (why this exact spot) and, for in-sentence placements,
    woven_sentence - the EXISTING sentence rewritten to carry the anchor
    inline, so the editor sees exactly what to paste, not just where.
    woven_sentence is precomputed (scripts/36_generate_woven_sentences.py,
    NVIDIA LLM with a deterministic fallback) - reading it here never makes
    a live API call."""
    from agents.agent_11_editorial_review import _placement_reason, _woven_sentence, clean_title

    conn = get_db()
    rows = conn.execute(
        """SELECT r.recommendation_id, r.source_url, r.target_url,
                  r.relationship_type,
                  r.relationship_class, r.market_match_score,
                  r.technology_match_score,
                  r.anchor_text, r.placement_type, r.placement_section,
                  r.suggested_sentence, r.proposed_sentence, r.woven_sentence,
                  r.woven_sentence_source,
                  r.placement_status, r.plan_category,
                  r.source_plan_rank, r.link_score, r.seo_score,
                  r.business_score, r.score_band, r.risk_flag,
                  r.recommendation_reason, t.title AS target_title
           FROM link_recommendations r
           JOIN content_nodes t ON t.node_id = r.target_node_id
           WHERE r.status = 'pending' AND r.score_band != 'drop'
           ORDER BY r.link_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        rec = dict(r)
        rec["placement_reason"] = _placement_reason(
            rec, clean_title(rec.pop("target_title") or ""))
        rec["woven_sentence"] = (
            _woven_sentence(rec)
            if rec["placement_type"] == "contextual_body"
               and rec.get("suggested_sentence")
            else None)
        out.append(rec)
    return {"count": len(out), "recommendations": out}


# ── 32. Recommendation stats ─────────────────────────────────────────────────

@app.get("/api/recommendations/stats")
def get_recommendation_stats():
    """Summary of the recommendation set: totals by band, status, and
    validation outcome."""
    conn = get_db()
    def group(col):
        return {row[0]: row[1] for row in conn.execute(
            f"SELECT {col}, COUNT(*) FROM link_recommendations GROUP BY {col}")}
    total = conn.execute("SELECT COUNT(*) FROM link_recommendations").fetchone()[0]
    avg = conn.execute(
        "SELECT ROUND(AVG(link_score),1) FROM link_recommendations").fetchone()[0]
    # build every group BEFORE closing the connection
    result = {"total": total, "avg_link_score": avg,
              "by_band": group("score_band"), "by_status": group("status"),
              "by_validation": group("validation_status"),
              "by_relationship_class": group("relationship_class")}
    conn.close()
    return result


# ── 33. List recommendations (paginated, filterable) ─────────────────────────

@app.get('/api/report-link-plans/stats')
def get_report_link_plan_stats():
    '''Coverage against the PRD link and opportunity ranges.'''
    conn = get_db()
    total = conn.execute(
        'SELECT COUNT(*) FROM report_link_plans'
    ).fetchone()[0]
    by_status = {
        row[0]: row[1] for row in conn.execute(
            'SELECT plan_status, COUNT(*) FROM report_link_plans '
            'GROUP BY plan_status'
        )
    }
    by_opportunity = {
        row[0]: row[1] for row in conn.execute(
            'SELECT opportunity_status, COUNT(*) FROM report_link_plans '
            'GROUP BY opportunity_status'
        )
    }
    totals = conn.execute(
        '''SELECT COALESCE(SUM(recommended_outgoing_links), 0),
                  COALESCE(SUM(incoming_opportunities), 0),
                  COALESCE(SUM(remaining_gap), 0)
           FROM report_link_plans'''
    ).fetchone()
    conn.close()
    return {
        'total_reports': total,
        'by_plan_status': by_status,
        'by_opportunity_status': by_opportunity,
        'recommended_outgoing': totals[0],
        'incoming_opportunities': totals[1],
        'remaining_link_gap': totals[2],
        'link_range': {'minimum': 10, 'maximum': 25},
        'opportunity_range': {'minimum': 10, 'maximum': 30},
    }


@app.get('/api/report-link-plans')
def list_report_link_plans(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    plan_status: Optional[str] = Query(None),
    opportunity_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    '''Return one balanced incoming/outgoing plan per active report.'''
    conn = get_db()
    where, params = [], []
    if plan_status:
        where.append('LOWER(p.plan_status)=LOWER(?)')
        params.append(plan_status)
    if opportunity_status:
        where.append('LOWER(p.opportunity_status)=LOWER(?)')
        params.append(opportunity_status)
    if search:
        where.append('(p.report_url LIKE ? OR n.title LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%'])
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
    total = conn.execute(
        f'''SELECT COUNT(*) FROM report_link_plans p
            JOIN content_nodes n ON n.node_id=p.report_node_id {where_sql}''',
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f'''SELECT p.*, n.title AS report_title
            FROM report_link_plans p
            JOIN content_nodes n ON n.node_id=p.report_node_id
            {where_sql}
            ORDER BY
                CASE p.plan_status
                    WHEN 'existing_over_limit' THEN 0
                    WHEN 'planned_over_limit' THEN 1
                    WHEN 'needs_more_relevant_links' THEN 2
                    ELSE 3
                END,
                p.total_opportunities DESC, p.remaining_gap DESC,
                p.report_url
            LIMIT ? OFFSET ?''',
        params + [limit, skip],
    ).fetchall()
    conn.close()
    return {
        'total': total,
        'skip': skip,
        'limit': limit,
        'plans': [dict(row) for row in rows],
    }


@app.get("/api/recommendations")
def list_recommendations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    band: Optional[str] = Query(None, description="priority | strong | secondary | hold"),
    status: Optional[str] = Query(None, description="pending | approved | rejected | deployed"),
    relationship_type: Optional[str] = Query(None),
    relationship_class: Optional[str] = Query(None),
):
    """List link recommendations with full context, highest score first.
    EVERY row carries its placement_reason (why this exact spot) so the
    review table can show the justification inline for all links."""
    from agents.agent_11_editorial_review import _placement_reason, _woven_sentence, clean_title

    conn = get_db()
    where, params = [], []
    if band:
        where.append("LOWER(r.score_band) = LOWER(?)"); params.append(band)
    if status:
        where.append("LOWER(r.status) = LOWER(?)"); params.append(status)
    if relationship_type:
        where.append("LOWER(r.relationship_type) = LOWER(?)"); params.append(relationship_type)
    if relationship_class:
        where.append("LOWER(r.relationship_class) = LOWER(?)"); params.append(relationship_class)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(
        f"SELECT COUNT(*) FROM link_recommendations r {where_sql}",
        params).fetchone()[0]
    rows = conn.execute(
        f"""SELECT r.recommendation_id, r.source_url, r.target_url,
                   r.relationship_type,
                   r.relationship_class, r.market_match_score,
                   r.technology_match_score,
                   r.anchor_text, r.placement_type, r.placement_section,
                   r.suggested_sentence, r.proposed_sentence, r.woven_sentence,
                   r.woven_sentence_source,
                   r.placement_status, r.plan_category,
                   r.source_plan_rank, r.link_score,
                   r.seo_score, r.business_score, r.ai_readiness_score,
                   r.confidence_score,
                   r.score_band, r.risk_flag, r.risk_reason,
                   r.recommendation_reason,
                   r.validation_status, r.status, t.title AS target_title
            FROM link_recommendations r
            JOIN content_nodes t ON t.node_id = r.target_node_id
            {where_sql}
            ORDER BY r.link_score DESC LIMIT ? OFFSET ?""",
        params + [limit, skip],
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        rec = dict(r)
        rec["placement_reason"] = _placement_reason(
            rec, clean_title(rec.pop("target_title") or ""))
        rec["woven_sentence"] = (
            _woven_sentence(rec)
            if rec["placement_type"] == "contextual_body"
               and rec.get("suggested_sentence")
            else None)
        out.append(rec)
    return {"total": total, "skip": skip, "limit": limit,
            "recommendations": out}


# ── 34. Anchor bank for one page (Agent 7) ───────────────────────────────────

@app.get("/api/pages/{node_id}/anchors")
def get_page_anchors(node_id: str):
    """The anchor bank for one target page: the diverse, safe anchor options
    Agent 7 built, so inbound links can rotate anchors instead of repeating one
    exact-match phrase. 404 if the page is unknown; empty bank if none built."""
    import json as _json
    conn = get_db()
    page = conn.execute(
        """SELECT node_id, url, title, content_type,
                  COALESCE(internal_links_out, 0) AS internal_links_out
           FROM content_nodes WHERE node_id = ?""",
        (node_id,)).fetchone()
    if page is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    bank = conn.execute(
        "SELECT * FROM anchor_banks WHERE target_node_id = ?", (node_id,)).fetchone()
    conn.close()
    if bank is None:
        return {**dict(page), "has_bank": False,
                "note": "No anchor bank yet. Run agents/agent_7_anchor_text.py."}
    def arr(col):
        return _json.loads(bank[col]) if bank[col] else []
    return {
        **dict(page), "has_bank": True,
        "primary_anchor": bank["primary_anchor"],
        "secondary_anchors": arr("secondary_anchors"),
        "long_tail_anchors": arr("long_tail_anchors"),
        "country_specific_anchors": arr("country_specific_anchors"),
        "market_specific_anchors": arr("market_specific_anchors"),
        "commercial_anchors": arr("commercial_anchors"),
        "restricted_anchors": arr("restricted_anchors"),
    }


# ── 35. Editorial action on a recommendation (approve / reject / edit) ───────

class RecommendationDecision(BaseModel):
    decision: str            # "approve" | "reject"
    reviewed_by: str
    edited_anchor: Optional[str] = None
    notes: Optional[str] = None


@app.patch("/api/recommendations/{recommendation_id}")
def decide_recommendation(recommendation_id: str, body: RecommendationDecision):
    """Editorial action on one recommendation (master PRD 29.3): approve or
    reject it, optionally editing the anchor text. Records who decided. This is
    the human-in-the-loop gate; nothing deploys without an approve here.

    Deliberately does NOT publish anything to the live site (that is Phase 4,
    and requires CMS access). It only records the editorial decision.
    """
    decision = body.decision.strip().lower()
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=422,
                            detail="decision must be 'approve' or 'reject'")
    new_status = "approved" if decision == "approve" else "rejected"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    conn = get_db()
    existing = conn.execute(
        "SELECT status FROM link_recommendations WHERE recommendation_id = ?",
        (recommendation_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404,
                            detail=f"Recommendation '{recommendation_id}' not found")
    sets = ["status = ?", "approved_by = ?", "updated_at = ?"]
    params: list = [new_status, body.reviewed_by, now]
    if body.edited_anchor:
        sets.append("anchor_text = ?"); params.append(body.edited_anchor)
    if body.notes:
        sets.append("risk_reason = ?"); params.append(body.notes)
    params.append(recommendation_id)
    conn.execute(
        f"UPDATE link_recommendations SET {', '.join(sets)} "
        "WHERE recommendation_id = ?", params)
    from analysis.report_link_planner import refresh_report_link_plans
    refresh_report_link_plans(conn, now)
    conn.commit()
    row = conn.execute(
        "SELECT recommendation_id, status, approved_by, anchor_text, updated_at "
        "FROM link_recommendations WHERE recommendation_id = ?",
        (recommendation_id,)).fetchone()
    conn.close()
    return {"updated": True, **dict(row)}


# ── 35b. Editorial review note (Agent 11) ────────────────────────────────────

@app.get("/api/recommendations/{recommendation_id}/review")
def get_recommendation_review(recommendation_id: str):
    """Plain-English review note for one recommendation (master PRD 13.11):
    why it's recommended, where it goes, its anchor, relationship, SEO/
    business value, and risk - everything a human editor needs to approve or
    reject via PATCH /api/recommendations/{id}. This endpoint never decides
    anything itself (master PRD section 26: human-in-the-loop)."""
    from agents.agent_11_editorial_review import build_review_note

    conn = get_db()
    rec = conn.execute(
        "SELECT * FROM link_recommendations WHERE recommendation_id = ?",
        (recommendation_id,)).fetchone()
    if rec is None:
        conn.close()
        raise HTTPException(status_code=404,
                            detail=f"Recommendation '{recommendation_id}' not found")
    rec = dict(rec)
    source_title = conn.execute(
        "SELECT title FROM content_nodes WHERE node_id = ?",
        (rec["source_node_id"],)).fetchone()
    target_title = conn.execute(
        "SELECT title FROM content_nodes WHERE node_id = ?",
        (rec["target_node_id"],)).fetchone()
    conn.close()
    note = build_review_note(
        rec, source_title[0] if source_title else rec["source_url"],
        target_title[0] if target_title else rec["target_url"])
    return {
        "recommendation_id": note.recommendation_id,
        "status": rec["status"],
        "headline": note.headline,
        "why": note.why,
        "where": note.where,
        "placement_reason": note.placement_reason,
        "woven_sentence": note.woven_sentence,
        "anchor": note.anchor,
        "relationship": note.relationship,
        "seo_value": note.seo_value,
        "business_value": note.business_value,
        "risk": note.risk,
        "plain_summary": note.plain_summary,
    }


# ── 36. Recommendations touching one page ────────────────────────────────────

@app.get("/api/pages/{node_id}/recommendations")
def get_page_recommendations(node_id: str):
    """Link recommendations where this page is the source (links it should add)
    or the target (links it should receive). 404 if the page is unknown."""
    conn = get_db()
    page = conn.execute(
        "SELECT node_id, url, title FROM content_nodes WHERE node_id = ?",
        (node_id,)).fetchone()
    if page is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    outgoing = conn.execute(
        """SELECT target_url, anchor_text, link_score, score_band,
                  relationship_class, market_match_score, technology_match_score,
                  placement_type, placement_section, placement_status,
                  plan_category, source_plan_rank, suggested_sentence, status
           FROM link_recommendations WHERE source_node_id = ?
           ORDER BY link_score DESC""", (node_id,)).fetchall()
    incoming = conn.execute(
        """SELECT source_url, anchor_text, link_score, score_band,
                  relationship_class, market_match_score, technology_match_score,
                  placement_type, placement_section, placement_status,
                  plan_category, suggested_sentence, status
           FROM link_recommendations WHERE target_node_id = ?
           ORDER BY link_score DESC""", (node_id,)).fetchall()
    link_plan = conn.execute(
        "SELECT * FROM report_link_plans WHERE report_node_id = ?",
        (node_id,),
    ).fetchone()
    # link spread: are this page's outgoing links distributed across its real
    # sections, or bunched in one place? (Agent 9's section map = the truth
    # about which sections exist and can host links.)
    linkable_sections = [r[0] for r in conn.execute(
        """SELECT heading FROM section_purpose_map
           WHERE node_id = ? AND linkable = 1 AND heading IS NOT NULL
           ORDER BY section_order""", (node_id,))]
    sections_used = sorted({
        r["placement_section"] for r in outgoing
        if r["status"] != "rejected" and r["placement_section"]})
    conn.close()
    spread = None
    if linkable_sections:
        used_real = [s for s in sections_used if s in linkable_sections]
        spread = {
            "linkable_sections": linkable_sections,
            "sections_used": sections_used,
            "spread_note": (
                f"Links sit in {len(used_real)} of "
                f"{len(linkable_sections)} linkable sections"
                + (f"; also: {', '.join(s for s in sections_used if s not in linkable_sections)}"
                   if any(s not in linkable_sections for s in sections_used) else "")),
        }
    return {**dict(page),
            "link_plan": dict(link_plan) if link_plan else None,
            "link_spread": spread,
            "links_to_add": [dict(r) for r in outgoing],
            "links_to_receive": [dict(r) for r in incoming]}


# ── 38. Paragraph evidence (Agent 8) ─────────────────────────────────────────

@app.get("/api/evidence/stats")
def get_evidence_stats():
    """Summary of Agent 8's paragraph evidence map: how many market claims
    exist, how many are unsupported, and the pages with the most unsupported
    claims (the pages an editor should look at first)."""
    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM paragraph_evidence_map").fetchone()[0]
    claims = {row[0]: row[1] for row in conn.execute(
        """SELECT support_status, COUNT(*) FROM paragraph_evidence_map
           WHERE classification = 'market_claim'
           GROUP BY support_status""")}
    with_evidence = conn.execute(
        """SELECT COUNT(*) FROM paragraph_evidence_map
           WHERE evidence_target_node_id IS NOT NULL""").fetchone()[0]
    pages_mapped = conn.execute(
        "SELECT COUNT(DISTINCT node_id) FROM paragraph_evidence_map"
    ).fetchone()[0]
    top_unsupported = conn.execute(
        """SELECT e.node_id, e.url, n.title,
                  COUNT(*) AS unsupported_claims,
                  SUM(CASE WHEN e.evidence_target_node_id IS NOT NULL
                      THEN 1 ELSE 0 END) AS with_evidence_found
           FROM paragraph_evidence_map e
           JOIN content_nodes n ON n.node_id = e.node_id
           WHERE e.classification = 'market_claim'
             AND e.support_status = 'unsupported'
           GROUP BY e.node_id ORDER BY unsupported_claims DESC
           LIMIT 10""").fetchall()
    conn.close()
    return {
        "pages_mapped": pages_mapped,
        "paragraphs_mapped": total,
        "market_claims": sum(claims.values()),
        "claims_by_support": claims,
        "evidence_links_found": with_evidence,
        "top_pages_with_unsupported_claims": [dict(r) for r in top_unsupported],
    }


@app.get("/api/pages/{node_id}/evidence")
def get_page_evidence(node_id: str):
    """Agent 8's paragraph evidence map for one page: every meaningful
    paragraph, whether it makes a market claim, whether that claim is
    supported by a link, and the best evidence page found for unsupported
    claims. 404 if the page is unknown; empty if the page has not been
    mapped yet."""
    conn = get_db()
    page = conn.execute(
        "SELECT node_id, url, title FROM content_nodes WHERE node_id = ?",
        (node_id,)).fetchone()
    if page is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    rows = conn.execute(
        """SELECT section_heading, section_purpose, paragraph_index,
                  paragraph_text, classification, has_numeric_claim,
                  support_status, evidence_target_url, evidence_type,
                  evidence_score
           FROM paragraph_evidence_map WHERE node_id = ?
           ORDER BY paragraph_index""", (node_id,)).fetchall()
    conn.close()
    paragraphs = [dict(r) for r in rows]
    claims = [p for p in paragraphs if p["classification"] == "market_claim"]
    return {**dict(page),
            "mapped": bool(paragraphs),
            "paragraph_count": len(paragraphs),
            "claim_count": len(claims),
            "unsupported_claims": sum(
                1 for c in claims if c["support_status"] == "unsupported"),
            "paragraphs": paragraphs}


# ═════════════════════════════════════════════════════════════════════════════
# Phase 2 — Google integrations (GSC / GA4)
# ═════════════════════════════════════════════════════════════════════════════

# ── 28. Integration status ───────────────────────────────────────────────────

@app.get("/api/integrations/status")
def get_integrations_status():
    """Whether Search Console and GA4 are connected, and what has been synced.

    Reports honestly when a source has no data yet: `connected: false` means
    credentials are not configured or no sync has run — not that Ken has no
    search traffic.
    """
    from config.settings import (GA4_PROPERTY_ID, GSC_SITE_URL,
                                 google_credentials_available)
    conn = get_db()
    out = {}
    for source in ("gsc", "ga4"):
        row = conn.execute(
            """SELECT COUNT(*) AS rows,
                      COUNT(DISTINCT node_id) AS pages_matched,
                      MAX(date_range) AS latest_window,
                      MAX(created_at) AS last_synced
               FROM integration_placeholders
               WHERE source = ? AND status = 'matched'""",
            (source,),
        ).fetchone()
        unmatched = conn.execute(
            "SELECT COUNT(DISTINCT url) FROM integration_placeholders "
            "WHERE source = ? AND status = 'unmatched'",
            (source,),
        ).fetchone()[0]
        out[source] = {
            "has_data": bool(row["rows"]),
            "metric_rows": row["rows"],
            "pages_matched": row["pages_matched"],
            "pages_not_in_inventory": unmatched,
            "latest_window": row["latest_window"],
            "last_synced": row["last_synced"],
        }
    conn.close()
    out["credentials_configured"] = google_credentials_available()
    out["gsc_property"] = GSC_SITE_URL
    out["ga4_property"] = GA4_PROPERTY_ID or None
    return out


# ── 29. Search performance for one page ──────────────────────────────────────

@app.get("/api/pages/{node_id}/search-performance")
def get_page_search_performance(node_id: str):
    """Google Search Console metrics for one page (clicks, impressions, CTR,
    average position), plus whether it sits in striking distance (positions
    4-20), where an internal link has the most leverage.

    Returns has_data=false rather than 404 when GSC has not been synced —
    the page exists, the data does not.
    """
    from config.settings import STRIKING_DISTANCE_MAX, STRIKING_DISTANCE_MIN
    conn = get_db()
    page = conn.execute(
        "SELECT node_id, url, title FROM content_nodes WHERE node_id = ?",
        (node_id,),
    ).fetchone()
    if page is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    rows = conn.execute(
        """SELECT metric_name, metric_value, date_range
           FROM integration_placeholders
           WHERE source='gsc' AND node_id=? AND status='matched'
           ORDER BY date_range DESC""",
        (node_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return {**dict(page), "has_data": False,
                "note": "No Search Console data. Run scripts/19_sync_gsc.py "
                        "(needs credentials)."}
    window = rows[0]["date_range"]
    metrics = {r["metric_name"]: r["metric_value"]
               for r in rows if r["date_range"] == window}
    position = metrics.get("position")
    return {
        **dict(page),
        "has_data": True,
        "date_range": window,
        "clicks": metrics.get("clicks"),
        "impressions": metrics.get("impressions"),
        "ctr": metrics.get("ctr"),
        "position": position,
        "in_striking_distance": (
            position is not None
            and STRIKING_DISTANCE_MIN <= position <= STRIKING_DISTANCE_MAX
        ),
    }


# ── 30b. GA4 analytics for one page (the GA4 twin of search-performance) ─────

@app.get("/api/pages/{node_id}/analytics")
def get_page_analytics(node_id: str):
    """Google Analytics (GA4) metrics for one page (sessions, users, engaged
    sessions, average engagement seconds, key events / conversions).

    Returns has_data=false rather than 404 when GA4 has not been synced for the
    page. Use this to prove the GA4 connection: cross-check a number here
    against the same page in GA4's Pages-and-screens report for the same dates.
    """
    conn = get_db()
    page = conn.execute(
        "SELECT node_id, url, title FROM content_nodes WHERE node_id = ?",
        (node_id,),
    ).fetchone()
    if page is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Page '{node_id}' not found")
    rows = conn.execute(
        """SELECT metric_name, metric_value, date_range
           FROM integration_placeholders
           WHERE source='ga4' AND node_id=? AND status='matched'
           ORDER BY date_range DESC""",
        (node_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return {**dict(page), "has_data": False,
                "note": "No GA4 data. Run scripts/20_sync_ga4.py (needs credentials)."}
    window = rows[0]["date_range"]
    m = {r["metric_name"]: r["metric_value"]
         for r in rows if r["date_range"] == window}
    return {
        **dict(page),
        "has_data": True,
        "date_range": window,
        "sessions": m.get("sessions"),
        "users": m.get("users"),
        "engaged_sessions": m.get("engaged_sessions"),
        "avg_engagement_seconds": m.get("avg_engagement_seconds"),
        "conversions": m.get("key_events"),
    }


# ── 30. Striking-distance pages: the GSC-driven priority list ────────────────

@app.get("/api/opportunities/striking-distance")
def get_striking_distance_pages(
    limit: int = Query(50, ge=1, le=500),
):
    """Pages ranking 4-20 in Google, highest impressions first.

    Master PRD 11.3: these gain the most from internal links — close enough to
    page 1 that a push moves them, far enough that the traffic gain is large.
    Combined with business_priority, this is the highest-ROI target list in the
    whole system.

    Empty with has_data=false until Search Console is synced.
    """
    from config.settings import STRIKING_DISTANCE_MAX, STRIKING_DISTANCE_MIN
    conn = get_db()
    rows = conn.execute(
        """SELECT n.node_id, n.url, n.title, n.business_priority,
                  n.internal_links_in, n.page_authority_score,
                  MAX(CASE WHEN p.metric_name='position'    THEN p.metric_value END) AS position,
                  MAX(CASE WHEN p.metric_name='impressions' THEN p.metric_value END) AS impressions,
                  MAX(CASE WHEN p.metric_name='clicks'      THEN p.metric_value END) AS clicks,
                  MAX(CASE WHEN p.metric_name='ctr'         THEN p.metric_value END) AS ctr
           FROM integration_placeholders p
           JOIN content_nodes n ON n.node_id = p.node_id
           WHERE p.source='gsc' AND p.status='matched' AND n.status='active'
           GROUP BY n.node_id
           HAVING position BETWEEN ? AND ?
           ORDER BY impressions DESC
           LIMIT ?""",
        (STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX, limit),
    ).fetchall()
    conn.close()
    return {
        "has_data": bool(rows),
        "count": len(rows),
        "position_range": [STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX],
        "pages": [dict(r) for r in rows],
        "note": None if rows else
                "No Search Console data yet. Run scripts/19_sync_gsc.py.",
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


# ═════════════════════════════════════════════════════════════════════════════
# Manual interlinking workbench (/users)
# ═════════════════════════════════════════════════════════════════════════════
# A human pastes a report URL, reads that page's real content here, and
# records where a link should go and why. Separate from the machine pipeline:
# these are human-authored instructions (manual_link_plans), not machine
# suggestions awaiting review (link_recommendations).


def _norm_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u.lower()


@app.get("/api/manual/related")
def manual_related(url: str = Query(..., description="Report URL to analyse"),
                   limit: int = Query(25, ge=1, le=100)):
    """Related, adjacent and regional pages for one URL.

    Looks in the local inventory FIRST (real relationship edges plus the
    subject gate over content_nodes), then tops up from the cached public
    sitemap - the inventory holds 500 pages but the live site has thousands,
    so a sitemap-only match is often the honest answer rather than "none".
    Every candidate passes the same market/technology subject gate the
    automated pipeline uses; geography alone never qualifies one.
    """
    from analysis.sitemap_index import (find_related_in_sitemap, slug_of,
                                       slug_to_text)
    from analysis.subject_similarity import market_technology_relevance
    from analysis.tfidf_similarity import build_corpus

    target_norm = _norm_url(url)
    conn = get_db()
    node = conn.execute(
        """SELECT node_id, url, title, market, country, region, content_type
           FROM content_nodes
           WHERE REPLACE(REPLACE(LOWER(RTRIM(url,'/')),'https://',''),
                         'http://','') = ?""", (target_norm,)).fetchone()
    if node is None:
        # The live site serves the same report under two paths - with and
        # without the /industry-reports/ prefix - and the inventory stores only
        # one of them. Matching on the slug (stable across both forms) is what
        # lets a pasted URL still reach its trusted relationship edges instead
        # of silently falling back to sitemap subject-matching.
        node = conn.execute(
            """SELECT node_id, url, title, market, country, region, content_type
               FROM content_nodes
               WHERE LOWER(REPLACE(RTRIM(url,'/'), '?', '')) LIKE ?
               LIMIT 1""", (f"%/{slug_of(url).lower()}",)).fetchone()

    from_db: list[dict] = []
    if node is not None:
        # trusted relationship edges first - these already passed Agent 3
        for r in conn.execute(
                """SELECT e.relationship_type, e.relationship_class,
                          e.confidence_score, e.market_match_score,
                          e.technology_match_score,
                          CASE WHEN e.source_node_id=? THEN t.url ELSE s.url END AS url,
                          CASE WHEN e.source_node_id=? THEN t.title ELSE s.title END AS title,
                          CASE WHEN e.source_node_id=? THEN t.content_type
                               ELSE s.content_type END AS content_type
                   FROM relationship_edges e
                   JOIN content_nodes s ON s.node_id = e.source_node_id
                   JOIN content_nodes t ON t.node_id = e.target_node_id
                   WHERE (e.source_node_id=? OR e.target_node_id=?)
                     AND e.source_node_id != e.target_node_id
                   ORDER BY e.confidence_score DESC""",
                (node["node_id"],) * 5):
            from_db.append({
                "url": r["url"], "title_guess": r["title"],
                "content_type": r["content_type"],
                "relation_label": (r["relationship_class"]
                                   or r["relationship_type"] or "related"),
                "market_match_score": r["market_match_score"] or 0.0,
                "technology_match_score": r["technology_match_score"] or 0.0,
                "combined_score": r["confidence_score"] or 0.0,
                "found_via": "inventory_edge",
                "reason": f'trusted {r["relationship_type"]} edge',
            })

        # then other inventory pages that pass the subject gate
        if len(from_db) < limit:
            source_text = " ".join(filter(None, [node["market"], node["title"]]))
            others = conn.execute(
                """SELECT url, title, market, content_type FROM content_nodes
                   WHERE status='active' AND node_id != ?""",
                (node["node_id"],)).fetchall()
            seen = {_norm_url(c["url"]) for c in from_db}
            texts = [" ".join(filter(None, [o["market"], o["title"]]))
                     for o in others]
            corpus = build_corpus([source_text] + texts)
            scored = []
            for other, text in zip(others, texts):
                if _norm_url(other["url"]) in seen:
                    continue
                rel = market_technology_relevance(corpus, source_text, text)
                if not rel.accepted:
                    continue
                scored.append({
                    "url": other["url"], "title_guess": other["title"],
                    "content_type": other["content_type"],
                    "relation_label": "adjacent",
                    "market_match_score": rel.market_score,
                    "technology_match_score": rel.technology_score,
                    "combined_score": rel.combined_score,
                    "found_via": "inventory_subject",
                    "reason": rel.reason,
                })
            scored.sort(key=lambda c: -c["combined_score"])
            from_db.extend(scored[: max(0, limit - len(from_db))])
    conn.close()

    # top up from the sitemap - always attempted, because the inventory is a
    # 500-page sample and the best real candidate is often outside it
    from_sitemap = []
    if len(from_db) < limit:
        seen = {_norm_url(c["url"]) for c in from_db}
        for cand in find_related_in_sitemap(url, limit=limit):
            if _norm_url(cand["url"]) in seen:
                continue
            from_sitemap.append(cand)
            if len(from_db) + len(from_sitemap) >= limit:
                break

    candidates = (from_db + from_sitemap)[:limit]
    return {
        "source_url": url,
        "in_inventory": node is not None,
        "source_title": node["title"] if node is not None else
                        slug_to_text(slug_of(url)).title(),
        "counts": {"from_inventory": len(from_db),
                   "from_sitemap": len(from_sitemap),
                   "total": len(candidates)},
        "candidates": candidates,
    }


@app.get("/api/manual/content")
def manual_page_content(url: str = Query(..., description="Report URL to read")):
    """The page's REAL section structure and paragraphs, so a human can read
    it here and pick the exact paragraph a link belongs in. Live read-only
    fetch; nothing is stored. Sections a link must never go in (author bio,
    FAQ, CTA, TOC, the hero stat, Market Overview) are marked, not hidden -
    the reader should see the whole page and know which parts are off limits.
    """
    from agents.agent_9_section_purpose import (NEVER_CROSS_REPORT_LINK_PURPOSES,
                                                PURPOSE_RULES, classify_heading)
    from analysis.contextual_placement import fetch_sections

    try:
        sections = fetch_sections(url)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not read that page: {type(exc).__name__}: {exc}")
    if not sections:
        return {"url": url, "section_count": 0, "sections": [],
                "note": "That page has no readable body text."}

    index = 0
    out = []
    for sec in sections:
        purpose = classify_heading(sec["heading"])
        blocked = purpose in NEVER_CROSS_REPORT_LINK_PURPOSES
        paras = []
        for text in sec["paragraphs"]:
            paras.append({"paragraph_index": index, "text": text})
            index += 1
        out.append({
            "heading": sec["heading"], "purpose": purpose,
            "linkable": not blocked,
            "guidance": PURPOSE_RULES.get(purpose, (False, ""))[1],
            "paragraphs": paras,
            "internal_link_count": sec["internal_link_count"],
        })
    return {"url": url, "section_count": len(out),
            "paragraph_count": index, "sections": out}


class ManualLinkPlan(BaseModel):
    source_url: str
    target_url: str
    anchor_text: str
    section_heading: Optional[str] = None
    paragraph_index: Optional[int] = None
    paragraph_excerpt: Optional[str] = None
    placement_note: Optional[str] = None
    relation_label: Optional[str] = None
    found_via: Optional[str] = None
    created_by: Optional[str] = "workbench-user"


@app.post("/api/manual/links")
def create_manual_link_plan(body: ManualLinkPlan):
    """Record one human-authored link decision."""
    if not body.anchor_text.strip():
        raise HTTPException(status_code=422, detail="anchor_text is required")
    if _norm_url(body.source_url) == _norm_url(body.target_url):
        raise HTTPException(status_code=422,
                            detail="a page cannot link to itself")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    plan_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO manual_link_plans
           (plan_id, source_url, target_url, anchor_text, section_heading,
            paragraph_index, paragraph_excerpt, placement_note,
            relation_label, found_via, created_by, status,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,'planned',?,?)""",
        (plan_id, body.source_url.strip(), body.target_url.strip(),
         body.anchor_text.strip(), body.section_heading,
         body.paragraph_index, body.paragraph_excerpt, body.placement_note,
         body.relation_label, body.found_via, body.created_by, now, now))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM manual_link_plans WHERE plan_id = ?", (plan_id,)).fetchone()
    conn.close()
    return {"created": True, **dict(row)}


@app.get("/api/manual/links")
def list_manual_link_plans(url: Optional[str] = Query(
        None, description="Filter to one source URL")):
    """Human-authored link decisions, newest first."""
    conn = get_db()
    if url:
        rows = conn.execute(
            """SELECT * FROM manual_link_plans
               WHERE REPLACE(REPLACE(LOWER(RTRIM(source_url,'/')),
                     'https://',''),'http://','') = ?
               ORDER BY created_at DESC""", (_norm_url(url),)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM manual_link_plans ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"count": len(rows), "plans": [dict(r) for r in rows]}


@app.delete("/api/manual/links/{plan_id}")
def delete_manual_link_plan(plan_id: str):
    conn = get_db()
    existing = conn.execute(
        "SELECT plan_id FROM manual_link_plans WHERE plan_id = ?",
        (plan_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    conn.execute("DELETE FROM manual_link_plans WHERE plan_id = ?", (plan_id,))
    conn.commit()
    conn.close()
    return {"deleted": True, "plan_id": plan_id}


@app.get("/api/manual/sitemap/status")
def manual_sitemap_status():
    """How much of Ken's public sitemap is cached, and when it was fetched."""
    from analysis.sitemap_index import cache_status
    return cache_status()


@app.post("/api/manual/sitemap/refresh")
def manual_sitemap_refresh():
    """Re-fetch Ken's sitemap index and its child sitemaps into the cache."""
    from analysis.sitemap_index import cache_status, refresh_sitemap_cache
    try:
        written = refresh_sitemap_cache()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Sitemap fetch failed: {type(exc).__name__}: {exc}")
    return {"refreshed": True, "urls_indexed": written, **cache_status()}


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
