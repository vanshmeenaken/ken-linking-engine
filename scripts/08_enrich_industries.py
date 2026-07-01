"""Fill missing content_nodes.industry values from URL/title/H1 evidence.

The original CSV contained blank industries for many pages. This script uses a
reviewable keyword taxonomy to update only blank industry fields in both the
SQLite database and scripts/sample_urls.csv, then writes an audit CSV showing
which keyword caused each assignment.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "ken_links.db"
CSV_PATH = ROOT / "scripts" / "sample_urls.csv"
AUDIT_PATH = ROOT / "reports" / "industry_enrichment_audit.csv"

# Ordered from more specific taxonomy signals to broader market words.
INDUSTRY_RULES = [
    ("pharmaceuticals", [
        "pharma", "pharmaceutical", "drug", "vaccine", "branded generics",
        "protein purification", "protein isolation", "molecular biology",
        "enzyme", "enzymes", "reagents", "gene synthesis", "herpes infection",
        "herpangina", "fucoidan", "nutraceutical", "clinical nutrition",
        "contract manufacturing services", "api market", "regulatory affairs",
        "dietary supplements", "supplements", "eye health supplements",
    ]),
    ("healthcare", [
        "healthcare", "health care", "hospital", "clinic", "clinics",
        "diagnostic", "diagnostics", "blood screening", "blood iv",
        "cath lab", "cath labs", "bone growth", "ulcerative colitis",
        "flow cytometry", "microscope", "ecg", "holter", "retinopathy",
        "corneal", "pen needle", "prenatal", "wheelchair", "hydrocephalus",
        "orthodontics", "pediatric", "virtual visits", "fertility",
        "vagus nerve", "immunoassay", "clia", "medical", "patient",
        "dental", "cardiac", "syringe", "cancer", "diabetes devices",
        "therapeutic",
        "therapeutics", "sepsis", "home healthcare", "medtech",
    ]),
    ("aerospace & defense", [
        "torpedo", "unmanned systems", "tactical communication", "command control",
        "c2 systems", "rocket systems", "airsoft guns", "aviation", "uav",
        "drone", "light sport aircraft", "defense", "defence",
    ]),
    ("it & telecom", [
        "application container", "serverless", "application performance",
        "microprocessor", "euv lithography", "semiconductor", "mini led",
        "micro led", "flip chip", "silicon photonics", "quantum sensors",
        "quantum computing", "image recognition", "byod", "networking",
        "embedded security", "intent based", "cloud", "software", "cybersecurity",
        "router", "switch", "telecom", "communications", "digital front door",
        "physical security", "pc market", "data center", "data centre",
        "pricing software", "ai powered", "ai-driven", "smart air purifier",
        "iot", "edtech", "elearning", "e-learning", "interactive whiteboard",
        "it services", "vcp", "vcpe", "hard disk", "mems", "sensor",
    ]),
    ("bfsi", [
        "credit scoring", "loan", "loans", "bank", "banking", "insurance",
        "remittance", "wealth management", "digital payments", "nbfc",
        "finance", "fintech", "p2p lending", "home finance", "loan aggregator",
        "car loan", "unsecured lending", "payments", "bnpl",
    ]),
    ("automotive", [
        "auto repair", "air deflector", "bike market", "bicycle", "bicycle sharing",
        "battery management system", "ev ", " ev", "electric vehicle", "vehicle",
        "car", "automotive", "bus", "scooter", "tractor", "tyre", "tire",
        "dealership", "passenger car", "car rental", "leasing", "after sales",
        "off road", "genset", "gensets", "diesel genset",
    ]),
    ("energy & utilities", [
        "electric generators", "uranium enrichment", "battery market", "refinery", "refineries",
        "oil", "gas", "energy", "renewable", "coal", "power", "solar",
        "bess", "fuel additives", "led lighting",
    ]),
    ("logistics & transportation", [
        "railway", "locomotive", "commercial laundry", "logistics", "warehousing",
        "freight", "cold chain", "cold storage", "delivery", "transportation",
        "taxi", "air cargo", "ambulance", "parking solutions", "parking management",
        "material handling",
    ]),
    ("construction & real estate", [
        "decorative concrete", "hvac", "residential market", "construction", "real estate",
        "facility management", "hospitality", "interior design", "cement", "tile",
        "external insulation", "workplace transformation", "structural steel",
        "property", "asphalt mixing", "building", "epc",
    ]),
    ("food & beverage", [
        "dragon fruit", "processed pumpkin", "quillaia", "confectionery", "coffee",
        "tea market", "pectin", "food", "beverage", "grocery", "pickles",
        "organic food", "mushroom", "citrus", "chilli", "camel milk", "yogurt",
        "bottled water", "restaurant", "catering", "meal", "ready to eat",
        "superfood", "acai", "edible oil", "functional foods", "sea moss",
    ]),
    ("agriculture", [
        "glufosinate", "turf protection", "poultry", "agriculture", "agri",
        "fertilizer", "farming", "ginger oil", "shrimp",
    ]),
    ("chemicals & materials", [
        "packaging", "detergents", "oleochemicals", "cyclohexane", "phosphate esters",
        "butanediol", "pentanediamine", "polyethyleneimine", "reflective materials",
        "benzene", "toluene", "xylene", "btx", "radiation cured", "asphalt",
        "ceramide", "security paper", "refrigerant", "low gwp", "xenon",
        "smart card materials", "compostable paper", "cleaning products", "bakelite",
        "paper tray", "protective equipment", "flame arrestor", "microcrystalline wax",
        "tanning agents", "plastic pipe", "synthetic resin", "bonded abrasives",
        "quinones", "paint", "paints", "coatings", "lubricant", "steel",
        "rubber", "plastics", "synthetic leather", "wool", "colour cosmetics",
        "basalt fiber", "advanced materials", "functional materials", "chemical",
        "chemicals", "materials", "inorganic catalyst", "catalyst",
    ]),
    ("manufacturing & industrial", [
        "machine tools", "atomic absorption spectrometer", "distributed control",
        "turboexpander", "non-destructive testing", "ndt", "industrial",
        "manufacturing", "equipment", "power tools", "air brake", "mooring",
        "industrial equipment", "ipo readiness", "benchmarking", "pump",
    ]),
    ("consumer goods", [
        "connected thermostat", "sleep wellness", "football shoes", "sportswear",
        "air purifier", "home water filtration",
        "pet boarding", "baby bottle", "hair care", "camping coolers", "mattress",
        "fashion accessories", "furniture", "sports equipment", "toys", "luggage",
        "fitness", "home furniture", "consumer durables", "blankets", "wedding",
        "luxury", "cosmetics", "beauty", "halal hair care",
    ]),
    ("retail & e-commerce", [
        "homeshopping", "e-commerce", "ecommerce", "online grocery", "classifieds",
        "marketplaces", "online classifieds", "retail", "pharmacy", "online travel",
    ]),
    ("education", [
        "education", "k12", "k8", "curriculum", "school", "schools",
        "student", "upsc", "executive education", "vocational training",
        "higher education",
    ]),
    ("media & entertainment", [
        "anime", "movies", "tv shows", "corporate branding", "branding",
        "media", "entertainment", "ott", "gaming", "igaming", "advertising",
        "sports streaming",
    ]),
    ("textiles & apparel", ["fashion", "textile", "apparel"]),
    ("travel & tourism", ["travel", "tourism", "hotel"]),
    ("mining & metals", ["mining", "metal", "metals", "copper"]),
]


def evidence_text(row: sqlite3.Row | dict[str, str]) -> str:
    values = [row.get(key, "") if isinstance(row, dict) else row[key] for key in ("url", "title", "h1", "content_type", "country")]
    text = " ".join(str(value or "") for value in values).lower().replace("&amp;", "&")
    return re.sub(r"[_/-]+", " ", text)


def classify(row: sqlite3.Row | dict[str, str]) -> tuple[str, str]:
    text = evidence_text(row)
    for industry, keywords in INDUSTRY_RULES:
        for keyword in keywords:
            if keyword in text:
                return industry, keyword
    return "", ""


def db_rows(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn, conn.execute(
            """SELECT node_id,url,title,h1,content_type,country
            FROM content_nodes
            WHERE industry IS NULL OR industry = ''
            ORDER BY rowid"""
        ).fetchall()
    except Exception:
        conn.close()
        raise


def update_csv(csv_path: Path, assignments: dict[str, tuple[str, str]]) -> int:
    rows = []
    changed = 0
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for row in reader:
            url = row.get("url", "")
            if url in assignments and not (row.get("industry") or "").strip():
                row["industry"] = assignments[url][0]
                changed += 1
            rows.append(row)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--csv", default=str(CSV_PATH))
    parser.add_argument("--audit", default=str(AUDIT_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn, rows = db_rows(Path(args.db))
    assignments: dict[str, tuple[str, str]] = {}
    audit_rows = []
    unmatched = []
    for row in rows:
        industry, keyword = classify(row)
        if industry:
            assignments[row["url"]] = (industry, keyword)
            audit_rows.append({
                "url": row["url"],
                "title": row["title"] or "",
                "content_type": row["content_type"] or "",
                "country": row["country"] or "",
                "assigned_industry": industry,
                "matched_keyword": keyword,
                "method": "keyword_taxonomy",
            })
        else:
            unmatched.append(row)

    if unmatched:
        print(f"ERROR: {len(unmatched)} rows still lack industry classification")
        for row in unmatched[:20]:
            print(row["url"])
        conn.close()
        return 2

    if args.dry_run:
        print(f"Dry run: would update {len(assignments)} DB rows")
    else:
        try:
            conn.execute("BEGIN IMMEDIATE")
            timestamp = datetime.now(timezone.utc).isoformat()
            for url, (industry, _keyword) in assignments.items():
                conn.execute(
                    """UPDATE content_nodes
                    SET industry = ?, updated_at = ?
                    WHERE url = ? AND (industry IS NULL OR industry = '')""",
                    (industry, timestamp, url),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        csv_changed = update_csv(Path(args.csv), assignments)
        audit_path = Path(args.audit)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0].keys()))
            writer.writeheader()
            writer.writerows(audit_rows)
        print(f"Updated DB rows: {len(assignments)}")
        print(f"Updated CSV rows: {csv_changed}")
        print(f"Audit: {audit_path}")

    counts = Counter(industry for industry, _keyword in assignments.values())
    for industry, count in sorted(counts.items()):
        print(f"{industry}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


