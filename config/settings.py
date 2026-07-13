import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ken_links.db")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ── Google integrations (Search Console + GA4) ───────────────────────────────
# Both read the SAME service-account JSON key. To enable:
#   1. Google Cloud Console -> create service account -> download JSON key
#   2. Enable "Google Search Console API" + "Google Analytics Data API"
#   3. Grant the service-account email access:
#      - Search Console: property -> Settings -> Users -> add (Full or Restricted)
#      - GA4: Admin -> Property Access Management -> add as Viewer
#   4. Set the vars below in .env
#
# Everything degrades gracefully when unset: the sync scripts report missing
# credentials and exit cleanly rather than breaking the pipeline.
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "")

# Search Console property, exactly as it appears in GSC.
#   domain property : sc-domain:kenresearch.com
#   URL prefix      : https://www.kenresearch.com/
GSC_SITE_URL = os.getenv("GSC_SITE_URL", "sc-domain:kenresearch.com")

# GA4 numeric property ID (Admin -> Property Settings), e.g. "123456789"
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")

# How far back each sync pulls. GSC data lags ~2-3 days; GA4 is near-real-time.
GSC_LOOKBACK_DAYS = int(os.getenv("GSC_LOOKBACK_DAYS", "28"))
GA4_LOOKBACK_DAYS = int(os.getenv("GA4_LOOKBACK_DAYS", "28"))

# "Striking distance": pages ranking here gain the most from internal links
# (master PRD 11.3 - push internal links to pages at positions 4 to 20).
STRIKING_DISTANCE_MIN = float(os.getenv("STRIKING_DISTANCE_MIN", "4"))
STRIKING_DISTANCE_MAX = float(os.getenv("STRIKING_DISTANCE_MAX", "20"))


def google_credentials_available() -> bool:
    """True only when a readable service-account key file is configured."""
    return bool(GOOGLE_CREDENTIALS_PATH) and os.path.isfile(GOOGLE_CREDENTIALS_PATH)
