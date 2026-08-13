"""MCP servers for the Ken Intelligence Linking Engine (master PRD section 11).

Nine of the PRD's twelve servers are implemented; CMS, Deployment, and Jira
are excluded with Agent 12 (deployment belongs to the tech team). All tools
are read-only against ken_links.db except the Evidence Library's two
PRD-specified internal-DB tools; nothing anywhere can touch the live site.

Run any server over stdio:
    python -m mcp_servers.content_inventory
    python -m mcp_servers.knowledge_graph
    ...

Or connect them all to Claude Code via the repo-root .mcp.json.
"""
