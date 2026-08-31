"""Scoring, banding, and gap prioritization for szl-iso42001.

DESIGN DECISION: every function in this module is PURE — same answers in, same
verdict out, no clock, no filesystem, no network. Determinism is a hard
requirement because the receipt that accompanies a report hashes the report
bytes; if scoring were non-deterministic, receipts would be unverifiable.

CRITICAL HONESTY RULES encoded here:
  * `unknown` scores ZERO points, exactly like `no` — but it is tracked in a
    DISTINCT list (evidence gaps) because the remediation differs: a `no` means
    "go fix this", an `unknown` means "go find out". Conflating them would let
    ignorance masquerade as either compliance or non-compliance.
  * No answer is ever assumed. A control absent from the answers mapping is
    treated as `unknown` (an evidence gap), never as a pass.
  * The top band requires BOTH >= 85% weighted score AND zero `no` answers on
    weight-3 (audit-blocking) controls. A single un-fixed critical control caps
    the verdict at PARTIAL no matter how good the rest looks — that is how real
    Stage-1 audits behave.
"""

from __future__ import annotations

from dataclasses import dataclass

from .controls import ANSWER_KINDS, Control

# ---------------------------------------------------------------------------
# Scoring constants (module-level so tests can pin them at the boundaries).
# ---------------------------------------------------------------------------

# Points multiplier per answer kind. `unknown` and `no` both earn nothing;
# only `partial` earns half.
ANSWER_POINTS: dict[str, float] = {
    "yes": 1.0,
    "partial": 0.5,
    "no": 0.0,
    "unknown": 0.0,
}

# Weighted-score threshold for the top band. Boundary-tested at 84.9 vs 85.
READY_THRESHOLD: float = 85.0

# Weighted-score threshold for the middle band.
PARTIAL_THRESHOLD: float = 50.0

# The three outcome bands, re-exported here for convenience.
BAND_NOT_READY = "NOT_READY"
BAND_PARTIAL = "PARTIAL"
BAND_READY = "READY_FOR_STAGE1_AUDIT"


@dataclass(frozen=True, slots=True)
class Gap:
    """A single open item the assessor must act on.

    kind is either "NO_FIX" (answered `no` — the control is absent/broken; go
    fix it) or "EVIDENCE_GAP" (answered `unknown` or not answered at all — go
    find out). The two kinds are never merged, by design.
    """

    control_id: str
    title: str
    domain: str
    weight: int
    kind: str  # "NO_FIX" | "EVIDENCE_GAP"
    evidence_hint: str


@dataclass(frozen=True, slots=True)
class DomainScore:
    """Weighted score for one domain (e.g. one ISO clause or Annex-A theme)."""

    domain: str
    instrument: str
    earned: float  # sum of weight * answer_points over the domain's controls
    possible: float  # sum of weights over the domain's controls
    percentage: float  # earned / possible * 100 (0.0 when the domain is empty)
    control_count: int


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """The complete, self-contained result of scoring one assessment.

    Everything report.py and receipt.py need hangs off this object — they add
    no scoring logic of their own (single source of truth).
    """

    band: str  # NOT_READY | PARTIAL | READY_FOR_STAGE1_AUDIT
    percentage: float  # overall weighted percentage, 0-100
    earned: float
    possible: float
    domain_scores: tuple[DomainScore, ...]  # corpus first-appearance order
    gaps: tuple[Gap, ...]  # prioritized: weight-3 NO_FIX first, then EVIDENCE_GAPs
    no_fix_gaps: tuple[Gap, ...]  # answered `no` — subset of gaps
    evidence_gaps: tuple[Gap, ...]  # unanswered/`unknown` — subset of gaps
    counts: dict[str, int]  # answer-kind -> how many controls got that answer
    control_count: int  # total controls in the corpus that was scored


def normalize_answer(value: object) -> str:
    """Coerce a raw answer value (e.g. from a YAML file) into a canonical kind.

    Accepts the four kinds case-insensitively; anything else raises ValueError.
    YAML is tricky here: `yes`/`no` parse as booleans, so True/False are mapped
    to 'yes'/'no' — the answers template writes the words quoted to avoid this,
    but we handle the booleans anyway because hand-edited files will hit it.
    """
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ANSWER_KINDS:
            return lowered
    raise ValueError(
        f"invalid answer {value!r}: expected one of {', '.join(ANSWER_KINDS)}"
    )


def score_control(control: Control, answer: str) -> float:
    """Weighted points for one answered control: weight * answer multiplier."""
    return control.weight * ANSWER_POINTS[answer]


def _percentage(earned: float, possible: float) -> float:
    """Guarded percentage — an empty selection scores 0%, never NaN."""
    if possible <= 0:
        return 0.0
    return earned / possible * 100.0


