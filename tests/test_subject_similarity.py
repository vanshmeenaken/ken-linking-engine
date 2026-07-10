"""Tests for the subject-aware similarity engine (Shrey's 4-layer method,
Layers 2+3). Phase 2 — relationship-mapping precision fix."""

from analysis.tfidf_similarity import build_corpus
from analysis.subject_similarity import (
    detect_tech_qualifier,
    has_compound_structure,
    subject_similarity,
    tech_intersection_ok,
    weighted_vector,
)

# ── Layer 2: generic-term downweighting ───────────────────────────────────


def test_generic_terms_downweighted_relative_to_subject_words():
    corpus = build_corpus([
        "automotive coolant market",
        "pharma 3pl logistics market",
        "automotive 3pl logistics market",
    ])
    v = weighted_vector(corpus, "automotive 3pl logistics market")
    # subject noun keeps full relative weight; generic terms shrink
    assert v["automotive"] > v["3pl"]
    assert v["automotive"] > v["logistics"]


def test_shared_generic_word_alone_does_not_drive_match():
    # Real drift the user reported: "automotive 3PL" vs "pharma 3PL" share
    # only the generic function word "3pl" — subjects are unrelated.
    corpus = build_corpus([
        "automotive 3pl logistics market",
        "pharma 3pl logistics market",
        "filler unrelated market report",
    ])
    score = subject_similarity(
        corpus, "automotive 3pl logistics market", "pharma 3pl logistics market",
    )
    assert score < 0.3


def test_year_tokens_excluded_entirely():
    corpus = build_corpus([
        "north america bone growth stimulator market outlook to 2030",
        "usa microscope market share major players outlook to 2030",
    ])
    v = weighted_vector(corpus, "north america bone growth stimulator market outlook to 2030")
    assert "2030" not in v


def test_real_regression_bone_growth_stimulator_vs_microscope():
    # The exact bad country_region edge Shrey flagged live: both titles
    # share "2030"/"market"/"outlook" only — zero real subject overlap.
    a = "North America Bone Growth Stimulator Market, Industry Analysis and Future Forecast to 2030"
    b = "USA Microscope Market, Share, Major Players and Outlook to 2030"
    corpus = build_corpus([a, b, "filler market report one", "filler market report two"])
    score = subject_similarity(corpus, a, b)
    assert score < 0.05


# ── Layer 3: tech-intersection gate ───────────────────────────────────────


def test_detect_tech_qualifier():
    assert detect_tech_qualifier("AI in Medicine Market") == "ai"
    assert detect_tech_qualifier("Herbal Medicine Market") == ""


def test_compound_structure_detection():
    assert has_compound_structure("AI in Medicine Market")
    assert has_compound_structure("Blockchain-based Supply Chain Market")
    assert not has_compound_structure("Herbal Medicine Market")
    assert not has_compound_structure("AI Market")  # bare tech word, no domain link


def test_tech_intersection_requires_both_halves():
    # "AI in Medicine" vs "AI in Healthcare" -> same qualifier, both compound -> ok
    assert tech_intersection_ok("AI in Medicine Market", "AI in Healthcare Market")
    # "AI in Medicine" vs "Herbal Medicine" -> only one side compound -> reject
    assert not tech_intersection_ok("AI in Medicine Market", "Herbal Medicine Market")
    # "AI in Medicine" vs "AI in Robotics" -> both compound, different domain qualifier match but different domain word entirely differs -> qualifier same (ai) so gate passes structurally; domain difference is handled by subject weighting, not this gate
    # "AI in Robotics" vs "Blockchain in Medicine" -> both compound, different qualifiers -> reject
    assert not tech_intersection_ok("AI in Robotics Market", "Blockchain in Medicine Market")


def test_tech_intersection_noop_when_neither_compound():
    assert tech_intersection_ok("India Electric Bus Market", "Vietnam Electric Bus Market")


def test_subject_similarity_zero_when_gate_fails():
    corpus = build_corpus(["ai in medicine market", "herbal medicine market"])
    assert subject_similarity(corpus, "ai in medicine market", "herbal medicine market") == 0.0


# ── Known-good pairs must survive the new weighting ───────────────────────


def test_known_good_pairs_stay_meaningfully_similar():
    pairs = [
        ("South Africa E-Learning and Skills Platforms Market",
         "Russia E-Learning Skills Platforms Market"),
        ("Brazil Smart Agriculture and Agri Drones Market",
         "Germany Agri Drones Robotics Market"),
        ("Saudi Arabia Radiology Information Systems Market",
         "Saudi Arabia Hospital Information Systems Market"),
    ]
    docs = [x for pair in pairs for x in pair] + ["filler market report"]
    corpus = build_corpus(docs)
    for a, b in pairs:
        assert subject_similarity(corpus, a, b) > 0.3
