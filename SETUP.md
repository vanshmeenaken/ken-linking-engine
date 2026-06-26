# KEN INTELLIGENCE LINKING ENGINE - SETUP
## Complete Automated Setup Instructions

**Developer:** Vansh  
**Folder Location:** `C:\Users\Vansh\Ken-Interlinking-Engine`  
**GitHub Repo:** https://github.com/vanshmeenaken/ken-linking-engine  
**Date:** June 26, 2026  
**Deadline:** 6:00 PM

---

## INSTRUCTIONS FOR CLAUDE

Read this entire file and execute ALL steps in order. This file contains everything needed to set up the project completely.

---

## STEP 1: CLONE GITHUB REPOSITORY

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
git clone https://github.com/vanshmeenaken/ken-linking-engine.git .
git status
```

**Expected:** Shows "On branch main" and working tree clean

---

## STEP 2: RUN AUTO-SETUP SCRIPT

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
python setup_phase1.py
```

**Expected:** Creates all folders (config, database, scripts, api, data, tests) and files

---

## STEP 3: MOVE FILES UP ONE LEVEL

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine

# If nested folder exists, move files up
if exist ken-linking-engine (
    move ken-linking-engine\* .
    rmdir ken-linking-engine
)

# Verify structure
dir
```

**Expected:** See config/, database/, scripts/, api/, data/, tests/ folders directly

---

## STEP 4: CREATE VIRTUAL ENVIRONMENT

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
python -m venv venv
```

**Expected:** venv folder created (takes 10-30 seconds)

---

## STEP 5: INSTALL DEPENDENCIES

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected:** Successfully installed fastapi, sqlalchemy, uvicorn, and other packages

---

## STEP 6: CREATE .ENV FILE

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
copy .env.example .env

# Verify
dir .env
```

**Expected:** .env file created in main folder

---

## STEP 7: INITIALIZE DATABASE

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
call venv\Scripts\activate.bat
python scripts/01_setup_db.py
```

**Expected:** ken_links.db created with 4 tables (content_nodes, content_entities, relationship_edges, crawl_logs)

**Verify:**
```bash
dir *.db
```

---

## STEP 8: VERIFY IMPORTS WORK

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
call venv\Scripts\activate.bat
python -c "import sqlalchemy; print('✅ SQLAlchemy OK')"
python -c "import fastapi; print('✅ FastAPI OK')"
```

**Expected:** Both show OK messages

---

## STEP 9: TEST DATABASE

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
call venv\Scripts\activate.bat
python scripts/03_validate_data.py
```

**Expected:** Shows validation report with statistics

---

## STEP 10: COMMIT TO GITHUB

```bash
cd C:\Users\Vansh\Ken-Interlinking-Engine
git add .
git commit -m "Phase 1: Initial setup - all project files and database configured"
git push origin main
```

**Expected:** Code pushed to GitHub, visible at https://github.com/vanshmeenaken/ken-linking-engine

---

## ✅ SETUP COMPLETE

Once all above steps are done:

- ✅ Folder: C:\Users\Vansh\Ken-Interlinking-Engine
- ✅ All project files created
- ✅ Virtual environment working
- ✅ All dependencies installed
- ✅ Database created (ken_links.db)
- ✅ Code pushed to GitHub
- ✅ Ready for Shrey to clone

---

## NEXT: SHREY'S SETUP

**Shrey will:**
1. Clone the repo: `git clone https://github.com/vanshmeenaken/ken-linking-engine.git`
2. Create his folder and put repo there
3. Get this same SETUP.md file (already in the repo)
4. Give Claude this file
5. Claude will do the same setup steps for Shrey (without git push)

---

**Claude: Execute all steps above in order. Confirm when complete.** ✅
