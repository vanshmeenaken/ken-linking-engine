"""Build TF-IDF semantic vectors for every active page (Phase 2, Day 2).

Assembles each page's document (title + H1 + meta description + extracted
entity names), fits a TF-IDF corpus over all active pages, and stores the
per-page unit vector in semantic_embeddings as sparse JSON. text_hash lets a
re-run skip pages whose source text is unchanged.

Usage:
    python scripts/16_build_semantic_embeddings.py [--dry-run] [--top-similar N]

--top-similar N prints, for a few sample pages, their N most similar pages —
a quick eyeball check that the similarity signal is sane before Agent 3
consumes it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.tfidf_similarity import build_corpus, cosine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "ken_links.db"
EMBEDDING_MODEL = "tfidf-v1"


def load_page_documents(conn) -> dict[str, dict]:
    """Per active page: its text sources + assembled document string."""
    pages = {
        row["node_id"]: {
            "url": row["url"],
            "parts": [row["title"] or "", row["h1"] or "", row["meta_description"] or ""],
        }
        for row in conn.execute(
            "SELECT node_id, url, title, h1, meta_description "
            "FROM content_nodes WHERE status='active'"
        )
    }
    # Append market + industry entity names — the SUBJECT signal. Deliberately
    # NOT country/region: geography is already present in titles, and adding it
    # again just inflates "same-country" similarity over "same-subject"
    # similarity (dry-run showed north-america-tablet matching
    # north-america-xenon purely on shared geography). The market entity name
    # is geography-stripped ("Infusion Pumps Market", not "Saudi ... Market"),
    # so it adds pure subject weight. Cross-geography subject adjacency
    # (Saudi infusion pumps <-> Middle East insulin infusion pumps) is exactly
    # what we want to surface.
    for row in conn.execute(
        """SELECT ne.node_id, ce.entity_name
           FROM node_entities ne
           JOIN content_entities ce ON ce.entity_id = ne.entity_id
           WHERE ne.status != 'rejected'
             AND ce.entity_type IN ('market','industry')"""
    ):
        if row["node_id"] in pages:
            pages[row["node_id"]]["parts"].append(row["entity_name"])
    for p in pages.values():
        p["document"] = " ".join(part for part in p["parts"] if part)
    return pages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top-similar", type=int, default=0)
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    pages = load_page_documents(conn)
    documents = [p["document"] for p in pages.values()]
    corpus = build_corpus(documents)
    print(f"Corpus: {len(pages)} pages, {len(corpus.idf)} unique terms")

    vectors = {nid: corpus.vector(p["document"]) for nid, p in pages.items()}

    if args.top_similar:
        node_ids = list(pages)
        sample = node_ids[:3] + node_ids[len(node_ids) // 2: len(node_ids) // 2 + 2]
        print(f"\n=== sample: top-{args.top_similar} similar pages ===")
        for nid in sample:
            scored = sorted(
                ((cosine(vectors[nid], vectors[other]), other)
                 for other in pages if other != nid),
                reverse=True,
            )[:args.top_similar]
            print(f"\n{pages[nid]['url'].replace('https://www.kenresearch.com/','')}")
            for score, other in scored:
                print(f"  {score:.3f}  {pages[other]['url'].replace('https://www.kenresearch.com/','')}")

    if args.dry_run:
        print("\nDry run — nothing written.")
        conn.close()
        return 0

    now = datetime.now(timezone.utc).isoformat()
    written, skipped = 0, 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = {
            row["node_id"]: row["text_hash"]
            for row in conn.execute("SELECT node_id, text_hash FROM semantic_embeddings")
        }
        for nid, p in pages.items():
            text_hash = hashlib.sha256(p["document"].encode("utf-8")).hexdigest()
            vec_json = json.dumps(vectors[nid], separators=(",", ":"))
            if existing.get(nid) == text_hash:
                # source text unchanged, but IDF may have shifted corpus-wide;
                # refresh the vector anyway to keep scores consistent
                conn.execute(
                    "UPDATE semantic_embeddings SET embedding_vector=?, updated_at=? "
                    "WHERE node_id=?",
                    (vec_json, now, nid),
                )
                skipped += 1
                continue
            conn.execute(
                """INSERT INTO semantic_embeddings
                   (embedding_id, node_id, text_hash, source_text, embedding_model,
                    embedding_vector, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(node_id) DO UPDATE SET
                       text_hash=excluded.text_hash, source_text=excluded.source_text,
                       embedding_model=excluded.embedding_model,
                       embedding_vector=excluded.embedding_vector,
                       updated_at=excluded.updated_at""",
                (str(uuid.uuid4()), nid, text_hash, p["document"], EMBEDDING_MODEL,
                 vec_json, now, now),
            )
            written += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\nEmbeddings written (new/changed): {written}")
    print(f"Refreshed (text unchanged): {skipped}")
    print(f"Total in table: {written + skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
