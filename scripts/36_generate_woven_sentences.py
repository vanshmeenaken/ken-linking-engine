"""Generate and store the natural-language woven sentence for every active
contextual placement, via the NVIDIA LLM with a deterministic fallback.

For each active (status != 'rejected') contextual_body recommendation with
a suggested_sentence: ask integrations.nvidia_llm.llm_weave_sentence to
rewrite it naturally with the anchor woven in. If the LLM is unavailable or
its output fails verification (anchor missing, a number dropped), fall back
to the deterministic template in analysis/sentence_composer.py - the
pipeline never breaks because an external API had a bad moment.

Idempotent: re-running regenerates every row from scratch (use --only-
template-fallbacks to retry only the rows that fell back last time, once
API issues are resolved).

Usage:
    python scripts/36_generate_woven_sentences.py --dry-run
    python scripts/36_generate_woven_sentences.py --limit 5 --dry-run
    python scripts/36_generate_woven_sentences.py
    python scripts/36_generate_woven_sentences.py --only-template-fallbacks
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from analysis.sentence_composer import weave_anchor_into_sentence
from integrations.nvidia_llm import api_keys, llm_weave_sentence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"


def _rows(conn: sqlite3.Connection, limit: int | None,
         only_template_fallbacks: bool,
         only_missing: bool = False) -> list[sqlite3.Row]:
    where = ["status != 'rejected'", "placement_type = 'contextual_body'",
             "suggested_sentence IS NOT NULL"]
    if only_template_fallbacks:
        where.append("woven_sentence_source = 'template'")
    if only_missing:
        # scripts/22 clears woven_sentence whenever it changes a placement,
        # so "missing" == "re-placed since the last generation run"
        where.append("woven_sentence IS NULL")
    q = (f"SELECT recommendation_id, anchor_text, relationship_type, "
         f"suggested_sentence FROM link_recommendations "
         f"WHERE {' AND '.join(where)}")
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q).fetchall()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-template-fallbacks", action="store_true",
                        help="regenerate only rows that fell back to the "
                             "template last time")
    parser.add_argument("--only-missing", action="store_true",
                        help="generate only rows with no stored rewrite yet "
                             "(i.e. re-placed since the last run)")
    parser.add_argument("--workers", type=int, default=0,
                        help="parallel workers (default: one per API key)")
    parser.add_argument("--breaker", type=int, default=5,
                        help="consecutive API failures before falling back to "
                             "template wording for the rest of the run")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = _rows(conn, args.limit, args.only_template_fallbacks,
                 args.only_missing)
    print(f"Rows to process: {len(rows)}")

    # One worker per configured API key - the API takes ~10s per call, so a
    # serial run over ~130 links is impractically slow. Each worker owns a
    # distinct key so parallelism does not concentrate rate-limit pressure
    # on one credential.
    keys = api_keys() or [None]
    workers = min(len(keys), max(1, args.workers or len(keys)))
    print(f"API keys available: {len(keys)}   parallel workers: {workers}")

    # Circuit breaker: when the endpoint is down, every row would otherwise
    # burn the full request timeout before falling back (124 rows x 45s / 4
    # workers = ~23 minutes of pure waiting). After this many consecutive
    # failures, stop calling the API and use the template for the rest of the
    # run - a fallback run then finishes in seconds, and
    # --only-template-fallbacks upgrades those rows once the API is healthy.
    breaker_limit = max(1, args.breaker)
    state = {"consecutive_failures": 0, "open": False}
    lock = Lock()

    def _one(index_and_row):
        i, r = index_and_row
        key = keys[i % len(keys)]
        woven = source = None
        with lock:
            skip_api = state["open"]
        if not skip_api:
            woven = llm_weave_sentence(r["suggested_sentence"], r["anchor_text"],
                                       api_key=key)
            with lock:
                if woven is None:
                    state["consecutive_failures"] += 1
                    if state["consecutive_failures"] >= breaker_limit:
                        if not state["open"]:
                            print(f"  ! {breaker_limit} consecutive API "
                                  f"failures - using template wording for the "
                                  f"rest of this run", flush=True)
                        state["open"] = True
                else:
                    state["consecutive_failures"] = 0
        if woven is None:
            woven = weave_anchor_into_sentence(
                r["suggested_sentence"], r["anchor_text"], r["relationship_type"])
            source = "template"
        else:
            source = "llm"
        return woven, source, r["recommendation_id"]

    def _flush(batch: list[tuple]) -> None:
        """Commit a batch. Writing incrementally (not once at the very end)
        means an interrupted run keeps the rows it already generated - an
        earlier version lost ~70 rows of work when a wrapper timeout killed
        it just before its single final commit."""
        if not batch or args.dry_run:
            return
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "UPDATE link_recommendations SET woven_sentence=?, "
            "woven_sentence_source=? WHERE recommendation_id=?", batch)
        conn.commit()

    total_written = 0
    pending: list[tuple] = []
    by_source = {"llm": 0, "template": 0}
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_one, (i, r)): r
                   for i, r in enumerate(rows)}
        for fut in as_completed(futures):
            woven, source, rec_id = fut.result()
            by_source[source] += 1
            pending.append((woven, source, rec_id))
            done += 1
            if done <= 5 or done % 10 == 0 or done == len(rows):
                print(f"  [{done}/{len(rows)}] ({source}) {woven[:90]}...",
                      flush=True)
            if len(pending) >= 20:
                _flush(pending)
                total_written += len(pending)
                pending = []
    _flush(pending)
    total_written += len(pending)

    print(f"\nvia LLM: {by_source['llm']}   via template fallback: {by_source['template']}")
    if args.dry_run:
        print("Database update: skipped (dry run)")
    else:
        print(f"Database update: committed ({total_written} rows)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
