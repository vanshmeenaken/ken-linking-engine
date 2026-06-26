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
- **19-column** relationship scoring system
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
├── api/                      FastAPI server (coming Day 6)
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
- **relationship_edges** (19 cols) — Typed connections with scoring
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

### Run tests
```bash
pytest tests/
```

## 📋 Status

**Day 1 (Jun 26):** ✅ COMPLETE
- GitHub repo setup
- Project structure
- Python environment
- Extended database schema
- 500 URLs loaded

**Days 2-10:** IN PROGRESS
- Follow `source_of_truth/PHASE_1_PROFESSIONAL_PROJECT_PLAN.md`

## 📞 Support

- **Questions?** Check `source_of_truth/INDEX.md` for documentation
- **Issues?** Check `source_of_truth/` folder for comprehensive docs
- **Architecture?** See `SCHEMA_VISUAL.md`

## 📄 License

MIT License - See LICENSE file

---

**Built with:** Python, FastAPI, SQLAlchemy, SQLite  
**Status:** Phase 1 Foundation - Production Ready  
**Team:** Vansh (Lead) + Shrey (QA)  
**Deadline:** Phase 1 complete by July 5, 2026
