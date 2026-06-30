"""
Rebuilds sample_urls.csv with a balanced content mix:
  300 reports  (kept from existing CSV)
  100 articles (from article sitemap)
  100 case studies (from casestudy sitemap)
  ─────────────────────────────────────
  500 total

Run: python scripts/04_rebuild_csv.py
"""

import csv
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_IN  = os.path.join(ROOT, "scripts", "sample_urls.csv")
CSV_OUT = os.path.join(ROOT, "scripts", "sample_urls.csv")

# ── country keywords → country label ─────────────────────────────────────────
COUNTRY_MAP = {
    "india": "india", "indian": "india",
    "uae": "uae", "dubai": "uae",
    "ksa": "saudi arabia", "saudi": "saudi arabia", "saudi-arabia": "saudi arabia",
    "vietnam": "vietnam",
    "indonesia": "indonesia",
    "malaysia": "malaysia",
    "philippines": "philippines",
    "qatar": "qatar",
    "oman": "oman",
    "bahrain": "bahrain",
    "kuwait": "kuwait",
    "gcc": "gcc",
    "mena": "mena",
    "japan": "japan",
    "australia": "australia",
    "europe": "europe",
    "us": "usa", "usa": "usa",
    "uk": "uk",
    "france": "france",
    "germany": "germany",
    "china": "china",
    "kenya": "kenya",
    "norway": "norway",
    "singapore": "singapore",
    "thailand": "thailand",
    "bangladesh": "bangladesh",
    "israel": "israel",
    "iraq": "iraq",
    "latam": "latin america",
    "apac": "apac",
    "global": "global",
    "southeast-asia": "southeast asia", "southeast": "southeast asia",
    "sea": "southeast asia",
    "middle-east": "middle east",
    "north-america": "north america",
}

# ── industry keywords ─────────────────────────────────────────────────────────
INDUSTRY_MAP = {
    "automotive": "automotive", "car": "automotive", "vehicle": "automotive",
    "ev": "automotive", "electric-bus": "automotive", "tractor": "automotive",
    "two-wheeler": "automotive", "ebike": "automotive",
    "healthcare": "healthcare", "hospital": "healthcare", "dialysis": "healthcare",
    "pharma": "pharmaceuticals", "pharmaceutical": "pharmaceuticals",
    "fintech": "bfsi", "banking": "bfsi", "insurance": "bfsi", "loan": "bfsi",
    "bfsi": "bfsi", "payments": "bfsi", "lending": "bfsi", "bnpl": "bfsi",
    "edtech": "education", "education": "education", "k12": "education",
    "logistics": "logistics & transportation", "warehousing": "logistics & transportation",
    "cold-chain": "logistics & transportation", "freight": "logistics & transportation",
    "air-cargo": "logistics & transportation", "delivery": "logistics & transportation",
    "energy": "energy & utilities", "solar": "energy & utilities", "bess": "energy & utilities",
    "oil": "energy & utilities", "gas": "energy & utilities", "coal": "energy & utilities",
    "food": "food & beverage", "beverage": "food & beverage", "snack": "food & beverage",
    "chocolate": "food & beverage", "edible": "food & beverage", "grocery": "food & beverage",
    "retail": "retail & e-commerce", "ecommerce": "retail & e-commerce",
    "e-commerce": "retail & e-commerce",
    "real-estate": "construction & real estate", "real_estate": "construction & real estate",
    "construction": "construction & real estate", "housing": "construction & real estate",
    "telecom": "it & telecom", "semiconductor": "it & telecom", "tech": "it & telecom",
    "software": "it & telecom", "cloud": "it & telecom", "data-center": "it & telecom",
    "gaming": "media & entertainment", "ott": "media & entertainment",
    "agriculture": "agriculture", "agri": "agriculture", "farming": "agriculture",
    "fertilizer": "agriculture", "shrimp": "agriculture",
    "chemicals": "chemicals & materials", "steel": "chemicals & materials",
    "rubber": "chemicals & materials", "plastics": "chemicals & materials",
    "lubricant": "chemicals & materials",
    "manufacturing": "manufacturing & industrial", "industrial": "manufacturing & industrial",
    "fitness": "consumer goods", "beauty": "consumer goods", "cosmetics": "consumer goods",
    "furniture": "consumer goods", "luxury": "consumer goods",
}

def slug_to_title(slug):
    """Convert URL slug to Title Case string."""
    slug = slug.split("/")[-1]
    slug = re.sub(r"[-_]", " ", slug)
    return slug.title()

