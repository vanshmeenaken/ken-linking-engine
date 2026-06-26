# PROJECT STRUCTURE

Complete folder layout with descriptions.

## Root Level

```
ken-linking-engine/
├── docs/                      Documentation (YOU ARE HERE)
├── source_of_truth/           Original source materials (archived)
├── api/                       FastAPI server (Day 6+)
├── config/                    Configuration files
├── database/                  SQLAlchemy models & schema
├── scripts/                   Setup & utility scripts
├── tests/                     Unit tests
├── data/                      Output data
├── venv/                      Python virtual environment
│
├── README.md                  Project overview
├── LICENSE                    MIT License
├── SETUP.md                   Detailed setup (archived)
├── requirements.txt           Python dependencies
├── .env.example               Environment template
├── .gitignore                 Git rules
└── ken_links.db              SQLite database
```

## docs/ Structure (10 Sections)

```
docs/
├── 01-PROJECT/               What & why we're building
├── 02-SETUP/                 Getting started (setup/troubleshooting)
├── 03-DATABASE/              Database schema & queries
├── 04-DEVELOPMENT/           Code structure & standards
├── 05-PHASES/                Progress & timeline (Days 1-10)
├── 06-TESTING/               Test strategy & procedures
├── 07-DEPLOYMENT/            Production & scaling
├── 08-API/                   API endpoints & examples
├── 09-AGENTS/                Agent documentation
└── 10-REFERENCE/             Glossary & FAQ
```

## Module Descriptions

### api/
- `main.py` - FastAPI application entry point
- `__init__.py` - Module init

### config/
- `settings.py` - Configuration values
- `__init__.py` - Module init

### database/
- `db.py` - SQLAlchemy setup & session management
- `models.py` - All 4 table definitions
- `__init__.py` - Module init

### scripts/
- `01_setup_db.py` - Create database schema
- `02_load_urls.py` - Load URLs from CSV
- `03_validate_data.py` - Data quality validation
- `__init__.py` - Module init

### tests/
- `test_database.py` - Database tests
- `__init__.py` - Module init

---

**See also:** `02-CODE-STANDARDS.md` for coding conventions
