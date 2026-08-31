"""Scoring, banding, and gap-prioritization tests.

Every math fixture below is hand-computed in the test comments — if the code
and the comment ever disagree, the code is wrong by construction. Band
boundaries are pinned at the exact thresholds (84.9 vs 85) and the weight-3
override is proven to fire at 90%+.
"""

from __future__ import annotations

import pytest
from szl_iso42001.controls import Control, load_controls
from szl_iso42001.score import (
    BAND_NOT_READY,
    BAND_PARTIAL,
    BAND_READY,
    PARTIAL_THRESHOLD,
    READY_THRESHOLD,
    Gap,
    determine_band,
    normalize_answer,
    prioritize_gaps,
    score_answers,
    score_control,
)


def make_control(cid: str, weight: int, domain: str = "Test Domain") -> Control:
    """Minimal valid control fixture builder."""
    return Control(
        id=cid,
        title=f"Title for {cid}",
        question=f"Is {cid} handled?",
        evidence_hint=f"Evidence for {cid}.",
        domain=domain,
        weight=weight,
    )


# ---------------------------------------------------------------------------
# score_control / normalize_answer math
# ---------------------------------------------------------------------------

def test_answer_points_math():
    c = make_control("ISO42001-X-01", weight=2)
    assert score_control(c, "yes") == 2.0
    assert score_control(c, "partial") == 1.0
    assert score_control(c, "no") == 0.0
    assert score_control(c, "unknown") == 0.0


def test_weight_three_math():
    c = make_control("ISO42001-X-02", weight=3)
    assert score_control(c, "yes") == 3.0
    assert score_control(c, "partial") == 1.5


def test_normalize_answer_accepts_case_and_yaml_booleans():
    assert normalize_answer("YES") == "yes"
    assert normalize_answer(" Partial ") == "partial"
    assert normalize_answer(True) == "yes"
    assert normalize_answer(False) == "no"


def test_normalize_answer_rejects_garbage():
    for bad in ("maybe", "", 1, None, ["yes"]):
        with pytest.raises(ValueError, match="invalid answer"):
            normalize_answer(bad)


# ---------------------------------------------------------------------------
# score_answers on a hand-built mini-corpus
# ---------------------------------------------------------------------------

def mini_corpus() -> list[Control]:
    # Two domains so per-domain scoring is exercised.
    return [
        make_control("ISO42001-A-01", 3, "Domain One"),
        make_control("ISO42001-A-02", 2, "Domain One"),
        make_control("AIACT-A50-01", 1, "Domain Two"),
    ]


def test_hand_computed_overall_and_domains():
    # possible = 3 + 2 + 1 = 6
    # answers: A-01=yes (3), A-02=partial (1.0), 50-01=no (0) -> earned 4.0
    result = score_answers(
        {"ISO42001-A-01": "yes", "ISO42001-A-02": "partial", "AIACT-A50-01": "no"},
        mini_corpus(),
    )
    assert result.possible == 6.0
    assert result.earned == 4.0
    assert result.percentage == pytest.approx(4.0 / 6.0 * 100.0)
    by_domain = {d.domain: d for d in result.domain_scores}
    assert by_domain["Domain One"].percentage == pytest.approx(4.0 / 5.0 * 100.0)
    assert by_domain["Domain Two"].percentage == 0.0
    assert result.counts == {"yes": 1, "partial": 1, "no": 1, "unknown": 0}


def test_missing_answer_is_unknown_not_pass():
    # A-02 absent from the mapping -> treated as unknown -> EVIDENCE_GAP.
    # 50-01 answered 'no' so it lands in the OTHER list (no_fix), proving a
    # missing answer is not silently lumped in with real failures.
    result = score_answers(
        {"ISO42001-A-01": "yes", "AIACT-A50-01": "no"}, mini_corpus()
    )
    assert result.counts == {"yes": 1, "partial": 0, "no": 1, "unknown": 1}
    gap_ids = {g.control_id for g in result.evidence_gaps}
    assert gap_ids == {"ISO42001-A-02"}
    assert [g.control_id for g in result.no_fix_gaps] == ["AIACT-A50-01"]
    assert result.band == BAND_PARTIAL  # 3/6 = 50% exactly -> PARTIAL


def test_no_and_unknown_are_distinct_gap_lists():
    result = score_answers(
        {"ISO42001-A-01": "no", "ISO42001-A-02": "unknown", "AIACT-A50-01": "yes"},
        mini_corpus(),
    )
    assert [g.control_id for g in result.no_fix_gaps] == ["ISO42001-A-01"]
    assert [g.control_id for g in result.evidence_gaps] == ["ISO42001-A-02"]
    # The two lists never overlap and both feed the combined prioritized list.
    assert {g.control_id for g in result.gaps} == {
        "ISO42001-A-01", "ISO42001-A-02",
    }


def test_unknown_control_id_in_answers_raises():
    with pytest.raises(ValueError, match="unknown control ids"):
        score_answers({"ISO42001-TYPO-99": "yes"}, mini_corpus())