def determine_band(
    percentage: float, answers: dict[str, str], controls: list[Control]
) -> str:
    """Map an overall percentage + answers onto a readiness band.

    The weight-3 override lives here and nowhere else: any `no` on a weight-3
    control caps the band at PARTIAL, even at 100% overall. This mirrors how a
    Stage-1 audit works — a major nonconformity blocks recommendation
    regardless of how many minor controls pass.
    """
    has_blocking_no = any(
        answers.get(c.id, "unknown") == "no" and c.weight == 3 for c in controls
    )
    if percentage >= READY_THRESHOLD and not has_blocking_no:
        return BAND_READY
    if percentage >= PARTIAL_THRESHOLD:
        return BAND_PARTIAL
    return BAND_NOT_READY


def prioritize_gaps(gaps: list[Gap]) -> list[Gap]:
    """Order gaps for the report: most audit-relevant first.

    Sort key: (1) NO_FIX before EVIDENCE_GAP — a known-broken control outranks
    an unexplored one; (2) within a kind, higher weight first, so weight-3
    'no' answers lead the list exactly as the brief requires; (3) control id as
    a stable tie-break so output is deterministic.
    """
    kind_rank = {"NO_FIX": 0, "EVIDENCE_GAP": 1}
    return sorted(
        gaps, key=lambda g: (kind_rank[g.kind], -g.weight, g.control_id)
    )


def score_answers(
    answers: dict[str, object], controls: list[Control]
) -> ScoreResult:
    """Score a full assessment against the given corpus.

    Args:
        answers: mapping of control id -> raw answer. Missing ids and the
            literal 'unknown' are equivalent: both become EVIDENCE_GAPs.
            Extra ids not present in the corpus raise ValueError — a typo'd id
            must never silently vanish from an assessment.
        controls: the corpus to score against (pass controls.load_controls()).

    Returns:
        A fully-populated ScoreResult. Pure function: no I/O, no clock.
    """
    # Reject unknown control ids up front — otherwise a typo in answers.yaml
    # would silently score the real control as `unknown` and hide the mistake.
    corpus_ids = {c.id for c in controls}
    extras = sorted(set(answers) - corpus_ids)
    if extras:
        raise ValueError(f"answers reference unknown control ids: {extras}")

    # Canonicalize every answer exactly once; missing => 'unknown'.
    canonical: dict[str, str] = {}
    counts: dict[str, int] = {kind: 0 for kind in ANSWER_KINDS}
    for control in controls:
        raw = answers.get(control.id, "unknown")
        answer = normalize_answer(raw)
        canonical[control.id] = answer
        counts[answer] += 1

    # Overall weighted score.
    earned = sum(score_control(c, canonical[c.id]) for c in controls)
    possible = float(sum(c.weight for c in controls))
    percentage = _percentage(earned, possible)

    # Per-domain scores, in corpus first-appearance order.
    domain_order: list[str] = []
    domain_earned: dict[str, float] = {}
    domain_possible: dict[str, float] = {}
    domain_count: dict[str, int] = {}
    domain_instrument: dict[str, str] = {}
    for control in controls:
        if control.domain not in domain_earned:
            domain_order.append(control.domain)
            domain_earned[control.domain] = 0.0
            domain_possible[control.domain] = 0.0
            domain_count[control.domain] = 0
            domain_instrument[control.domain] = control.instrument
        domain_earned[control.domain] += score_control(control, canonical[control.id])
        domain_possible[control.domain] += control.weight
        domain_count[control.domain] += 1

    domain_scores = tuple(
        DomainScore(
            domain=d,
            instrument=domain_instrument[d],
            earned=domain_earned[d],
            possible=domain_possible[d],
            percentage=_percentage(domain_earned[d], domain_possible[d]),
            control_count=domain_count[d],
        )
        for d in domain_order
    )

    # Gaps: 'no' -> NO_FIX; 'unknown' (explicit or absent) -> EVIDENCE_GAP.
    no_fix_gaps: list[Gap] = []
    evidence_gaps: list[Gap] = []
    for control in controls:
        answer = canonical[control.id]
        if answer == "no":
            no_fix_gaps.append(
                Gap(control.id, control.title, control.domain, control.weight,
                    "NO_FIX", control.evidence_hint)
            )
        elif answer == "unknown":
            evidence_gaps.append(
                Gap(control.id, control.title, control.domain, control.weight,
                    "EVIDENCE_GAP", control.evidence_hint)
            )

    gaps = prioritize_gaps(no_fix_gaps + evidence_gaps)
    band = determine_band(percentage, canonical, controls)

    return ScoreResult(
        band=band,
        percentage=percentage,
        earned=earned,
        possible=possible,
        domain_scores=domain_scores,
        gaps=tuple(gaps),
        no_fix_gaps=tuple(no_fix_gaps),
        evidence_gaps=tuple(evidence_gaps),
        counts=counts,
        control_count=len(controls),
    )