def detect_country(slug):
    slug_lower = slug.lower()
    parts = re.split(r"[-/]", slug_lower)
    for part in parts:
        if part in COUNTRY_MAP:
            return COUNTRY_MAP[part]
    for key, val in COUNTRY_MAP.items():
        if key in slug_lower:
            return val
    return "global"

def detect_industry(slug):
    slug_lower = slug.lower()
    for key, val in INDUSTRY_MAP.items():
        if key in slug_lower:
            return val
    return ""

# ── article URLs ──────────────────────────────────────────────────────────────
ARTICLE_URLS = [
    "https://www.kenresearch.com/articles/gcc-dental-equipment-market-opportunities-forecast",
    "https://www.kenresearch.com/articles/genset-after-sales-crisis-india-service-benchmark",
    "https://www.kenresearch.com/articles/indian-car-buyers-consider-ev-but-choose-ice",
    "https://www.kenresearch.com/articles/india-api-market-dependency-to-dominance",
    "https://www.kenresearch.com/articles/india-bess-market-storage-revolution",
    "https://www.kenresearch.com/articles/india-busbar-value-chain-design-control",
    "https://www.kenresearch.com/articles/india-ev-market-sustainability-to-economics",
    "https://www.kenresearch.com/articles/india-personal-loan-market-trust-gap",
    "https://www.kenresearch.com/articles/india-health-insurance-consumer-behavior-forecast",
    "https://www.kenresearch.com/articles/hospital-emergency-trust-deficit-india",
    "https://www.kenresearch.com/articles/battery-confidence-shaping-india-ev-scooter-future",
    "https://www.kenresearch.com/articles/conocophillips-cost-advantage-us-oil-market",
    "https://www.kenresearch.com/articles/uae-cement-market-outlook-entry-opportunity",
    "https://www.kenresearch.com/articles/philippines-unsecured-lending-growth-digital-credit-opportunity",
    "https://www.kenresearch.com/articles/india-mould-market-manufacturing-vs-imports-competitive-gap",
    "https://www.kenresearch.com/articles/india-bpc-growth-opportunity-brand-equity",
    "https://www.kenresearch.com/articles/gcc-luxury-market-concentration-uae-ksa-strategy",
    "https://www.kenresearch.com/articles/vietnam-mushroom-imports-vs-domestic-production-gap",
    "https://www.kenresearch.com/articles/saudi-arabia-logistics-trends-air-cargo-forecast",
    "https://www.kenresearch.com/articles/indian-construction-market-growth-lt-leadership",
    "https://www.kenresearch.com/articles/india-citrus-market-disruption-and-growth",
    "https://www.kenresearch.com/articles/future-of-india-chilli-market-2030",
    "https://www.kenresearch.com/articles/global-mattress-market-growth-fire-retardant-expansion",
    "https://www.kenresearch.com/articles/saudi-banking-deposit-concentration-digital-transactions",
    "https://www.kenresearch.com/articles/vietnam-edible-oil-supply-gap-import-dependency",
    "https://www.kenresearch.com/articles/uae-taxi-market-productivity-growth-revenue-outpaces-fleet",
    "https://www.kenresearch.com/articles/ksa-retail-pharmacy-market-foreign-investor-opportunity",
    "https://www.kenresearch.com/articles/saudi-digital-payments-market-cashless-economy-growth",
    "https://www.kenresearch.com/articles/uae-luxury-hospitality-premiumisation-growth",
    "https://www.kenresearch.com/articles/india-pet-food-market-leadership-shift-mars-vs-drools",
    "https://www.kenresearch.com/articles/malaysia-automotive-aftermarket-recurring-service-demand",
    "https://www.kenresearch.com/articles/uae-luxury-furniture-market-demand-surge-uhnwis",
    "https://www.kenresearch.com/articles/indonesia-poultry-producers-market",
    "https://www.kenresearch.com/articles/india-candle-manufacturing-cost-advantage-refinery-model",
    "https://www.kenresearch.com/articles/akzonobel-growth-strategy-vietnam-paints-market",
    "https://www.kenresearch.com/articles/india-makhana-market-future-and-export-opportunity",
    "https://www.kenresearch.com/articles/india-fintech-early-stage-deals-ma-activity",
    "https://www.kenresearch.com/articles/vietnam-fertilizer-market-bfc-revenue-growth-margins",
    "https://www.kenresearch.com/articles/why-automation-is-cost-of-competing-malaysia-warehousing",
    "https://www.kenresearch.com/articles/philippines-dialysis-market-coverage-driven-growth-trends",
    "https://www.kenresearch.com/articles/wakefit-growth-strategy-india-sleep-wellness",
    "https://www.kenresearch.com/articles/vietnam-natural-gas-next-investment-frontier",
    "https://www.kenresearch.com/articles/uae-lubricants-market-5-players-reshaping-profitability",
    "https://www.kenresearch.com/articles/uae-furniture-market-growth-residential-demand-expats",
    "https://www.kenresearch.com/articles/india-infrastructure-capex-reshaping-heavy-equipment-market",
    "https://www.kenresearch.com/articles/oman-hospitality-market-occupancy-rising-60-percent",
    "https://www.kenresearch.com/articles/india-eye-health-supplements-demand-shift",
    "https://www.kenresearch.com/articles/india-sportswear-market-tier2-tier3-opportunity",
    "https://www.kenresearch.com/articles/philippines-credit-access-transformation-fintech-bnpl",
    "https://www.kenresearch.com/articles/smart-air-purifier-market-profit-battleground",
    "https://www.kenresearch.com/articles/india-air-cargo-belly-capacity-dominance",
    "https://www.kenresearch.com/articles/used-car-dominance-transforming-iraq-vehicle-market",
    "https://www.kenresearch.com/articles/indonesia-plastic-pipe-market-spec-led-growth",
    "https://www.kenresearch.com/articles/saudi-arabia-fitness-market-winner-strategy",
    "https://www.kenresearch.com/articles/malaysia-led-market-policy-support-impact",
    "https://www.kenresearch.com/articles/ksa-automotive-growth-strategy-vision-2030",
    "https://www.kenresearch.com/articles/saudi-perfume-market-growth-premium-consumption",
    "https://www.kenresearch.com/articles/india-kiwi-market-growth-import-dependence",
    "https://www.kenresearch.com/articles/indonesia-mortgage-growth-rewiring-real-estate",
    "https://www.kenresearch.com/articles/healthkart-protein-market-india-profit-fy25",
    "https://www.kenresearch.com/articles/indonesia-car-rental-leasing-market-b2b-ota-dominance",
    "https://www.kenresearch.com/articles/europe-truck-leasing-market-growth-transformation",
    "https://www.kenresearch.com/articles/vietnam-fintech-payments-growth-profitability",
    "https://www.kenresearch.com/articles/india-confectionery-market-growth-but-low-exports",
    "https://www.kenresearch.com/articles/global-banking-resilience-growth-strategy",
    "https://www.kenresearch.com/articles/japan-transport-infrastructure-margins-outlook",
    "https://www.kenresearch.com/articles/automotive-suppliers-profitability-reset-global",
    "https://www.kenresearch.com/articles/india-coffee-exports-competitive-gap-analysis",
    "https://www.kenresearch.com/articles/saudi-residential-market-growth-after-foreign-ownership-2026",
    "https://www.kenresearch.com/articles/saudi-arabia-chocolate-market-trends-and-outlook",
    "https://www.kenresearch.com/articles/global-autonomous-vehicles-growth-emerging-markets",
    "https://www.kenresearch.com/articles/india-industrial-gases-regional-shift-market-outlook",
    "https://www.kenresearch.com/articles/saudi-retail-future-2030-riyadh-dominance",
    "https://www.kenresearch.com/articles/vietnam-vaccine-market-future-2030",
    "https://www.kenresearch.com/articles/saudi-hospitality-market-future",
    "https://www.kenresearch.com/articles/india-warehousing-market-future",
    "https://www.kenresearch.com/articles/global-gaming-industry-structural-shifts-2030",
    "https://www.kenresearch.com/articles/kenya-retail-real-estate-demand-trends",
    "https://www.kenresearch.com/articles/saudi-real-estate-market-affordability-pressure",
    "https://www.kenresearch.com/articles/china-manufacturing-disruption-global-market",
    "https://www.kenresearch.com/articles/australia-retail-market-recovery-growth",
    "https://www.kenresearch.com/articles/global-tea-market-growth-shifts-by-region",
    "https://www.kenresearch.com/articles/ksa-automotive-market-competitive-shift",
    "https://www.kenresearch.com/articles/southeast-asia-lubricants-market-future-2030",
    "https://www.kenresearch.com/articles/ott-market-growth-strategy-global",
    "https://www.kenresearch.com/articles/india-catering-industry-future-regional-economics",
    "https://www.kenresearch.com/articles/gcc-healthcare-market-forecast-trends",
    "https://www.kenresearch.com/articles/india-fashion-market-future-growth",
    "https://www.kenresearch.com/articles/global-energy-transition-trends-and-investment-needs",
    "https://www.kenresearch.com/articles/india-steel-growth-coking-coal-supply-gap",
    "https://www.kenresearch.com/articles/saudi-construction-growth-forecast-2030-insights",
    "https://www.kenresearch.com/articles/india-coking-coal-imports-forecast-supplier-analysis",
    "https://www.kenresearch.com/articles/bubble-tea-market-india-manufacturing-roadmap",
    "https://www.kenresearch.com/articles/vegan-food-industry-transformation-2025-strategic-outlook",
    "https://www.kenresearch.com/articles/used-car-market-opportunity-ksa-al-futtaim-strategy",
    "https://www.kenresearch.com/articles/saudi-arabia-mining-market-growth-outlook-2030",
    "https://www.kenresearch.com/articles/india-wedding-industry-economic-impact-and-forecast",
    "https://www.kenresearch.com/articles/vietnam-semiconductor-strategy-future-investment",
    "https://www.kenresearch.com/articles/food-delivery-market-digital-shift-and-opportunities",
]

