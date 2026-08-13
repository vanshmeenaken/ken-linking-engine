"""Tests for Agent 8 Paragraph Evidence (master PRD 13.8): claim detection,
knowledge hashing, support status, and the three evidence gates (vector
threshold + geography + subject relevance)."""

import sqlite3

from agents.agent_8_paragraph_evidence import (EVIDENCE_THRESHOLD,
                                               ParagraphEvidenceAgent,
                                               build_evidence_records,
                                               is_market_claim,
                                               knowledge_hash,
                                               support_status)
from analysis.vector_store import VectorStore


# ── claim detection (regex traps) ────────────────────────────────────────────

def test_money_and_growth_claims_detected():
    assert is_market_claim("The market is worth USD 130 million in 2025.")
    assert is_market_claim("Revenue reached $4.2 billion last year.")
    assert is_market_claim("The market grew at a CAGR of 6.8% over the period.")
    assert is_market_claim("Segment A holds 26.1% of the market.")
    assert is_market_claim("The market is expected to reach new highs by 2031.")
    assert is_market_claim("Demand is valued at record levels this cycle.")


def test_bare_years_and_numberless_prose_are_not_claims():
    # a year alone is not a quantity; narrative prose is not a claim
    assert not is_market_claim("The company was founded in 2025.")
    assert not is_market_claim("Established players dominate the landscape "
                               "through brand strength and distribution reach.")
    assert not is_market_claim("Chapter 5 covers the competitive landscape.")


# ── knowledge hash ───────────────────────────────────────────────────────────

def test_knowledge_hash_stable_across_whitespace_and_case():
    a = knowledge_hash("The Market  Grew\n  Strongly.")
    b = knowledge_hash("the market grew strongly.")
    assert a == b
    assert knowledge_hash("different text entirely") != a


# ── support status matrix ────────────────────────────────────────────────────

def test_support_status_matrix():
    assert support_status(paragraph_links=1, section_links=3) == "supported"
    assert support_status(paragraph_links=0, section_links=2) == "section_supported"
    assert support_status(paragraph_links=0, section_links=0) == "unsupported"


# ── record building (structural sections excluded) ───────────────────────────

def _sec(heading, paras, links_each=0, section_links=0, order=0):
    return {"heading": heading, "order": order, "paragraphs": paras,
            "paragraph_links": [links_each] * len(paras),
            "internal_link_count": section_links,
            "table_count": 0, "image_count": 0}


def test_structural_sections_never_produce_evidence_rows():
    sections = [
        _sec("Market Overview",
             ["The market is worth USD 500 million and growing steadily."]),
        _sec("FAQs", ["The market is worth USD 500 million, per our data."]),
        _sec("About the Author - Jane:", ["We support OEMs with USD insights."]),
    ]
    records = build_evidence_records("n1", "https://x/p", sections)
    headings = {r.section_heading for r in records}
    assert "Market Overview" in headings
    assert "FAQs" not in headings
    assert "About the Author - Jane:" not in headings


def test_claims_classified_and_context_kept():
    sections = [_sec("Market Overview", [
        "The market is worth USD 500 million and growing steadily onward.",
        "Established players dominate the landscape through brand strength.",
    ])]
    records = build_evidence_records("n1", "https://x/p", sections)
    assert records[0].classification == "market_claim"
    assert records[0].support_status == "unsupported"
    assert records[1].classification == "context"
    assert records[1].support_status is None  # only claims carry a status


# ── the three evidence gates ─────────────────────────────────────────────────

