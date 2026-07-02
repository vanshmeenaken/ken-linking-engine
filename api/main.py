import sqlite3
import os
import time
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse

from config.settings import API_HOST, API_PORT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "ken_links.db")

app = FastAPI(
    title="Ken Intelligence Linking Engine",
    description="Phase 1: Foundation & Data Layer",
    version="1.0.0",
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── 1. Health check ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "Ken Intelligence Linking Engine Phase 1"}


# ── 2. Database statistics ───────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
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


# ── 3. List all pages (paginated) ────────────────────────────────────────────

@app.get("/api/pages")
def list_pages(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    country: Optional[str] = Query(None, description="Filter by country"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
):
    conn = get_db()
    where_clauses = []
    params: list = []

    if industry:
        where_clauses.append("industry = ?")
        params.append(industry)
    if country:
        where_clauses.append("country = ?")
        params.append(country)
    if content_type:
        where_clauses.append("content_type = ?")
        params.append(content_type)

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


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