# ── case study URLs ───────────────────────────────────────────────────────────
CASESTUDY_URLS = [
    "https://www.kenresearch.com/case-studies/india-sports-equipment-industry-forecast-2025",
    "https://www.kenresearch.com/case-studies/southeast-asian-used-car-platform-market-insights",
    "https://www.kenresearch.com/case-studies/ken-research-logistics-transformation-insights",
    "https://www.kenresearch.com/case-studies/future-of-structural-steel-market-uae-trends-analysis",
    "https://www.kenresearch.com/case-studies/uae-steel-sector-expert-engagement-transformation",
    "https://www.kenresearch.com/case-studies/hybrid-workspace-market-trends-usa",
    "https://www.kenresearch.com/case-studies/future-of-bus-market-uae-2025-strategic-growth",
    "https://www.kenresearch.com/case-studies/india-vocational-training-modernization-impact-analysis",
    "https://www.kenresearch.com/case-studies/catering-market-entry-strategy-ksa-data-assessment",
    "https://www.kenresearch.com/case-studies/philippines-cold-chain-market-entry-strategy-success",
    "https://www.kenresearch.com/case-studies/cold-storage-market-strategy-saudi-arabia",
    "https://www.kenresearch.com/case-studies/warehousing-expansion-uae-conglomerate-insights",
    "https://www.kenresearch.com/case-studies/future-growth-india-home-furniture-market",
    "https://www.kenresearch.com/case-studies/freight-warehousing-growth-strategy-kuwait",
    "https://www.kenresearch.com/case-studies/edtech-market-strategy-pricing-impact-analysis",
    "https://www.kenresearch.com/case-studies/india-plastic-pipes-market-outlook-2025-opportunities",
    "https://www.kenresearch.com/case-studies/lubricant-market-demand-mapping-malaysia-insights",
    "https://www.kenresearch.com/case-studies/india-off-road-vehicle-market-forecast-2025-growth",
    "https://www.kenresearch.com/case-studies/fmcg-supply-chain-transformation-southeast-asia",
    "https://www.kenresearch.com/case-studies/india-power-tools-market-intelligence-growth-plan",
    "https://www.kenresearch.com/case-studies/india-cement-industry-benchmarking-and-brand-strategy",
    "https://www.kenresearch.com/case-studies/uae-logistics-benchmarking-market-insights-expansion",
    "https://www.kenresearch.com/case-studies/asian-manufacturing-ipo-readiness-strategy-ken-research",
    "https://www.kenresearch.com/case-studies/curriculum-flexibility-trends-k12-education-india",
    "https://www.kenresearch.com/case-studies/uae-it-services-market-growth-opportunity",
    "https://www.kenresearch.com/case-studies/digital-lending-india-growth-100k-applications-case",
    "https://www.kenresearch.com/case-studies/india-corporate-branding-awareness-gap-analysis",
    "https://www.kenresearch.com/case-studies/india-real-estate-buyer-personas-survey-analysis",
    "https://www.kenresearch.com/case-studies/real-estate-market-insight-led-planning-case-study-india",
    "https://www.kenresearch.com/case-studies/experience-driven-loyalty-growth-automotive-industry",
    "https://www.kenresearch.com/case-studies/gcc-telecom-regulatory-insights-market-prioritization-strategy",
    "https://www.kenresearch.com/case-studies/home-healthcare-customer-acquisition-strategy-india",
    "https://www.kenresearch.com/case-studies/indonesia-data-centre-market-expansion-ken-research",
    "https://www.kenresearch.com/case-studies/bhiwandi-data-center-market-analysis-maharashtra-capex-opportunity",
    "https://www.kenresearch.com/case-studies/quantitative-brand-survey-digital-infrastructure-india",
    "https://www.kenresearch.com/case-studies/b2b-elearning-market-trends-india-it-sector",
    "https://www.kenresearch.com/case-studies/customer-satisfaction-improvement-automotive-india-case-study",
    "https://www.kenresearch.com/case-studies/india-edtech-market-acquisition-strategy",
    "https://www.kenresearch.com/case-studies/how-bfsi-leaders-drive-home-finance-market-expansion",
    "https://www.kenresearch.com/case-studies/edtech-market-entry-tier-3-schools-india",
    "https://www.kenresearch.com/case-studies/dealer-satisfaction-forecast-tractor-business-growth",
    "https://www.kenresearch.com/case-studies/passenger-car-dealer-expansion-opportunities-south-india",
    "https://www.kenresearch.com/case-studies/dealer-retention-strategy-automotive-aftermarket-north-india",
    "https://www.kenresearch.com/case-studies/future-of-student-centric-edtech-india",
    "https://www.kenresearch.com/case-studies/ken-research-k12-curriculum-strategy-case-study",
    "https://www.kenresearch.com/case-studies/dealer-visibility-gaps-consumer-durables-market-insights",
    "https://www.kenresearch.com/case-studies/malaysia-higher-education-policy-uk-australia-impact",
    "https://www.kenresearch.com/case-studies/upsc-edtech-market-research-tier2-opportunities",
    "https://www.kenresearch.com/case-studies/global-parking-solutions-market-us-entry-strategy",
    "https://www.kenresearch.com/case-studies/enhancing-logistics-strategies-gcc-automotive-sector",
    "https://www.kenresearch.com/case-studies/asian-electronics-market-ipo-readiness-valuation-uplift",
    "https://www.kenresearch.com/case-studies/ipo-success-roadmap-asian-industrial-manufacturer",
    "https://www.kenresearch.com/case-studies/toys-market-expansion-ksa-online-retail-strategy",
    "https://www.kenresearch.com/case-studies/us-acai-cafe-expansion-middle-east-strategy",
    "https://www.kenresearch.com/case-studies/ipo-readiness-2025-valuation-governance-trends",
    "https://www.kenresearch.com/case-studies/india-education-market-transformation-revenue-impact",
    "https://www.kenresearch.com/case-studies/future-of-logistics-cost-optimization-in-fmcg",
    "https://www.kenresearch.com/case-studies/cost-effective-market-entry-strategy-vietnam-pharma",
    "https://www.kenresearch.com/case-studies/ipo-strategy-logistics-sector-transformation",
    "https://www.kenresearch.com/case-studies/kuwait-automotive-leasing-growth-opportunity",
    "https://www.kenresearch.com/case-studies/india-bfsi-digital-payments-scan-go-transformation",
    "https://www.kenresearch.com/case-studies/nbfc-expansion-geo-mapping-case-study-india",
    "https://www.kenresearch.com/case-studies/automotive-after-sales-benchmark-strategy-consulting",
    "https://www.kenresearch.com/case-studies/dealership-expansion-india-automobile-market-strategy",
    "https://www.kenresearch.com/case-studies/future-of-executive-education-global-market-trends",
    "https://www.kenresearch.com/case-studies/qatar-restaurant-market-penetration-strategy",
    "https://www.kenresearch.com/case-studies/how-ken-research-helped-launch-saudi-medical-fitness-center",
    "https://www.kenresearch.com/case-studies/saudi-arabia-automotive-digital-market-entry-case-study",
    "https://www.kenresearch.com/case-studies/hospital-expansion-gtm-strategy-india-case-study",
    "https://www.kenresearch.com/case-studies/india-k8-education-ecosystem-market-opportunity",
    "https://www.kenresearch.com/case-studies/ksa-loan-aggregator-market-entry-opportunity",
    "https://www.kenresearch.com/case-studies/superfood-ready-to-eat-foods-ksa-uae-forecast",
    "https://www.kenresearch.com/case-studies/agri-equipment-market-growth-strategy-india-sea",
    "https://www.kenresearch.com/case-studies/strategic-benchmarking-ipo-readiness-case-study",
    "https://www.kenresearch.com/case-studies/indonesia-dental-services-market-entry-strategy-success",
    "https://www.kenresearch.com/case-studies/fitness-strategy-consulting-case-study-saudi-arabia",
    "https://www.kenresearch.com/case-studies/bfsi-saudi-car-loan-forecasting-market-share",
    "https://www.kenresearch.com/case-studies/qatar-catering-meal-pricing-gtm-profitability",
    "https://www.kenresearch.com/case-studies/saudi-loan-market-entry-strategy",
    "https://www.kenresearch.com/case-studies/ev-battery-raw-material-suppliers-indonesia-benchmarking",
    "https://www.kenresearch.com/case-studies/philippine-bank-digital-finance-expansion-strategy",
    "https://www.kenresearch.com/case-studies/car-rental-market-entry-strategy-vs-risk-analysis",
    "https://www.kenresearch.com/case-studies/improving-customer-loyalty-and-service-perception-for-telecom-leader-in-middle-east",
    "https://www.kenresearch.com/case-studies/indonesia-p2p-lending-ecosystem-analysis-competitive-insights",
    "https://www.kenresearch.com/case-studies/ksa-luggage-market-growth-opportunity",
    "https://www.kenresearch.com/case-studies/india-agritech-market-growth-gtm-strategy",
    "https://www.kenresearch.com/case-studies/policy-impact-on-india-packaging-and-material-handling",
    "https://www.kenresearch.com/case-studies/ken-research-mena-medtech-pricing-optimization",
    "https://www.kenresearch.com/case-studies/igaming-user-behavior-strategy-india",
    "https://www.kenresearch.com/case-studies/industrial-equipment-customer-satisfaction-loyalty",
    "https://www.kenresearch.com/case-studies/tyre-care-market-entry-strategy-india",
    "https://www.kenresearch.com/case-studies/india-tile-market-entry-china-strategy",
    "https://www.kenresearch.com/case-studies/global-lubricant-market-logistics-optimization",
    "https://www.kenresearch.com/case-studies/uae-cold-storage-market-expansion-strategies",
    "https://www.kenresearch.com/case-studies/strategic-entry-data-center-epc-market-ken-research",
    "https://www.kenresearch.com/case-studies/packaging-market-entry-strategy-india",
    "https://www.kenresearch.com/case-studies/digital-agriculture-market-entry-emerging-economies",
    "https://www.kenresearch.com/case-studies/india-k12-curriculum-publishing-market-expansion",
    "https://www.kenresearch.com/case-studies/fmcg-logistics-cost-reduction-strategy",
    "https://www.kenresearch.com/case-studies/middle-east-fitness-market-strategy",
    "https://www.kenresearch.com/case-studies/latam-apac-lubricant-market-entry-strategy",
    "https://www.kenresearch.com/case-studies/southeast-asia-agricultural-equipment-market-expansion",
    "https://www.kenresearch.com/case-studies/bangladesh-clinical-lab-market-entry-strategy",
]

