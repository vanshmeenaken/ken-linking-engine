# MCP Design Pack

## Status

Design only. No MCP server is built in Phase 2. This document sets the
boundaries so later phases build against a fixed plan.

## Purpose

MCP (Model Context Protocol) is the standardized tool-access layer between the
LLM/agents and Ken's approved internal systems. Instead of hardcoding every
integration into the application, each approved system is exposed as an MCP
server that offers a specific, scoped set of tools. This document accounts for
all 12 servers the master PRD requires (section 10.4), their tools, their
read/write boundary, and which phase each is built in.

## Hard rules (apply to every server)

- Read-only by default. Write and publish tools are separate and gated.
- No tool publishes to the live site or CMS without human approval (master PRD
  section 26).
- Every server exposes only its approved tools; permissions are scoped per
  server, not shared.
- Every tool call is logged.
- Invalid or unauthorized tool calls fail safely.

## The 12 servers

| Server | Purpose | Access | Phase |
|---|---|---|---|
| Content Inventory | page + entity metadata lookup | read | 2 (foundation exists as API) |
| Knowledge Graph | query/update entities and relationships | read + gated write | 2 (foundation exists as API) |
| Crawler | crawl + link-health audit | read | 2 (reuses Agent 1 logic) |
| SEO Rules | validate a proposed link | read | 2 (exists as Agent 10) |
| Search Console | search performance data | read | 3 (data live; tools later) |
| GA4 | behaviour + conversion data | read | 3 (data live; tools later) |
| Report Store | report catalog access | read | 3+ (depends on store access) |
| Embedding Search | semantic similarity search | read | 3 |
| CMS | draft edits + link insertion | gated write | 4 |
| Jira | recommendations to tickets | write (own system) | 4 |
| Deployment | apply approved changes | gated write | 4 |
| Evidence Library | paragraph-to-evidence | read | 5 |

## Phase 2 servers (foundations already exist)

These four are backed by working code today, exposed as REST endpoints; wrapping
them as MCP tools is a thin layer in a later phase.

### Content Inventory MCP (read)
`get_page_by_url`, `get_page_by_id`, `search_pages`, `list_pages_by_industry`,
`list_pages_by_country`, `get_orphan_pages`, `get_page_entities`,
`get_page_relationships`. Backed by the `/api/pages`, `/api/entities`, and
`/api/opportunities` endpoints.

### Knowledge Graph MCP (read + gated write)
`get_entity_by_name`, `search_entities`, `get_related_entities`,
`get_relationships_for_page`, `get_relationship_explanation` are read.
`create_relationship_edge`, `update_relationship_status` are writes and require
review. Backed by the `/api/relationships` and `/api/entities` endpoints.

### Crawler MCP (read)
`crawl_url`, `get_internal_links`, `check_canonical`, `check_indexability`,
`detect_redirect`, `get_broken_links`. Reuses Agent 1's crawl and hub-redirect
detection logic.

### SEO Rules MCP (read)
`validate_canonical_target`, `validate_indexability`, `validate_anchor_text`,
`validate_faceted_url_risk`, `validate_link_count`, `validate_redirect_risk`.
Backed by Agent 10 and `POST /api/internal-linking/validate`.

## Later-phase servers

- Search Console MCP and GA4 MCP (Phase 3): the data is already synced into
  `integration_placeholders`; these servers expose it as tools
  (`get_page_queries`, `get_pages_ranking_positions_4_to_20`,
  `get_page_sessions`, `get_conversion_events`, and similar). Read-only.
- Embedding Search MCP (Phase 3): `semantic_search_pages`,
  `find_similar_reports`, `find_similar_articles`, backed by the TF-IDF
  similarity foundation.
- CMS, Jira, Deployment MCP (Phase 4): the only servers with write or publish
  tools. All gated behind human approval; no auto-publish in V1.
- Report Store MCP (Phase 3+) and Evidence Library MCP (Phase 5): depend on
  systems and data not yet in scope.

## MCP host and clients

The host is the internal AI application used by the SEO, content, and tech
teams (a dashboard, a chat assistant, or a CMS sidebar). The client sits inside
the host and talks only to approved servers. Neither is built in Phase 2.
