# MCP Servers

Nine of the master PRD's twelve MCP servers are implemented (section 11).
CMS, Deployment, and Jira are excluded with Agent 12: deployment belongs to
the tech team, and no publish tool may exist in this system (PRD section 26).

## Purpose

An MCP server lets any MCP-capable AI tool (Claude Code, Claude Desktop, and
others) query the linking engine's data directly: look up pages, walk the
relationship graph, run semantic search, validate a proposed link, or read
the synced Search Console / GA4 numbers.

## The servers

| Server | Module | Backed by | Tools |
| --- | --- | --- | --- |
| ken-content-inventory | `mcp_servers/content_inventory.py` | content_nodes | 13 |
| ken-knowledge-graph | `mcp_servers/knowledge_graph.py` | relationship_edges, content_entities | 8 |
| ken-embedding-search | `mcp_servers/embedding_search.py` | analysis/vector_store.py | 8 |
| ken-evidence-library | `mcp_servers/evidence_library.py` | paragraph_evidence_map (Agent 8) | 8 |
| ken-seo-rules | `mcp_servers/seo_rules.py` | Agent 10 rule engine | 8 |
| ken-crawler | `mcp_servers/crawler.py` | crawl_logs + live section crawl | 9 |
| ken-search-console | `mcp_servers/search_console.py` | synced GSC data | 8 |
| ken-ga4 | `mcp_servers/ga4.py` | synced GA4 data | 6 |
| ken-report-store | `mcp_servers/report_store.py` | content_nodes (reports) | 8 |

## Read-only guarantee

Every server opens the database in SQLite read-only mode (`mode=ro`), so no
tool can modify state even by accident. Two deliberate exceptions, both
specified by the PRD and both internal-only:

- `map_paragraph_to_evidence` and `flag_unsupported_claim` (Evidence
  Library) annotate `paragraph_evidence_map` rows. They never touch link
  recommendations or the live site.

The Knowledge Graph server deliberately omits the PRD's three edge-mutation
tools (`create_relationship_edge`, `update_relationship_confidence`,
`reject_relationship`): relationship edges are created only by Agent 3's
gated pipeline and reviewed by humans.

## Running a server

```powershell
python -m mcp_servers.content_inventory
```

Each runs over stdio. Claude Code picks all nine up automatically from the
repo-root `.mcp.json`.

## Verification

`tests/test_mcp_servers.py` calls every tool function directly against the
live database (27 tests). The stdio protocol layer was verified end to end
with the MCP client SDK (initialize, list_tools, call_tool round-trip).

## Honest limitations

- GA4 tools for scroll depth, internal link clicks, lead sources, and
  assisted conversions are absent: the GA4 property has no such custom
  events yet. They are not simulated.
- GSC per-page search queries are not stored by the current sync
  (page-level clicks/impressions/ctr/position are).
- Chart/table search is section-level (the crawler counts tables and images
  per section); per-asset indexing does not exist yet.