# ── build rows ────────────────────────────────────────────────────────────────

def make_row(url, content_type):
    slug = url.rstrip("/").split("/")[-1]
    return {
        "url":          url,
        "title":        slug_to_title(slug),
        "content_type": content_type,
        "industry":     detect_industry(slug),
        "country":      detect_country(slug),
    }

def main():
    # 1. Read existing reports, keep first 300
    with open(CSV_IN, "r", encoding="utf-8-sig", newline="") as f:
        reports = [r for r in csv.DictReader(f)
                   if (r.get("content_type") or "").strip().lower() == "report"]
    reports = reports[:300]
    print(f"Reports kept    : {len(reports)}")

    # 2. Build article rows
    articles = [make_row(u, "article") for u in ARTICLE_URLS[:100]]
    print(f"Articles added  : {len(articles)}")

    # 3. Build case study rows
    casestudies = [make_row(u, "case_study") for u in CASESTUDY_URLS[:100]]
    print(f"Case studies    : {len(casestudies)}")

    # 4. Combine and deduplicate on url
    all_rows = reports + articles + casestudies
    seen = set()
    unique = []
    for r in all_rows:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    print(f"Total unique    : {len(unique)}")

    # 5. Write CSV
    fields = ["url", "title", "content_type", "industry", "country"]
    with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(unique)

    print(f"Written to      : {CSV_OUT}")

    # content type summary
    from collections import Counter
    ct = Counter(r["content_type"] for r in unique)
    for k, v in ct.most_common():
        print(f"  {k:<15} {v}")

if __name__ == "__main__":
    main()
