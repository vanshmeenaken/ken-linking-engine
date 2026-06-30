"""Collect site-wide incoming-link evidence for the 500-page inventory.

Reads the official Ken Research sitemap index, crawls each listed page, and
counts unique source pages linking to each inventory URL. The JSON output is a
reusable evidence snapshot for Agent 1; no project database is modified.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, SoupStrainer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SITEMAP_INDEX = "https://www.kenresearch.com/sitemap.xml"
USER_AGENT = (
    "Mozilla/5.0 (compatible; KenResearchContentInventory/1.0; "
    "+https://www.kenresearch.com/)"
)
_local = threading.local()


def normalize_url(url: str) -> str:
    from agents.agent_1_content_inventory import normalize_url as normalize
    return normalize(url)


def session() -> requests.Session:
    if not hasattr(_local, "session"):
        value = requests.Session()
        retry = Retry(
            total=1, connect=1, read=1, backoff_factor=0.25,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)
        value.mount("https://", adapter)
        value.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        })
        _local.session = value
    return _local.session


def xml_locations(content: bytes) -> list[str]:
    root = ET.fromstring(content)
    return [node.text.strip() for node in root.findall(".//{*}loc") if node.text]


def sitemap_urls(timeout: float) -> tuple[list[str], list[str]]:
    index = session().get(SITEMAP_INDEX, timeout=timeout)
    index.raise_for_status()
    sitemaps = xml_locations(index.content)
    urls = []
    for sitemap in sitemaps:
        response = session().get(sitemap, timeout=timeout)
        response.raise_for_status()
        urls.extend(xml_locations(response.content))
    # Stable de-duplication makes results reproducible.
    return sitemaps, list(dict.fromkeys(normalize_url(url) for url in urls))


def inventory_targets(db_path: Path) -> set[str]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        targets = set()
        for url, canonical in conn.execute(
            "SELECT url,COALESCE(canonical_url,'') FROM content_nodes"
        ):
            targets.add(normalize_url(url))
            if canonical:
                targets.add(normalize_url(canonical))
        return {target for target in targets if target}
    finally:
        conn.close()


def collect_source(source_url: str, targets: set[str], timeout: float):
    started = time.perf_counter()
    try:
        response = session().get(source_url, timeout=(5.0, timeout))
        # Removed sitemap URLs cannot contribute live internal links; a
        # confirmed 404/410 is complete evidence, not an unknown crawl failure.
        if response.status_code in {404, 410}:
            return source_url, set(), "", round(time.perf_counter() - started, 3)
        if response.status_code != 200:
            return source_url, set(), f"HTTP {response.status_code}", 0.0
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            return source_url, set(), f"non-HTML {content_type}", 0.0
        anchors = BeautifulSoup(
            response.content, "html.parser", parse_only=SoupStrainer("a")
        ).find_all("a", href=True)
        matched = set()
        for anchor in anchors:
            candidate = normalize_url(urljoin(response.url, anchor.get("href", "")))
            if candidate in targets and candidate != source_url:
                matched.add(candidate)
        return source_url, matched, "", round(time.perf_counter() - started, 3)
    except Exception as exc:
        return source_url, set(), f"{type(exc).__name__}: {exc}", 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "ken_links.db"))
    parser.add_argument("--workers", type=int, default=40)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--retry-from",
        help="Retry only failures from a prior snapshot and merge results",
    )
    parser.add_argument(
        "--output", default=str(ROOT / "data" / "sitewide_incoming_snapshot.json")
    )
    args = parser.parse_args()
    started = time.perf_counter()
    base = None
    if args.retry_from:
        base = json.loads(Path(args.retry_from).read_text(encoding="utf-8"))
        sitemaps = base.get("sitemaps", [])
        sources = [item["url"] for item in base.get("failures", [])]
    else:
        sitemaps, sources = sitemap_urls(args.timeout)
    if args.limit:
        sources = sources[: args.limit]
    targets = inventory_targets(Path(args.db))
    counts = Counter({target: 0 for target in targets})
    if base:
        counts.update({key: int(value) for key, value in base.get("incoming_counts", {}).items()})
    failures = []
    timings = []
    total = len(sources)
    print(f"Official sitemaps: {len(sitemaps)}")
    print(f"Source pages: {total}")
    print(f"Inventory URL aliases: {len(targets)}")
    print(f"Workers: {args.workers}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            executor.submit(collect_source, source, targets, args.timeout)
            for source in sources
        ]
        for completed, future in enumerate(as_completed(futures), 1):
            source, matched, error, elapsed = future.result()
            if error:
                failures.append({"url": source, "error": error})
            else:
                timings.append(elapsed)
                for target in matched:
                    counts[target] += 1
            if completed % 1000 == 0 or completed == total:
                print(
                    f"Processed {completed}/{total} "
                    f"({completed * 100 // total}%), failures={len(failures)}"
                )

    elapsed = round(time.perf_counter() - started, 2)
    base_success = int(base.get("sources_successful", 0)) if base else 0
    overall_total = int(base.get("sources_total", total)) if base else total
    successful = base_success + total - len(failures)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sitemap_index": SITEMAP_INDEX,
        "sitemaps": sitemaps,
        "sources_total": overall_total,
        "sources_successful": successful,
        "sources_failed": len(failures),
        "coverage_percent": round(successful / overall_total * 100, 2) if overall_total else 0,
        "elapsed_seconds": round(elapsed + (base.get("elapsed_seconds", 0) if base else 0), 2),
        "incoming_counts": dict(sorted(counts.items())),
        "failures": failures,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Completed in {elapsed} seconds")
    print(f"Coverage: {payload['coverage_percent']}%")
    print(f"Snapshot: {output}")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