def _agent_with_candidates(tmp_path, candidates):
    path = tmp_path / "evidence.db"
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE content_nodes (
        node_id TEXT PRIMARY KEY, url TEXT, title TEXT, market TEXT,
        country TEXT, content_type TEXT, status TEXT)""")
    for c in candidates:
        conn.execute("INSERT INTO content_nodes VALUES (?,?,?,?,?,?,?)",
                     (c["node_id"], c["url"], c["title"], c.get("market", ""),
                      c.get("country", ""), c.get("content_type", "report"),
                      "active"))
    conn.commit()
    conn.close()
    return ParagraphEvidenceAgent(path)


def _claim_record(node_id="src"):
    sections = [_sec("Market Overview", [
        "The China Battery Management System Market is projected to expand "
        "from USD 4,950 Mn in 2025 with battery management system adoption "
        "accelerating across electric vehicles."])]
    return build_evidence_records(node_id, "https://x/src", sections)


def test_geography_gate_blocks_cross_country_evidence(tmp_path):
    # regression: a West Africa battery report must not evidence a China claim
    agent = _agent_with_candidates(tmp_path, [
        {"node_id": "src", "url": "https://x/src",
         "title": "China Battery Management System Market", "country": "China"},
        {"node_id": "wa", "url": "https://x/wa",
         "title": "West Africa Battery Market Size Report",
         "market": "Battery", "country": "West Africa"},
    ])
    store, nodes = agent._evidence_store()
    records = _claim_record()
    source = {"market": "Battery Management System",
              "title": "China Battery Management System Market",
              "country": "China"}
    attached = agent.attach_evidence(records, store, nodes, source)
    assert attached == 0


def test_subject_gate_blocks_term_overlap_evidence(tmp_path):
    # regression: a China tire report shared "China" + automotive terms with a
    # battery-management claim and won on raw vector score before the gate
    agent = _agent_with_candidates(tmp_path, [
        {"node_id": "src", "url": "https://x/src",
         "title": "China Battery Management System Market", "country": "China"},
        {"node_id": "tire", "url": "https://x/tire",
         "title": "China Tire Industry Market Research Report",
         "market": "Tire", "country": "China"},
    ])
    store, nodes = agent._evidence_store()
    records = _claim_record()
    source = {"market": "Battery Management System",
              "title": "China Battery Management System Market",
              "country": "China"}
    attached = agent.attach_evidence(records, store, nodes, source)
    assert attached == 0


def test_genuine_same_subject_same_geo_evidence_attaches(tmp_path):
    agent = _agent_with_candidates(tmp_path, [
        {"node_id": "src", "url": "https://x/src",
         "title": "China Battery Management System Market", "country": "China"},
        {"node_id": "ev", "url": "https://x/ev",
         "title": "China Battery Management System Industry Case Study",
         "market": "Battery Management System", "country": "China",
         "content_type": "case_study"},
    ])
    store, nodes = agent._evidence_store()
    records = _claim_record()
    source = {"market": "Battery Management System",
              "title": "China Battery Management System Market",
              "country": "China"}
    attached = agent.attach_evidence(records, store, nodes, source)
    assert attached == 1
    claim = records[0]
    assert claim.evidence_target_node_id == "ev"
    assert claim.evidence_type == "case_study"
    assert claim.evidence_score >= EVIDENCE_THRESHOLD


def test_already_supported_claims_get_no_evidence(tmp_path):
    agent = _agent_with_candidates(tmp_path, [
        {"node_id": "src", "url": "https://x/src",
         "title": "China Battery Management System Market", "country": "China"},
        {"node_id": "ev", "url": "https://x/ev",
         "title": "China Battery Management System Industry Case Study",
         "market": "Battery Management System", "country": "China",
         "content_type": "case_study"},
    ])
    store, nodes = agent._evidence_store()
    sections = [{"heading": "Market Overview", "order": 0,
                 "paragraphs": ["The China Battery Management System Market "
                                "is worth USD 4,950 Mn across segments."],
                 "paragraph_links": [2],  # claim already carries links
                 "internal_link_count": 2, "table_count": 0, "image_count": 0}]
    records = build_evidence_records("src", "https://x/src", sections)
    assert records[0].support_status == "supported"
    source = {"market": "Battery Management System",
              "title": "China Battery Management System Market",
              "country": "China"}
    assert agent.attach_evidence(records, store, nodes, source) == 0


# ── live data sanity (after the live run) ────────────────────────────────────

def test_paragraph_evidence_map_populated_and_honest():
    conn = sqlite3.connect("ken_links.db")
    total = conn.execute(
        "SELECT COUNT(*) FROM paragraph_evidence_map").fetchone()[0]
    assert total > 0, "run agents/agent_8_paragraph_evidence.py to populate it"
    # every evidence attachment cleared the threshold - none padded below it
    weak = conn.execute(
        "SELECT COUNT(*) FROM paragraph_evidence_map "
        "WHERE evidence_target_node_id IS NOT NULL AND evidence_score < ?",
        (EVIDENCE_THRESHOLD,)).fetchone()[0]
    assert weak == 0
    # only market claims carry a support status
    mislabeled = conn.execute(
        "SELECT COUNT(*) FROM paragraph_evidence_map "
        "WHERE classification != 'market_claim' "
        "AND support_status IS NOT NULL").fetchone()[0]
    assert mislabeled == 0
    # no evidence rows in structural sections
    structural = conn.execute(
        "SELECT COUNT(*) FROM paragraph_evidence_map "
        "WHERE section_purpose IN ('faq', 'author', 'cta', 'toc', "
        "'methodology', 'chapter_banner', 'navigation')").fetchone()[0]
    conn.close()
    assert structural == 0
