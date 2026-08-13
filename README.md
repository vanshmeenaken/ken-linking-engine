# Ken Intelligence Linking Engine

**An MCP-powered, LLM-assisted, agentic internal linking platform for Ken Research.**

Transform Ken's website from a content repository into a connected market intelligence graph.

---

## 🎯 What This Does

Automatically discovers, scores, and recommends internal links based on:
- Market relationships (industries → markets → segments)
- Geographic connections (global → regional → country → local)
- Content type relationships (reports ↔ articles ↔ case studies)
- Search intent alignment
- Business value and SEO opportunity

## 📊 Quick Stats

- **500+ URLs** processed in Phase 1
- **30-column** content inventory schema
- **21-column** relationship scoring system
- **14 agents** planned for full system
- **12 MCP servers** for data access and CMS integration

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Git

### Setup (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/vanshmeenaken/ken-linking-engine.git
cd ken-linking-engine

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# OR: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database
python scripts/01_setup_db.py

# 5. Load sample data (500 URLs)
python scripts/02_load_urls.py scripts/sample_urls.csv

# 6. Validate
python scripts/03_validate_data.py
```

## 📁 Project Structure

```
ken-linking-engine/
├── source_of_truth/          All authoritative documentation
│   ├── INDEX.md              Navigation guide
│   ├── SCHEMA_VISUAL.md       Complete database reference
│   ├── PHASE_1_PROFESSIONAL_PROJECT_PLAN.md
│   ├── Ken_Intelligence_Linking_PRD_Summary.md
│   └── ... (5 more docs)
│
├── api/                      FastAPI server (8 REST endpoints)
├── config/                   Configuration & settings
├── database/                 SQLAlchemy models (4 tables)
├── scripts/                  Setup, load, validate scripts
├── tests/                    Unit tests
├── venv/                     Python virtual environment
│
├── requirements.txt          Python dependencies
├── .env.example              Environment variables template
├── .gitignore                Git ignore rules
└── ken_links.db              SQLite database (500 URLs)
```

## 📚 Documentation

**Start here:**
- `source_of_truth/INDEX.md` — Navigation to all docs
- `source_of_truth/SCHEMA_VISUAL.md` — Database schema reference
- `source_of_truth/PHASE_1_PROFESSIONAL_PROJECT_PLAN.md` — 10-day timeline

**For developers:**
- `source_of_truth/SCHEMA_VISUAL.md` — Schema, relationships, indexes
- `SETUP.md` — Detailed setup instructions

**For product/leadership:**
- `source_of_truth/Ken_Intelligence_Linking_PRD_Summary.md` — Product vision
- `source_of_truth/COMPLETE_EXECUTION_PLAN_All_Agents_Servers.md` — Full roadmap

## 🏗️ Architecture

### Phase 1: Foundation (Weeks 1-2) ✅ IN PROGRESS
- Content inventory (500 URLs)
- Database schema
- Content Inventory Agent
- Basic API endpoints

### Phase 2: Intelligence Layer (Weeks 3-4)
- Entity extraction
- Relationship mapping
- Semantic search
- Scoring system

### Phase 3: Recommendation Engine (Weeks 5-6)
- Link generation
- Anchor text optimization
- SEO validation
- Editorial review workflow

### Phase 4-6: Deployment & Learning
- CMS integration
- Production scaling
- Performance measurement
- Feedback loop

## 🗄️ Database Schema

**4 Tables | 71 Columns | 15 Indexes | 500 URLs Loaded**

- **content_nodes** (30 cols) — Pages and content items
- **content_entities** (12 cols) — Markets, industries, entities
- **relationship_edges** (21 cols) — Typed connections with scoring
- **crawl_logs** (10 cols) — Operation history

See `source_of_truth/SCHEMA_VISUAL.md` for complete reference.

## 🔧 Development

### Run database setup
```bash
python scripts/01_setup_db.py
```

### Load URLs from CSV
```bash
python scripts/02_load_urls.py scripts/sample_urls.csv
```

### Validate data quality
```bash
python scripts/03_validate_data.py
```

### Run Content Inventory Agent (Agent 1)
```bash
# Required 50-page read-only validation
python agents/agent_1_content_inventory.py --limit 50 --dry-run

# Collect site-wide incoming-link evidence
python scripts/05_collect_sitewide_links.py --workers 50

# Enrich all 500 pages using the verified snapshot
python agents/agent_1_content_inventory.py --workers 50 \
  --incoming-snapshot data/sitewide_incoming_snapshot.json
