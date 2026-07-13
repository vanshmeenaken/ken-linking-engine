"""Tests for the GSC/GA4 integration plumbing (integrations/).

The API calls themselves need live credentials, so they are not tested here.
What IS tested is the load-bearing local logic: URL normalisation and
node matching (if this is wrong, every metric lands on the wrong page or on
no page at all), date windowing, and storage upsert behaviour.
"""

import sqlite3

import pytest

from integrations.common import (CredentialsMissing, date_range, load_credentials,
                                 normalise_url, store_metrics, url_to_node_map)


# ── URL normalisation: the matching key between Google and content_nodes ─────

@pytest.mark.parametrize("raw,expected", [
    # GSC returns absolute URLs; GA4 returns bare paths. Both must collapse
    # to the same key or metrics never attach to a node.
    ("https://www.kenresearch.com/kuwait-freight-trucking-market",
     "/kuwait-freight-trucking-market"),
    ("/kuwait-freight-trucking-market", "/kuwait-freight-trucking-market"),
    ("kuwait-freight-trucking-market", "/kuwait-freight-trucking-market"),
    # trailing slash, scheme, www, case, query string and fragment must not
    # split one page into several
    ("https://www.kenresearch.com/kuwait-freight-trucking-market/",
     "/kuwait-freight-trucking-market"),
    ("http://kenresearch.com/Kuwait-Freight-Trucking-Market",
     "/kuwait-freight-trucking-market"),
    ("https://www.kenresearch.com/kuwait-freight-trucking-market?utm_source=x",
     "/kuwait-freight-trucking-market"),
    ("https://www.kenresearch.com/kuwait-freight-trucking-market#toc",
     "/kuwait-freight-trucking-market"),
    ("", ""),
])
def test_normalise_url(raw, expected):
    assert normalise_url(raw) == expected


def test_gsc_and_ga4_forms_of_same_page_match(tmp_path):
    # The whole point: an absolute GSC URL and a bare GA4 path for the same
    # page must resolve to the same node_id.
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE content_nodes (node_id TEXT, url TEXT)")
    conn.execute("INSERT INTO content_nodes VALUES ('n1', "
                 "'https://www.kenresearch.com/india-ev-market')")
    conn.commit()
    node_map = url_to_node_map(conn)
    conn.close()

    gsc_form = "https://www.kenresearch.com/india-ev-market"   # GSC style
    ga4_form = "/india-ev-market"                              # GA4 style
    assert node_map[normalise_url(gsc_form)] == "n1"
    assert node_map[normalise_url(ga4_form)] == "n1"


# ── date window ──────────────────────────────────────────────────────────────

def test_date_range_ends_yesterday_and_spans_requested_days():
    from datetime import date, timedelta
    start, end = date_range(28)
    # ends yesterday: today's data is incomplete in both GSC and GA4 and would
    # understate every metric
    assert end == (date.today() - timedelta(days=1)).isoformat()
    assert (date.fromisoformat(end) - date.fromisoformat(start)).days == 27


# ── storage ──────────────────────────────────────────────────────────────────

def _store_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("""CREATE TABLE integration_placeholders (
        integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT, node_id TEXT, url TEXT, metric_name TEXT,
        metric_value REAL, date_range TEXT, status TEXT, notes TEXT,
        created_at TEXT)""")
    return conn


def test_store_metrics_marks_matched_and_unmatched(tmp_path):
    conn = _store_db(tmp_path)
    rows = [
        {"url": "/a", "node_id": "n1", "metric_name": "clicks", "metric_value": 5.0},
        {"url": "/unknown", "node_id": None, "metric_name": "clicks", "metric_value": 2.0},
    ]
    matched, unmatched = store_metrics(conn, "gsc", rows, "2026-01-01..2026-01-28")
    assert (matched, unmatched) == (1, 1)
    statuses = dict(conn.execute(
        "SELECT url, status FROM integration_placeholders").fetchall())
    # unmatched rows are STORED, not dropped — dropping them would hide the
    # coverage gap between Google's view of the site and our 500-page inventory
    assert statuses == {"/a": "matched", "/unknown": "unmatched"}
    conn.close()


def test_store_metrics_is_idempotent_for_same_window(tmp_path):
    conn = _store_db(tmp_path)
    rows = [{"url": "/a", "node_id": "n1", "metric_name": "clicks", "metric_value": 5.0}]
    window = "2026-01-01..2026-01-28"
    store_metrics(conn, "gsc", rows, window)
    store_metrics(conn, "gsc", rows, window)  # re-run must not duplicate
    n = conn.execute("SELECT COUNT(*) FROM integration_placeholders").fetchone()[0]
    assert n == 1
    conn.close()


def test_store_metrics_keeps_other_sources_and_windows(tmp_path):
    conn = _store_db(tmp_path)
    r = [{"url": "/a", "node_id": "n1", "metric_name": "clicks", "metric_value": 1.0}]
    store_metrics(conn, "gsc", r, "w1")
    store_metrics(conn, "ga4", r, "w1")   # different source: must survive
    store_metrics(conn, "gsc", r, "w2")   # different window: must survive
    store_metrics(conn, "gsc", r, "w1")   # re-run of the first: replaces only itself
    n = conn.execute("SELECT COUNT(*) FROM integration_placeholders").fetchone()[0]
    assert n == 3
    conn.close()


# ── credential handling ──────────────────────────────────────────────────────

def test_missing_credentials_raise_actionable_error(monkeypatch):
    # Without a key the sync must fail with a clear, fixable message rather
    # than an opaque Google SDK traceback.
    monkeypatch.setattr("config.settings.GOOGLE_CREDENTIALS_PATH", "")
    monkeypatch.setattr("config.settings.google_credentials_available",
                        lambda: False)
    with pytest.raises(CredentialsMissing) as exc:
        load_credentials(["scope"])
    assert "GOOGLE_CREDENTIALS_PATH" in str(exc.value)
