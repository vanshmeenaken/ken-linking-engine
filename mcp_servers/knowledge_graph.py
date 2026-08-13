"""MCP-2 Knowledge Graph Server (master PRD section 11).

Read-only queries over the relationship index (relationship_edges +
content_entities). The PRD lists three write tools (create/update/reject
relationship); they are deliberately NOT implemented - relationship edges
are created by Agent 3's gated pipeline and reviewed by humans, and letting
an external tool mutate the graph would bypass both. Documented here rather
than silently dropped.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from mcp_servers._db import find_node_by_url, one, rows

_EDGE_COLS = """e.edge_id, e.relationship_type, e.relationship_class,
    e.relationship_direction, e.confidence_score, e.market_match_score,
    e.technology_match_score, e.status,
    s.url AS source_url, s.title AS source_title,
    t.url AS target_url, t.title AS target_title"""

_EDGE_JOIN = """FROM relationship_edges e
    JOIN content_nodes s ON s.node_id = e.source_node_id
    JOIN content_nodes t ON t.node_id = e.target_node_id"""


def get_related_entities(entity_id: str) -> list[dict]:
    """Entities related to one entity (same parent, or parent/child)."""
    ent = one("SELECT * FROM content_entities WHERE entity_id = ?", (entity_id,))
    if not ent:
        return []
    return rows(
        """SELECT entity_id, entity_name, entity_type, parent_entity_id
           FROM content_entities
           WHERE (parent_entity_id = ? OR entity_id = ?
                  OR (parent_entity_id IS NOT NULL AND parent_entity_id = ?))
             AND entity_id != ?""",
        (ent["entity_id"], ent["parent_entity_id"] or "",
         ent["parent_entity_id"] or "", entity_id))


def get_relationships_for_page(url: str) -> list[dict]:
    """Every relationship edge touching one page (either direction)."""
    node = find_node_by_url(url)
    if not node:
        return []
    return rows(
        f"""SELECT {_EDGE_COLS} {_EDGE_JOIN}
            WHERE (e.source_node_id = ? OR e.target_node_id = ?)
              AND e.source_node_id != e.target_node_id""",
        (node["node_id"], node["node_id"]))


def get_parent_child_relationships(url: str) -> dict:
    """A page's market hierarchy: its entities and their parent entities."""
    node = find_node_by_url(url)
    if not node:
        return {"found": False, "url": url}
    entities = rows(
        """SELECT ce.entity_id, ce.entity_name, ce.entity_type,
                  p.entity_name AS parent_name, p.entity_type AS parent_type
           FROM node_entities ne
           JOIN content_entities ce ON ce.entity_id = ne.entity_id
           LEFT JOIN content_entities p ON p.entity_id = ce.parent_entity_id
           WHERE ne.node_id = ?""", (node["node_id"],))
    return {"url": node["url"], "entities": entities}


def get_global_local_relationships(limit: int = 50) -> list[dict]:
    """Global-to-local market edges (a global report and its country twin)."""
    return rows(
        f"""SELECT {_EDGE_COLS} {_EDGE_JOIN}
            WHERE e.relationship_type = 'global_local' LIMIT ?""",
        (min(int(limit), 500),))


def get_country_region_relationships(limit: int = 50) -> list[dict]:
    """Country-to-region hub edges."""
    return rows(
        f"""SELECT {_EDGE_COLS} {_EDGE_JOIN}
            WHERE e.relationship_type = 'country_region' LIMIT ?""",
        (min(int(limit), 500),))


def get_case_study_relationships(url: str) -> list[dict]:
    """Case-study support edges touching one page."""
    node = find_node_by_url(url)
    if not node:
        return []
    return rows(
        f"""SELECT {_EDGE_COLS} {_EDGE_JOIN}
            WHERE e.relationship_type = 'case_study_support'
              AND (e.source_node_id = ? OR e.target_node_id = ?)""",
        (node["node_id"], node["node_id"]))


def get_evidence_relationships(url: str) -> list[dict]:
    """Agent 8 evidence links for one page: claims and their evidence pages."""
    node = find_node_by_url(url)
    if not node:
        return []
    return rows(
        """SELECT paragraph_text, section_heading, support_status,
                  evidence_target_url, evidence_type, evidence_score
           FROM paragraph_evidence_map
           WHERE node_id = ? AND evidence_target_node_id IS NOT NULL""",
        (node["node_id"],))


def get_relationship_explanation(edge_id: str) -> dict:
    """Plain-English explanation of one relationship edge."""
    edge = one(
        f"SELECT {_EDGE_COLS} {_EDGE_JOIN} WHERE e.edge_id = ?", (edge_id,))
    if not edge:
        return {"found": False, "edge_id": edge_id}
    labels = {
        "same_market": "cover the same market in different countries",
        "adjacent_market": "cover closely related markets in the same industry",
        "global_local": "are the global and local views of the same market",
        "country_region": "are a country page and its regional hub",
        "report_article_support": "are a report and an article discussing it",
        "case_study_support": "are a report and a case study evidencing it",
    }
    what = labels.get(edge["relationship_type"],
                      f'are related by "{edge["relationship_type"]}"')
    return {**edge, "explanation": (
        f'"{edge["source_title"]}" and "{edge["target_title"]}" {what} '
        f'(confidence {edge["confidence_score"]:.2f}).')}


server = MCPServer(
    name="ken-knowledge-graph",
    instructions="Read-only queries over Ken Research's page-relationship "
                 "graph and entity hierarchy. Edge creation/mutation is "
                 "deliberately not exposed (Agent 3 pipeline + human review "
                 "own that).")
for fn in (get_related_entities, get_relationships_for_page,
           get_parent_child_relationships, get_global_local_relationships,
           get_country_region_relationships, get_case_study_relationships,
           get_evidence_relationships, get_relationship_explanation):
    server.add_tool(fn)

if __name__ == "__main__":
    server.run()
