"""Shared plumbing for the Google integrations: URL -> node_id mapping,
credential loading, and writes into `integration_placeholders`.

Both GSC and GA4 report metrics keyed by a URL or page path. Ken's
content_nodes are keyed by node_id. Everything useful downstream (scoring,
opportunities, the linking engine) needs the metric attached to a node, so
the mapping step is the load-bearing part of both integrations — it is kept
here, once, rather than duplicated per source.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "ken_links.db"

# Read-only scopes. These integrations never write to Google — only read.
GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


class CredentialsMissing(RuntimeError):
    """Raised when a sync is attempted without usable credentials."""


# Both scopes are always requested together so the browser consent happens
# ONCE and the resulting token works for GSC and GA4 alike. Asking per-API
# would force a second login and silently invalidate the first token.
ALL_SCOPES = GSC_SCOPES + GA4_SCOPES


def load_credentials(scopes: list[str] | None = None):
    """Credentials for the Google APIs, from whichever file is configured.

    Auto-detects the credential type so the caller does not care:
      - service account  -> used directly, no interaction
      - OAuth client     -> browser consent on first run, then cached in
                            GOOGLE_TOKEN_PATH and refreshed silently forever

    `scopes` is accepted for call-site clarity but ALL_SCOPES is always used,
    so one login covers both APIs.

    Imports are deferred so the rest of the project runs without the Google
    libraries installed.
    """
    import json

    from config.settings import (GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH,
                                 google_credentials_available)

    if not google_credentials_available():
        raise CredentialsMissing(
            "No Google credentials found.\n"
            f"  GOOGLE_CREDENTIALS_PATH = {GOOGLE_CREDENTIALS_PATH or '(unset)'}\n"
            "  Point it at either an OAuth client JSON (Desktop app) or a\n"
            "  service-account key. See config/settings.py for the setup steps."
        )

    cred_path = Path(GOOGLE_CREDENTIALS_PATH)
    if not cred_path.is_absolute():
        cred_path = ROOT / cred_path

    with open(cred_path, encoding="utf-8") as fh:
        blob = json.load(fh)

    # Service account: no user interaction.
    if blob.get("type") == "service_account":
        try:
            from google.oauth2 import service_account
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise CredentialsMissing(
                "google-auth is not installed. Run: pip install -r requirements.txt"
            ) from exc
        return service_account.Credentials.from_service_account_file(
            str(cred_path), scopes=ALL_SCOPES
        )

    # OAuth client (Desktop app): browser consent once, then a cached token.
    if "installed" not in blob and "web" not in blob:
        raise CredentialsMissing(
            f"{cred_path} is neither a service-account key nor an OAuth client "
            "JSON. Re-download it from Google Cloud Console -> Credentials."
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:  # pragma: no cover - env-dependent
        raise CredentialsMissing(
            "google-auth-oauthlib is not installed. Run:\n"
            "  pip install -r requirements.txt"
        ) from exc

    token_path = Path(GOOGLE_TOKEN_PATH)
    if not token_path.is_absolute():
        token_path = ROOT / token_path

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), ALL_SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        # Silent refresh — the normal path on every run after the first.
        creds.refresh(Request())
    else:
        # First run (or the token was revoked): open a browser for consent.
        flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), ALL_SCOPES)
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message=(
                "\nA browser window is opening. Log in with the Google account "
                "that can see Search Console and GA4, then click Allow.\n"
                "If it does not open automatically, visit:\n  {url}\n"
            ),
            success_message=(
                "Authorised. You can close this tab and return to the terminal."
            ),
            open_browser=True,
        )

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    # This file grants ongoing access to the account's GSC/GA4 data.
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass  # best-effort on Windows
    return creds


def normalise_url(url: str) -> str:
    """Canonical key for matching a Google-reported URL to a content_node.

    Google reports URLs inconsistently across products and properties (GA4
    gives bare paths, GSC gives absolute URLs; either may carry a trailing
    slash, query string, fragment, http/https, or a www prefix). Reduce every
    form to a bare lowercase path so both sides compare on the same basis.
    """
    if not url:
        return ""
    url = url.strip()
    if url.startswith(("http://", "https://")):
        path = urlsplit(url).path
    else:
        path = urlsplit("//x" + ("" if url.startswith("/") else "/") + url).path
    return "/" + path.strip("/").lower()


def url_to_node_map(conn: sqlite3.Connection) -> dict[str, str]:
    """normalised path -> node_id, for every page in the inventory."""
    return {
        normalise_url(row[1]): row[0]
        for row in conn.execute("SELECT node_id, url FROM content_nodes")
        if row[1]
    }


def date_range(lookback_days: int) -> tuple[str, str]:
    """(start, end) as YYYY-MM-DD, ending yesterday.

    Ends yesterday rather than today because neither source has complete data
    for the current day; including it would understate every metric.
    """
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=lookback_days - 1)
    return start.isoformat(), end.isoformat()


def store_metrics(conn: sqlite3.Connection, source: str, rows: list[dict],
                  date_range_label: str) -> tuple[int, int]:
    """Upsert metric rows into integration_placeholders.

    Each row: {url, node_id (may be None), metric_name, metric_value, notes}.
    Rows that could not be matched to a node are still stored (node_id NULL,
    status='unmatched') — silently dropping them would hide coverage gaps.

    Returns (matched, unmatched).
    """
    matched = unmatched = 0
    now = _now()
    # Replace this source's rows for this window rather than accumulating
    # duplicates across re-runs (sync is expected to be run repeatedly).
    conn.execute(
        "DELETE FROM integration_placeholders WHERE source = ? AND date_range = ?",
        (source, date_range_label),
    )
    for r in rows:
        node_id = r.get("node_id")
        status = "matched" if node_id else "unmatched"
        if node_id:
            matched += 1
        else:
            unmatched += 1
        conn.execute(
            """INSERT INTO integration_placeholders
               (source, node_id, url, metric_name, metric_value, date_range,
                status, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (source, node_id, r["url"], r["metric_name"], r["metric_value"],
             date_range_label, status, r.get("notes"), now),
        )
    return matched, unmatched


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn
