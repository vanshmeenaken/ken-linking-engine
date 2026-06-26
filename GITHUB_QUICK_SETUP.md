# GITHUB REPO SETUP - QUICK VERSION

## Create Repo (Vansh)
```
1. https://github.com/new
2. Name: ken-linking-engine
3. Private ✓
4. Create
5. Settings → Collaborators → Add Shrey
```

## Shrey Accepts
Accept email invite from GitHub

## Both Clone
```bash
git clone https://github.com/YOUR_USERNAME/ken-linking-engine.git
cd ken-linking-engine
```

## Vansh: Setup Project
```bash
# Save setup_phase1.py in the folder
python3 setup_phase1.py

# Move files up
mv ken-linking-engine/* .
rm -rf ken-linking-engine/

# Commit
git add .
git commit -m "Phase 1: Initial setup"
git push origin main
```

## Both: Setup Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# OR venv\Scripts\activate  # Windows

pip install -r requirements.txt
python scripts/01_setup_db.py
```

## Shrey: Pull Latest
```bash
git pull origin main
```

## Daily Workflow
```bash
# Start: pull latest
git pull origin main

# Work: edit files

# End: push changes
git add .
git commit -m "Your change"
git push origin main
```

Done. Ready to build Phase 1.
