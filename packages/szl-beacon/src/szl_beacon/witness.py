"""Witness Diversity — Proof of Outcome.

A physical outcome is not verified because the actor says it happened. It is
verified when at least TWO DISTINCT witness classes corroborate it:

  * INDEPENDENT_SENSOR      — a sensor not controlled by the actor
  * SECOND_NODE             — another Beacon node observing the same event
  * RECIPIENT_CONFIRMATION  — the human/system recipient confirms receipt
  * AUTHENTICATED_WITNESS   — an authenticated human/institutional witness

Rules:
  * >= 2 DISTINCT classes are required before OUTCOME VERIFIED.
  * Same-class duplicates do NOT count toward the threshold (two sensors of
    the same class are one class of evidence, not two).
  * Every witness event carries its OWN evidence ref — a witness without an
    evidence ref is not a witness, it is a claim.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .debt import DebtKind, DebtRegister

__all__ = [
    "MIN_DISTINCT_CLASSES",
    "WitnessClass",
    "WitnessError",
    "witness_event_payload",
    "evaluate_witnesses",
    "check_outcome_gate",
]

MIN_DISTINCT_CLASSES = 2


class WitnessClass(StrEnum):
    INDEPENDENT_SENSOR = "INDEPENDENT_SENSOR"
    SECOND_NODE = "SECOND_NODE"
    RECIPIENT_CONFIRMATION = "RECIPIENT_CONFIRMATION"
    AUTHENTICATED_WITNESS = "AUTHENTICATED_WITNESS"


class WitnessError(ValueError):
    """Raised when a witness attestation is malformed or insufficient."""


def witness_event_payload(
    witness_class: WitnessClass | str,
    evidence_ref: str,
    *,
    observer_id: str,
    observation: str,
) -> dict[str, Any]:
    """Build the payload for a WITNESS-state event. Fail closed on bad input."""

    try:
        wclass = WitnessClass(witness_class)
    except ValueError:
        raise WitnessError(f"unknown witness class: {witness_class!r}") from None
    if not evidence_ref or not isinstance(evidence_ref, str):
        raise WitnessError("every witness event must carry its own evidence ref")
    if not observer_id:
        raise WitnessError("witness event must name its observer")
    return {
        "witness_class": wclass.value,
        "evidence_ref": evidence_ref,
        "observer_id": observer_id,
        "observation": observation,
    }


def evaluate_witnesses(witness_events: list[dict]) -> dict[str, Any]:
    """Evaluate a set of WITNESS events against the diversity policy.

    Returns a report::

        {"ok": bool, "distinct_classes": [...], "count": int,
         "duplicates_ignored": int, "rejections": [...]}

    A witness event is counted only if it names a known class and carries a
    non-empty ``evidence_ref`` either in the payload or top-level
    ``evidence_refs``. Same-class repeats are counted as duplicates and never
    raise the class count.
    """

    distinct: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    rejections: list[str] = []

    for event in witness_events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        raw_class = payload.get("witness_class")
        evidence_ref = payload.get("evidence_ref") or (
            event.get("evidence_refs") or [None]
        )[0]
        try:
            wclass = WitnessClass(raw_class)
        except ValueError:
            rejections.append(f"unknown witness class {raw_class!r}")
            continue
        if not evidence_ref:
            rejections.append(f"witness {wclass.value} has no evidence ref")
            continue
        if wclass.value in seen:
            duplicates += 1
            continue
        seen.add(wclass.value)
        distinct.append(wclass.value)

    ok = len(distinct) >= MIN_DISTINCT_CLASSES
    return {
        "ok": ok,
        "distinct_classes": distinct,
        "count": len(distinct),
        "required": MIN_DISTINCT_CLASSES,
        "duplicates_ignored": duplicates,
        "rejections": rejections,
    }


def check_outcome_gate(
    witness_events: list[dict],
    debt: DebtRegister,
) -> dict[str, Any]:
    """Gate for promoting OUTCOME to VERIFIED.

    Returns ``{"ok": bool, "reasons": [...], "witness_report": {...},
    "blocking_debt": [...]}``. Fail closed: ANY insufficiency — too few
    distinct witness classes, any OPEN blocking debt — means not ok, with the
    reasons enumerated. This function never opens or resolves debt itself;
    when diversity is insufficient it reports so the caller can open a
    MISSING_WITNESS debt item.
    """

    report = evaluate_witnesses(witness_events)
    reasons: list[str] = []

    if not report["ok"]:
        reasons.append(
            f"witness diversity insufficient: {report['count']} distinct class(es), "
            f"require >= {MIN_DISTINCT_CLASSES}"
        )
    for rejection in report["rejections"]:
        reasons.append(f"witness rejected: {rejection}")

    blocking = debt.blocking_items()
    if blocking:
        kinds = sorted({item["kind"] for item in blocking})
        reasons.append(f"OPEN Reality Debt blocks verification: {', '.join(kinds)}")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "witness_report": report,
        "blocking_debt": [item["id"] for item in blocking],
        "missing_witness_kind": (
            DebtKind.MISSING_WITNESS.value if not report["ok"] else None
        ),
    }