# ---------------------------------------------------------------------------
# Band boundaries — the exact thresholds, pinned
# ---------------------------------------------------------------------------

def test_band_boundary_just_below_ready():
    # 84.9% with no weight-3 'no' must NOT be READY.
    assert determine_band(84.9, {}, mini_corpus()) == BAND_PARTIAL
    assert determine_band(READY_THRESHOLD - 0.1, {}, mini_corpus()) == BAND_PARTIAL


def test_band_boundary_exactly_ready():
    assert determine_band(85.0, {}, mini_corpus()) == BAND_READY
    assert determine_band(READY_THRESHOLD, {}, mini_corpus()) == BAND_READY


def test_band_boundary_partial_edges():
    assert determine_band(PARTIAL_THRESHOLD - 0.1, {}, mini_corpus()) == BAND_NOT_READY
    assert determine_band(PARTIAL_THRESHOLD, {}, mini_corpus()) == BAND_PARTIAL


def test_weight3_no_forces_partial_even_at_90_percent():
    # 9.5 / 10.5 possible = ~90.5% — comfortably over the READY threshold —
    # but the weight-3 control is answered 'no', so the band caps at PARTIAL.
    corpus = [
        make_control("ISO42001-C-01", 3, "D"),  # no -> 0, blocking
        make_control("ISO42001-C-02", 2, "D"),  # yes -> 2
        make_control("ISO42001-C-03", 2, "D"),  # yes -> 2
        make_control("ISO42001-C-04", 2, "D"),  # yes -> 2
        make_control("ISO42001-C-05", 1, "D"),  # yes -> 1
        make_control("ISO42001-C-06", 1, "D"),  # yes -> 1
        make_control("ISO42001-C-07", 1, "D"),  # partial -> 0.5
    ]
    # possible = 3+2+2+2+1+1+1 = 12; earned = 0+2+2+2+1+1+0.5 = 8.5
    answers = {
        "ISO42001-C-01": "no",
        "ISO42001-C-02": "yes",
        "ISO42001-C-03": "yes",
        "ISO42001-C-04": "yes",
        "ISO42001-C-05": "yes",
        "ISO42001-C-06": "yes",
        "ISO42001-C-07": "partial",
    }
    result = score_answers(answers, corpus)
    assert result.percentage == pytest.approx(8.5 / 12.0 * 100.0)  # ~70.8
    assert result.band == BAND_PARTIAL
    # Direct determine_band check at 90% with a weight-3 no — the override
    # itself, independent of percentage:
    assert determine_band(
        90.0, {"ISO42001-C-01": "no"}, corpus
    ) == BAND_PARTIAL
    # ...and the same 90% with the weight-3 fixed flips to READY:
    assert determine_band(
        90.0, {"ISO42001-C-01": "yes"}, corpus
    ) == BAND_READY


def test_weight2_no_does_not_block_ready():
    # Only weight-3 controls trigger the override.
    corpus = [make_control("ISO42001-D-01", 2, "D")]
    assert determine_band(90.0, {"ISO42001-D-01": "no"}, corpus) == BAND_READY


def test_full_corpus_all_yes_is_ready():
    controls = load_controls()
    result = score_answers({c.id: "yes" for c in controls}, controls)
    assert result.percentage == 100.0
    assert result.band == BAND_READY
    assert result.gaps == ()


def test_full_corpus_all_unknown_is_not_ready_and_all_evidence_gaps():
    controls = load_controls()
    result = score_answers({}, controls)  # every control missing => unknown
    assert result.percentage == 0.0
    assert result.band == BAND_NOT_READY
    assert len(result.evidence_gaps) == len(controls)
    assert result.no_fix_gaps == ()


# ---------------------------------------------------------------------------
# Gap prioritization
# ---------------------------------------------------------------------------

def test_prioritized_gaps_weight3_no_first_then_evidence_gaps():
    def gap(cid, weight, kind):
        return Gap(cid, f"t-{cid}", "D", weight, kind, "hint")

    gaps = [
        gap("ISO42001-E-01", 1, "EVIDENCE_GAP"),
        gap("ISO42001-E-02", 2, "NO_FIX"),
        gap("ISO42001-E-03", 3, "EVIDENCE_GAP"),
        gap("ISO42001-E-04", 3, "NO_FIX"),
        gap("ISO42001-E-05", 1, "NO_FIX"),
    ]
    ordered = [g.control_id for g in prioritize_gaps(gaps)]
    # NO_FIX first (weight desc), then EVIDENCE_GAPs (weight desc).
    assert ordered == [
        "ISO42001-E-04",  # weight-3 no  -> first, per the brief
        "ISO42001-E-02",  # weight-2 no
        "ISO42001-E-05",  # weight-1 no
        "ISO42001-E-03",  # weight-3 evidence gap
        "ISO42001-E-01",  # weight-1 evidence gap
    ]


def test_score_result_is_pure_and_repeatable():
    answers = {"ISO42001-A-01": "yes"}
    first = score_answers(answers, mini_corpus())
    second = score_answers(answers, mini_corpus())
    assert first == second
