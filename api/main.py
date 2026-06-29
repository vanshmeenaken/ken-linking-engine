import sqlite3
import os
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from config.settings import API_HOST, API_PORT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "ken_links.db")

app = FastAPI(title="KEN Interlinking Engine")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/health")
def health():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM content_nodes").fetchone()[0]
    conn.close()
    return {"status": "ok", "total_pages": total}


@app.get("/api/stats")
def stats():
    start = time.time()
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM content_nodes").fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE status = 'active'"
    ).fetchone()[0]
    orphan = conn.execute(
        "SELECT COUNT(*) FROM content_nodes WHERE orphan_status IS NOT NULL AND orphan_status != ''"
    ).fetchone()[0]
    avg_links = conn.execute(
        "SELECT ROUND(AVG(internal_links_in), 2) FROM content_nodes"
    ).fetchone()[0] or 0.0

    # content type breakdown
    content_types = {}
    for row in conn.execute(
        "SELECT COALESCE(NULLIF(content_type,''),'unknown') as ct, COUNT(*) c "
        "FROM content_nodes GROUP BY ct ORDER BY c DESC"
    ):
        content_types[row["ct"]] = row["c"]

    # industry breakdown
    industries = {}
    for row in conn.execute(
        "SELECT COALESCE(NULLIF(industry,''),'unknown') as ind, COUNT(*) c "
        "FROM content_nodes GROUP BY ind ORDER BY c DESC LIMIT 20"
    ):
        industries[row["ind"]] = row["c"]

    # country breakdown
    countries = {}
    for row in conn.execute(
        "SELECT COALESCE(NULLIF(country,''),'unknown') as co, COUNT(*) c "
        "FROM content_nodes GROUP BY co ORDER BY c DESC LIMIT 20"
    ):
        countries[row["co"]] = row["c"]

    # global vs local
    scope = {}
    for row in conn.execute(
        "SELECT COALESCE(NULLIF(global_or_local,''),'unknown') as gl, COUNT(*) c "
        "FROM content_nodes GROUP BY gl ORDER BY c DESC"
    ):
        scope[row["gl"]] = row["c"]

    # field completeness
    critical_fields = ["url", "title", "content_type", "country", "global_or_local"]
    completeness = {}
    for f in critical_fields:
        filled = conn.execute(
            f"SELECT COUNT(*) FROM content_nodes WHERE {f} IS NOT NULL AND {f} != ''"
        ).fetchone()[0]
        completeness[f] = round(filled / total * 100, 1) if total else 0

    conn.close()

    elapsed_ms = round((time.time() - start) * 1000, 1)

    return {
        "total_pages":    total,
        "active_pages":   active,
        "orphan_pages":   orphan,
        "avg_links_in":   avg_links,
        "content_types":  content_types,
        "industries":     industries,
        "countries":      countries,
        "scope":          scope,
        "field_completeness": completeness,
        "response_time_ms":   elapsed_ms,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
