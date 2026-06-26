# QUICK START (5 MINUTES)

Get up and running in 5 minutes.

## Prerequisites
- Python 3.11+
- Git
- ~200 MB disk space

## Setup Steps

```bash
# 1. Clone
git clone https://github.com/vanshmeenaken/ken-linking-engine.git
cd ken-linking-engine

# 2. Create environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
# OR: venv\Scripts\activate  # Windows

# 3. Install
pip install -r requirements.txt

# 4. Initialize database
python scripts/01_setup_db.py

# 5. Load data
python scripts/02_load_urls.py scripts/sample_urls.csv

# 6. Verify
python scripts/03_validate_data.py
```

## What You'll Get

✅ 4 database tables  
✅ 500 Ken Research URLs  
✅ Full schema ready for agents  
✅ Everything on GitHub

---

**Need help?** → `03-TROUBLESHOOTING.md`  
**Want details?** → `02-DETAILED-SETUP.md`
