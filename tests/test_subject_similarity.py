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
        "automotive coolant 3pl logistics market",
    ])
    v = weighted_vector(corpus, "automotive coolant 3pl logistics market")
    # specific subject noun keeps full relative weight; generic terms
    # (including "automotive" itself — an industry-umbrella word, not a
    # specific subject) shrink
    assert v["coolant"] > v["3pl"]
    assert v["coolant"] > v["logistics"]
    assert v["coolant"] > v["automotive"]


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


def test_shared_industry_umbrella_word_alone_does_not_drive_match():
    # Real live false positives Shrey caught: a shared broad industry/sector
    # word alone (not a specific subject) inflated similarity above
    # threshold. Different material/product/angle each time.
    cases = [
        ("UK Automotive Carbon Fiber Market", "Europe Automotive Exhaust Market"),
        ("Asia Pacific Injection Molding Plastic Market", "India Plastic Pipes Market"),
        ("Japan Food Antioxidants Market", "Asia Pacific Halal Food Beverages Market"),
        ("Bahrain Healthcare Analytics Market", "Philippines Healthcare Wearables Market"),
        ("Japan Security Paper Market", "Bahrain Embedded Security Market"),
        ("MEA Insulin Pumps Market", "Indonesia Breast Pumps Market"),
        ("Malaysia Retail Core Banking Solution Market", "Saudi Arabia Retail Banking Market"),
        ("Saudi Arabia Radiology Information Systems Market",
         "Saudi Arabia Hospital Information Systems Market"),
        ("India Luxury Fashion Market", "UAE Luxury Hospitality Market"),
        ("United Arab Emirates Acute Hospital Care Market",
         "Saudi Arabia Hospital Information Systems Market"),
        ("Global Electric Switch Market Strategy", "India Pump Market, Growth Opportunities"),
        ("Indonesia Coin Operated Commercial Laundry Market", "Bahrain Commercial Cleaning Products Market"),
        ("KSA Residential Market Shift: Supply, Prices", "UAE Furniture Market Growth: Residential Demand"),
        ("India Home Furniture Market Analysis", "Vietnam Home Water Filtration Unit Market"),
        ("Vietnam Car Rental Market", "Saudi BFSI Car Loan Market Forecast"),
        ("India Off-Road Vehicle Market", "Kuwait Vehicle Leasing Market Growth"),
        ("Indonesia Skilled Nursing Facility Rehabilitation Market",
         "Thailand Facility Management in Hospitals Market"),
        ("KSA Automotive Market: OEM Shifts", "UAE Lubricants Market: OEM Access"),
        ("How a B2B Packaging Marketplace Boosted Revenue by 25%",
         "How Ken Research Boosted IPO Readiness for an Asian Manufacturing Firm"),
        ("Global Blood Screening Market", "Saudi Arabia Blood IV Warmers Market"),
        ("Kuwait Military Radar Market",
         "Oman Military Simulation And Virtual Training Market"),
    ]
    docs = [x for pair in cases for x in pair] + ["filler market report"]
    corpus = build_corpus(docs)
    for a, b in cases:
        assert subject_similarity(corpus, a, b) < 0.25, (a, b)


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
    # A bare tech-qualifier mention counts as compound — Ken's real titles
    # use "[Domain] [Tech] Market" with no linking word ("Cold Storage
    # Automation & Robotics Market"), not just "[Tech] in [Domain]".
    assert has_compound_structure("AI in Medicine Market")
    assert has_compound_structure("Blockchain-based Supply Chain Market")
    assert has_compound_structure("AI Market")
    assert has_compound_structure("Cold Storage Automation & Robotics Market")
    assert not has_compound_structure("Herbal Medicine Market")
    assert not has_compound_structure("Cold Storage Market")


def test_tech_intersection_requires_symmetry_not_exact_qualifier():
    # Both compound -> gate passes regardless of which qualifier each uses;
    # domain-word overlap (Layer 2) decides the actual score, not this gate.
    assert tech_intersection_ok("AI in Medicine Market", "AI in Healthcare Market")
    assert tech_intersection_ok("AI in Robotics Market", "Blockchain in Medicine Market")
    # Real regression: exact-qualifier-match used to wrongly reject this —
    # "smart" and "robotics" are just different words for the same
    # automation-adjacent layer on an identical subject (agri drones), not
    # competing technologies.
    assert tech_intersection_ok(
        "Brazil Smart Agriculture and Agri Drones Market",
        "Germany Agri Drones Robotics Market",
    )
    # Asymmetric (one compound, one not) -> reject. This is the real Cold
    # Storage bug: "Cold Storage Market" (broad, no tech qualifier) is a
    # DIFFERENT market than "Cold Storage Automation & Robotics Market"
    # (the narrower automation/robotics tech layer within it).
    assert not tech_intersection_ok("AI in Medicine Market", "Herbal Medicine Market")
    assert not tech_intersection_ok(
        "Saudi Arabia Cold Storage Market Insights and Investment Opportunities",
        "Oman Cold Storage Automation & Robotics Market Share, Companies & Trends "
        "Report 2025-2030",
    )


def test_tech_intersection_noop_when_neither_compound():
    assert tech_intersection_ok("India Electric Bus Market", "Vietnam Electric Bus Market")


def test_subject_similarity_zero_when_gate_fails():
    corpus = build_corpus(["ai in medicine market", "herbal medicine market"])
    assert subject_similarity(corpus, "ai in medicine market", "herbal medicine market") == 0.0


def test_real_regression_cold_storage_vs_cold_storage_automation_robotics():
    # Shrey flagged this live: these are different markets (one broad, one
    # the automation/robotics tech segment within it) despite sharing
    # "cold storage" — the asymmetric compound structure must gate it out.
    a = "Saudi Arabia Cold Storage Market Insights and Investment Opportunities"
    b = ("Oman Cold Storage Automation & Robotics Market Share, Companies & "
         "Trends Report 2025-2030")
    corpus = build_corpus([a, b, "filler market report"])
    assert subject_similarity(corpus, a, b) == 0.0


# ── Known-good pairs must survive the new weighting ───────────────────────


def test_known_good_pairs_stay_meaningfully_similar():
    pairs = [
        ("South Africa E-Learning and Skills Platforms Market",
         "Russia E-Learning Skills Platforms Market"),
        ("Brazil Smart Agriculture and Agri Drones Market",
         "Germany Agri Drones Robotics Market"),
    ]
    # NOTE: "Saudi Arabia Radiology Information Systems Market" vs "Saudi
    # Arabia Hospital Information Systems Market" was originally in this
    # list as a "known good" pair — wrong. It only ever shared "information"
    # + "systems" (both generic/boilerplate), never a real subject word
    # (radiology vs hospital are different specific IT products). Moved to
    # test_shared_industry_umbrella_word_alone_does_not_drive_match, where
    # it belongs: caught by the same audit that found the pumps/banking/
    # luxury/hospital false positives.
    docs = [x for pair in pairs for x in pair] + ["filler market report"]
    corpus = build_corpus(docs)
    for a, b in pairs:
        assert subject_similarity(corpus, a, b) > 0.3