```

See `docs/09-AGENTS/01-CONTENT-INVENTORY-AGENT.md` for metric definitions,
safety guarantees, evidence scope and verification commands.

### Run tests
```bash
pytest tests/
```

## 🌐 API Server

A read-only FastAPI server exposes the content inventory over REST for the
dashboard and the future Content Inventory MCP server.

### Start the server
```bash
python api/main.py
# or: python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Then open the interactive Swagger UI at **http://localhost:8000/docs**, or the
human-readable visual dashboard at **http://localhost:8000/dashboard**.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Health check |
| GET | `/api/stats` | Overall metrics (totals, orphans, avg scores) |
| GET | `/api/metrics` | Detailed breakdown (content types, industries, countries, link distribution, orphan analysis) |
| GET | `/api/pages` | List pages (paginated: `skip`, `limit`, filters incl. `search`) |
| GET | `/api/pages/orphans` | Orphan pages (0 incoming links) |
| GET | `/api/pages/{node_id}` | Single page detail (by node_id or URL fragment) |
| GET | `/api/taxonomy/industries` | Unique industries + counts (filter dropdown) |
| GET | `/api/taxonomy/countries` | Unique countries + counts (filter dropdown) |
| GET | `/docs` | Swagger UI (auto-generated) |
| GET | `/dashboard` | Visual dashboard — cards, charts, searchable table, no raw JSON |

Full request/response examples: **[docs/API.md](docs/API.md)**.

## Current Status

Phases 1-3 are complete apart from editorial review. Every master PRD agent
is built except Agent 12 (Deployment - the tech team applies approved links
manually from the CSV) and Agent 13 (Measurement - needs deployed links
first). Agents 8 and 9 landed with the section-aware crawler; 9 of the 12
MCP servers are live; the vector store has a real index backend.

- 500 pages in the local inventory.
- 447 entities and 2,021 page-to-entity mappings.
- 108 relationship edges after the market/technology rebuild.
- 135 active link recommendations (151 records including 16 retained rejections).
- 26 approved / 16 rejected / 109 pending editorial review.
- 298 active reports have PRD link-plan rows; 48 project into the 10-25 link range and 250 still need qualified candidates.
- 1,249 sections classified across 103 pages (Agent 9, section_purpose_map); placement now uses real section names and never places links in author bios, FAQs, TOCs, or CTAs.
- 1,275 paragraphs mapped (Agent 8, paragraph_evidence_map): 328 market claims, 189 unsupported, 14 with genuine evidence pages attached (three gates: similarity, geography, subject).
- Anchor rotation is intent-aware: the variant matching the link's sentence is preferred (growth sentence gets the Growth anchor).
- Every in-sentence placement carries a ready-to-paste rewrite of that sentence with the anchor woven in, written by an LLM (NVIDIA NIM, `meta/llama-3.3-70b-instruct`) and verified to preserve every original number, with a deterministic template fallback. See `docs/06-INTEGRATIONS/03-NVIDIA-LLM-SENTENCE-REWRITE.md`.
- Cross-report links are barred from a report's own opening hero stat and its Market Overview section (editorial rule): those stay focused on the report's own market.
- 9 MCP servers (76 tools) expose the system to MCP clients, read-only by construction: `.mcp.json`, docs in `docs/07-MCP/01-MCP-SERVERS.md`.
- Vector search can run on a real index (sqlite-vec) behind the unchanged VectorStore interface; brute-force stays the default. `scripts/31_vector_backend_setup.py` builds it (498 page + 911 paragraph vectors verified).
- All placements confirmed except 1 honest unresolved (a source URL that renders as an empty catalogue shell).
- Every adjacent recommendation has market relevance >= 0.30 and technology relevance >= 0.50.
- Web-team handover CSV: `reports/approved_links_handover_phase3.csv`.
- Current Phase 3 handoff: `docs/05-PHASES/PHASE-3/01-HANDOFF.md`.

Next work: review the 109 pending recommendations (human), add
industry/country/region/service pages to the inventory so report plans can
reach 10-30 opportunities, re-export the approved CSV after new approvals,
and hand it to the web team. Deployment/measurement (Agents 12/13) stay with
the tech team by design.

## 📞 Support

- **Questions?** Check `source_of_truth/INDEX.md` for documentation
- **Issues?** Check `source_of_truth/` folder for comprehensive docs
- **Architecture?** See `SCHEMA_VISUAL.md`

## 📄 License

MIT License - See LICENSE file

---

**Built with:** Python, FastAPI, SQLAlchemy, SQLite  
**Status:** Phase 3 recommendation review/export active  
**Team:** Vansh (Lead) + Shrey (QA)  
**Latest handoff:** August 10, 2026
