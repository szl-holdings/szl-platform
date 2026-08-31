"""Corpus integrity tests.

The corpus is the product's legal content: if it silently loses a control, a
readiness verdict silently changes. These tests pin the corpus's invariants so
any edit is a deliberate, review-visible act.
"""

from __future__ import annotations

from szl_iso42001.controls import (
    ANSWER_KINDS,
    BANDS,
    DISCLAIMER,
    Control,
    controls_by_domain,
    instruments,
    load_controls,
)
from szl_iso42001.score import ANSWER_POINTS

EXPECTED_ISO_COUNT = 34
EXPECTED_AIACT_COUNT = 10


def test_corpus_loads_with_expected_counts():
    controls = load_controls()
    assert len(controls) == EXPECTED_ISO_COUNT + EXPECTED_AIACT_COUNT
    by_instrument = instruments()
    assert len(by_instrument["ISO42001"]) == EXPECTED_ISO_COUNT
    assert len(by_instrument["AIACT-A50"]) == EXPECTED_AIACT_COUNT


def test_control_ids_are_unique():
    ids = [c.id for c in load_controls()]
    assert len(ids) == len(set(ids))


def test_all_weights_in_allowed_set():
    for c in load_controls():
        assert c.weight in (1, 2, 3), f"{c.id}: bad weight {c.weight}"


def test_every_field_is_non_empty():
    for c in load_controls():
        assert c.id.strip()
        assert c.title.strip()
        assert c.question.strip()
        assert c.evidence_hint.strip()
        assert c.domain.strip()


def test_id_prefixes_match_instrument():
    for c in load_controls():
        if c.instrument == "ISO42001":
            assert c.id.startswith("ISO42001-")
        else:
            assert c.id.startswith("AIACT-A50-")


def test_questions_are_questions():
    # Every control question must be answerable yes/partial/no/unknown; a
    # statement instead of a question is a corpus bug.
    for c in load_controls():
        assert c.question.rstrip().endswith("?"), f"{c.id}: question must end with '?'"


def test_iso_corpus_covers_clauses_4_through_10():
    domains = {c.domain for c in load_controls() if c.instrument == "ISO42001"}
    for clause in ("Clause 4", "Clause 5", "Clause 6", "Clause 7",
                   "Clause 8", "Clause 9", "Clause 10"):
        assert any(d.startswith(clause) for d in domains), f"missing {clause}"


def test_iso_corpus_covers_annex_a_themes():
    domains = {c.domain for c in load_controls() if c.instrument == "ISO42001"}
    for annex in ("A.2", "A.3", "A.4", "A.5", "A.6", "A.7", "A.8", "A.9", "A.10"):
        assert any(f"Annex {annex} " in d for d in domains), f"missing Annex {annex}"


def test_aiact_corpus_covers_article_50_topics():
    titles = " ".join(c.title.lower() for c in load_controls()
                      if c.instrument == "AIACT-A50")
    for topic in ("machine-readable", "chatbot", "deepfake",
                  "emotion-recognition", "biometric-categorization"):
        assert topic in titles, f"missing Article 50 topic: {topic}"


def test_all_four_answer_kinds_have_scoring_rules():
    # If a fifth answer kind ever appears in ANSWER_KINDS without a points
    # rule, scoring would KeyError at runtime. Pin the pairing.
    assert set(ANSWER_KINDS) == set(ANSWER_POINTS)
    assert set(ANSWER_KINDS) == {"yes", "partial", "no", "unknown"}


def test_bands_never_say_certified_or_compliant():
    # The core honesty rule, pinned as a test so a future edit can't weaken it.
    for band in BANDS:
        assert "CERTIF" not in band.upper()
        assert "COMPLI" not in band.upper()
    assert set(BANDS) == {"NOT_READY", "PARTIAL", "READY_FOR_STAGE1_AUDIT"}


def test_disclaimer_is_the_mandated_sentence():
    assert DISCLAIMER == (
        "Readiness self-assessment only. Not legal advice. Not certification. "
        "Only an accredited body certifies ISO/IEC 42001."
    )


def test_load_controls_is_deterministic():
    first = load_controls()
    second = load_controls()
    assert first == second


def test_controls_by_domain_preserves_corpus():
    grouped = controls_by_domain()
    flat = [c for controls in grouped.values() for c in controls]
    assert flat == load_controls()


def test_control_dataclass_is_immutable():
    control = load_controls()[0]
    assert isinstance(control, Control)
    try:
        control.weight = 99  # type: ignore[misc]
    except AttributeError:
        pass
    else:  # pragma: no cover - frozen dataclass must refuse
        raise AssertionError("Control must be immutable")
