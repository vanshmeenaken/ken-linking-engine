"""MCP-3 Embedding Search Server (master PRD section 11).

Semantic (vector) search over pages and paragraphs, backed by
analysis/vector_store.py. Read-only.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from analysis.vector_store import VectorStore, load_page_store
from mcp_servers._db import find_node_by_url, one, rows


@lru_cache(maxsize=1)
def _page_store() -> VectorStore:
    return load_page_store()


def _page_results(results) -> list[dict]:
    out = []
    for r in results:
        node = one("SELECT url, title, content_type FROM content_nodes "
                   "WHERE node_id = ?", (r.item_id,))
        if node:
            out.append({"score": round(r.score, 4), **node})
    return out


def semantic_search_pages(query: str, limit: int = 5) -> list[dict]:
    """Pages most semantically similar to a free-text query."""
    return _page_results(_page_store().search(query, top_k=min(int(limit), 50)))


def semantic_search_paragraphs(query: str, limit: int = 5) -> list[dict]:
    """Stored paragraphs most similar to a free-text query."""
    hits = rows(
        """SELECT p.paragraph_id, p.node_id, p.paragraph_text, n.url
           FROM paragraph_embeddings p
           JOIN content_nodes n ON n.node_id = p.node_id""")
    if not hits:
        return []
    store = VectorStore.fit(
        [(h["paragraph_id"], h["paragraph_text"]) for h in hits])
    by_id = {h["paragraph_id"]: h for h in hits}
    return [{"score": round(r.score, 4),
             "url": by_id[r.item_id]["url"],
             "paragraph": by_id[r.item_id]["paragraph_text"][:300]}
            for r in store.search(query, top_k=min(int(limit), 50))]


def _similar_to_url(url: str, content_type: str | None, limit: int) -> list[dict]:
    node = find_node_by_url(url)
    if not node:
        return []
    text = one("SELECT source_text FROM semantic_embeddings WHERE node_id = ?",
               (node["node_id"],))
    query = (text or {}).get("source_text") or " ".join(
        filter(None, [node["title"], node["market"]]))
    results = _page_store().search(query, top_k=min(int(limit), 50) + 1,
                                   exclude={node["node_id"]})
    out = _page_results(results)
    if content_type:
        out = [o for o in out if o["content_type"] == content_type]
    return out[:limit]


def find_similar_reports(report_url: str, limit: int = 5) -> list[dict]:
    """Reports most similar to the given report."""
    return _similar_to_url(report_url, "report", int(limit))


def find_similar_articles(article_url: str, limit: int = 5) -> list[dict]:
    """Articles most similar to the given page."""
    return _similar_to_url(article_url, "article", int(limit))


def find_similar_case_studies(url: str, limit: int = 5) -> list[dict]:
    """Case studies most similar to the given page."""
    return _similar_to_url(url, "case_study", int(limit))


def find_duplicate_paragraphs(paragraph_text: str) -> list[dict]:
    """Stored paragraphs with identical content (via knowledge hash)."""
    from agents.agent_8_paragraph_evidence import knowledge_hash
    return rows(
        """SELECT node_id, url, section_heading, paragraph_text
           FROM paragraph_evidence_map WHERE paragraph_hash = ?""",
        (knowledge_hash(paragraph_text),))


def find_claim_similarity(claim_text: str, limit: int = 5) -> list[dict]:
    """Market claims most similar to the given claim text."""
    claims = rows(
        """SELECT evidence_row_id, url, paragraph_text
           FROM paragraph_evidence_map
           WHERE classification = 'market_claim'""")
    if not claims:
        return []
    store = VectorStore.fit(
        [(c["evidence_row_id"], c["paragraph_text"]) for c in claims])
    by_id = {c["evidence_row_id"]: c for c in claims}
    return [{"score": round(r.score, 4), "url": by_id[r.item_id]["url"],
             "claim": by_id[r.item_id]["paragraph_text"][:300]}
            for r in store.search(claim_text, top_k=min(int(limit), 50))]


def get_embedding_similarity_score(text1: str, text2: str) -> dict:
    """Similarity (0-1) between two arbitrary texts."""
    store = VectorStore.fit([("a", text1), ("b", text2)])
    return {"similarity": round(store.similarity("a", "b"), 4)}


server = MCPServer(
    name="ken-embedding-search",
    instructions="Semantic search over Ken Research pages and paragraphs "
                 "(TF-IDF vectors today; the backend is swappable). "
                 "Read-only.")
for fn in (semantic_search_pages, semantic_search_paragraphs,
           find_similar_reports, find_similar_articles,
           find_similar_case_studies, find_duplicate_paragraphs,
           find_claim_similarity, get_embedding_similarity_score):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
