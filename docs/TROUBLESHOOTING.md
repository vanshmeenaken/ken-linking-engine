# Troubleshooting Guide

Every issue below actually happened during Phase 1 development — these are
real incidents, not hypotheticals.

---

## "Port 8000 already in use" / server won't start

**Symptom:**
```
ERROR: [Errno 10048] error while attempting to bind on address
('127.0.0.1', 8000): only one usage of each socket address is normally permitted
```

**Cause:** A previous `uvicorn` process is still running (often left over from
an earlier session or a background task that wasn't cleanly stopped).

**Fix (PowerShell):**
```powershell
$portInfo = netstat -ano | Select-String ":8000\s"
$portInfo | ForEach-Object {
    $parts = ($_ -split '\s+' | Where-Object { $_ -ne '' })
    Stop-Process -Id $parts[-1] -Force -ErrorAction SilentlyContinue
}
```
Then start the server again. Wait 2–3 seconds after killing the old process
before starting the new one — Windows can take a moment to fully release the
socket.

---

## `ModuleNotFoundError` (sqlalchemy or openai)

**Symptom:**
```
ModuleNotFoundError: No module named 'sqlalchemy'
```
or
```
ModuleNotFoundError: No module named 'openai'
```

**Cause:** This project currently has **two separate Python environments**,
and each script needs the right one:

| Script | Needs | Interpreter |
|--------|-------|--------------|
| `agents/agent_1_content_inventory.py` | `openai`, `beautifulsoup4`, `requests`, `python-dotenv` | global `python` |
| `scripts/01_setup_db.py`, `api/main.py` | `sqlalchemy` (setup only), `fastapi`, `uvicorn` | `venv\Scripts\python.exe` |

**Fix:** Match the interpreter to the script:
```bash
# Agent (global python has openai/bs4):
python agents/agent_1_content_inventory.py --workers 5

# DB setup / API server (venv has sqlalchemy/fastapi):
./venv/Scripts/python.exe scripts/01_setup_db.py
./venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

**Real fix, not a workaround:** before a production handoff, consolidate
these into a single `requirements.txt` and one virtual environment so this
split stops being a trap.

---

## "Device or resource busy" when deleting `ken_links.db`

**Symptom:**
```
rm: cannot remove 'ken_links.db': Device or resource busy
```

**Cause:** The FastAPI server (or any other process) still has the SQLite
file open. On Windows, an open file cannot be deleted out from under a
running process the way it can on Linux.

**Fix:** Stop whatever has the file open first (see "Port 8000 already in
use" above to find and kill the API server), *then* delete the file.

**Safer alternative (recommended):** Don't delete the live database at all.
Point `01_setup_db.py` / `02_load_urls.py` at a throwaway file instead, using
the `DATABASE_URL` environment variable (schema setup respects it) or by
monkey-patching a script's `DB_PATH` before calling `main()` (the loader
does not read the env var, but its `DB_PATH` module attribute can be
overridden in a one-off Python invocation). This is how the Day 8
fresh-rebuild test was verified without any risk to real data.

---

## Agent 1 seems to hang, or logs show 429 / `ConnectionError` / `ReadTimeoutError`

**Symptom:** Long pauses in the progress output, or `crawl_logs` /
console warnings mentioning `RetryError`, `ConnectionError`, or `429`.

**Cause:** Ken's server rate-limits aggressive crawling. This is expected
behavior at high worker counts, not a bug in the agent.

**Fix:**
- Reduce `--workers` (5 is the value that has worked reliably; higher counts
  like 20–40 reliably trigger rate limiting and a wall of failures)
- Add distance between passes — running the sitewide link collector
  (`scripts/05_collect_sitewide_links.py`) back-to-back at high concurrency is
  the most common trigger; space out large crawls
- If a sitewide snapshot run partially fails, use `--retry-from` to retry
  only the failed URLs and merge results into a new snapshot version, rather
  than re-crawling everything from zero:
  ```bash
  python scripts/05_collect_sitewide_links.py \
    --retry-from data/sitewide_incoming_snapshot_v2.json \
    --workers 15 --timeout 15 \
    --output data/sitewide_incoming_snapshot_v3.json
  ```

---

## API endpoint returns unexpected/stale data after a code change

**Symptom:** You edited `api/main.py` but the running server still behaves
like the old code.

**Cause:** The server process was started before your edit and needs a
restart — `uvicorn` without `--reload` does not pick up file changes
automatically.

**Fix:** Kill the existing server (see "Port 8000" fix above) and restart it.
If you want auto-reload during active development, add `--reload` to the
uvicorn command — but note this was intentionally *not* used during testing
sessions, since a mid-request reload can produce confusing intermittent
errors while debugging.

---

## Filter returns 0 results but you expected matches

**Checklist, in order:**
1. **Case:** filters are case-insensitive as of Day 7 (`India` and `india`
   both work) — if you're on an older checkout, this may not be true yet.
2. **Exact match, not substring:** `industry` and `country` require an exact
   match (case-insensitive). Use the `search` parameter for substring
   matching against URL/title instead.
3. **Check the real value first:** call `GET /api/taxonomy/industries` or
   `/api/taxonomy/countries` to see the exact spelling stored in the
   database before filtering on it.

---

## Data quality script reports a score you don't expect

Run it directly and read the per-field breakdown, not just the final score:
```bash
python scripts/03_validate_data.py
```
`region` and `published_date` are expected to show 0% — these fields are
intentionally out of Phase 1 scope (they belong to future entity/relationship
work), and are excluded from the critical-field weighting for exactly that
reason.

---

## A page shows a suspiciously huge `internal_links_in` (thousands)

**Cause (fixed as of the Day 8 hub-redirect detection):** older data may
still show this if Agent 1 hasn't been re-run since the fix. A discontinued
report page that 301-redirects to a generic hub (`/report-store`) was
inheriting that hub's own sitewide incoming-link count.

**Fix:** Re-run Agent 1 with the current codebase — this is now detected and
corrected automatically (`status='removed'`, `internal_links_in=0`,
`page_authority_score=0.0`). If it recurs for a *new* hub path, add that path
to `HUB_REDIRECT_PATHS` in `agents/agent_1_content_inventory.py`.
