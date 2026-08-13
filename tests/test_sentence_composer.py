"""Tests for the composed insert-sentence machinery: when no existing
sentence fits an anchor, the system writes a claim-free sentence carrying
the anchor and tells the editor exactly where to insert it - with the
justification present on EVERY queue row, not just behind the Explain view."""

import re

from fastapi.testclient import TestClient

from agents.agent_11_editorial_review import build_review_note
from analysis.sentence_composer import _TEMPLATES, compose_link_sentence
from api.main import app

client = TestClient(app)


# ── the composed sentence itself ─────────────────────────────────────────────

def test_composed_sentence_carries_anchor_verbatim():
    s = compose_link_sentence("UAE Cold Storage Market", "same_market")
    assert "UAE Cold Storage Market" in s
    assert s.endswith(".")


def test_composed_sentences_are_claim_free():
    # PRD 12.3: never invent market numbers or facts. No template may contain
    # digits or claim-words that would assert something about the market.
    for rel in list(_TEMPLATES) + ["unknown_type"]:
        s = compose_link_sentence("India EV Market", rel)
        assert not re.search(r"\d", s), f"template for {rel} contains a number"
        for banned in ("growing at", "valued at", "worth", "cagr", "expected to reach"):
            assert banned not in s.lower(), f"template for {rel} makes a claim"


def test_templates_vary_by_relationship():
    same = compose_link_sentence("X Market", "same_market")
    adjacent = compose_link_sentence("X Market", "adjacent_market")
    case = compose_link_sentence("X Market", "case_study_support")
    assert len({same, adjacent, case}) == 3


# ── the review note explains the insert position ─────────────────────────────

def _rec(**overrides):
    base = {
        "recommendation_id": "r1", "relationship_type": "same_market",
        "anchor_text": "India Online Grocery Market",
        "placement_type": "best_available_paragraph",
        "placement_section": "Market Overview",
        "suggested_sentence": "Grocery demand keeps rising in urban India.",
        "proposed_sentence": compose_link_sentence(
            "India Online Grocery Market", "same_market"),
        "link_score": 70.0, "score_band": "secondary",
        "seo_score": 70.0, "business_score": 70.0,
        "risk_flag": "low", "risk_reason": None,
    }
    base.update(overrides)
    return base


def test_note_gives_insert_position_and_composed_sentence():
    note = build_review_note(_rec(), "Source", "Target")
    assert "insert this new sentence" in note.where.lower()
    assert "right after the existing line" in note.where.lower()
    assert "India Online Grocery Market" in note.where


def test_note_explains_composed_sentence_is_claim_free():
    note = build_review_note(_rec(), "Source", "Target")
    assert "no market claims" in note.placement_reason.lower()
    assert "closest topical home" in note.placement_reason.lower()


# ── every queue row carries its explanation ──────────────────────────────────

def test_review_queue_has_placement_reason_on_every_row():
    r = client.get("/api/recommendations/review-queue?limit=500")
    assert r.status_code == 200
    rows = r.json()["recommendations"]
    assert rows
    for row in rows:
        assert row.get("placement_reason"), (
            f"row {row['recommendation_id']} has no placement_reason")


def test_list_endpoint_has_placement_reason_on_every_row():
    r = client.get("/api/recommendations?limit=500")
    assert r.status_code == 200
    rows = r.json()["recommendations"]
    assert rows
    for row in rows:
        assert row.get("placement_reason")
        assert "proposed_sentence" in row


def test_list_endpoint_status_filter_does_not_500():
    # regression: joining content_nodes for target_title made "status"
    # ambiguous (both link_recommendations and content_nodes have it),
    # crashing every filtered call with sqlite3.OperationalError
    for status in ("pending", "approved", "rejected"):
        r = client.get(f"/api/recommendations?limit=50&status={status}")
        assert r.status_code == 200
        assert all(row["status"] == status if status != "pending" else True
                   for row in r.json()["recommendations"])
    r = client.get("/api/recommendations?limit=10&band=hold")
    assert r.status_code == 200
    r = client.get("/api/recommendations?limit=10&relationship_class=regional")
    assert r.status_code == 200


# ── weaving the anchor into an EXISTING sentence ─────────────────────────────

from analysis.sentence_composer import weave_anchor_into_sentence


def test_weave_preserves_original_sentence_byte_for_byte():
    original = "The market grew at a CAGR of 6.8% during the review period"
    woven = weave_anchor_into_sentence(
        original + ".", "India Cement Market", "same_market")
    assert woven.startswith(original)


def test_weave_carries_the_anchor_verbatim():
    woven = weave_anchor_into_sentence(
        "Demand keeps rising across urban delivery zones.",
        "India Online Grocery Market", "adjacent_market")
    assert "India Online Grocery Market" in woven


def test_weave_never_invents_a_number():
    original = "Demand keeps rising across urban delivery zones."
    for rel in list(_WEAVE_CLAUSES) + ["unknown_type"]:
        woven = weave_anchor_into_sentence(original, "X Market", rel)
        added = woven[len(original.rstrip(".")):]
        assert not any(c.isdigit() for c in added), f"{rel} clause has a digit"


def test_weave_handles_missing_terminal_punctuation():
    woven = weave_anchor_into_sentence(
        "Demand keeps rising across urban delivery zones", "X Market", "same_market")
    assert woven.endswith(".")


def test_weave_varies_by_relationship_type():
    original = "Demand keeps rising across urban delivery zones."
    a = weave_anchor_into_sentence(original, "X Market", "same_market")
    b = weave_anchor_into_sentence(original, "X Market", "case_study_support")
    assert a != b


def test_weave_empty_inputs_return_sentence_unchanged():
    assert weave_anchor_into_sentence("", "X Market", "same_market") == ""
    assert weave_anchor_into_sentence("A sentence.", "", "same_market") == "A sentence."


from analysis.sentence_composer import _WEAVE_CLAUSES  # noqa: E402  (used above)


# ── every queue row shows the woven, ready-to-use sentence ───────────────────

def test_review_queue_has_woven_sentence_for_contextual_placements():
    # note: woven_sentence may come from the LLM (scripts/36) or the
    # deterministic template fallback - an LLM rewrite is free to restructure
    # the sentence, so this only checks the anchor is present, never an
    # exact-prefix match (that would only hold for the template path)
    r = client.get("/api/recommendations/review-queue?limit=500")
    rows = r.json()["recommendations"]
    contextual = [row for row in rows
                 if row["placement_type"] == "contextual_body"
                 and row.get("suggested_sentence")]
    assert contextual
    for row in contextual:
        assert row.get("woven_sentence"), (
            f"no woven_sentence for {row['recommendation_id']}")
        assert row["anchor_text"] in row["woven_sentence"]
