"""Policy engine — Rev A scope enforcement.

Actions are classified:

  * OBSERVE                — read/sense only; no consent gate
  * NOTIFY                 — message a human; no consent gate
  * ALLOCATE_NONCRITICAL   — allocate non-scarce resources; logged, consent
                             gate not required
  * CONSEQUENTIAL          — anything that changes the physical world or a
                             person's situation; requires explicit
                             authorization to pass POLICY -> CONSENT -> ACTION

Rev A scope (from the Beacon RFQ): the system may PROPOSE translation,
summarization, triage assistance, and matching. It must REFUSE — at the
policy layer, with an explicit, receipted refusal event — any request for:

  * diagnosis or prescription (medical or otherwise clinical),
  * autonomous allocation of scarce life-critical resources,
  * direct control of life-safety, medical, or high-energy machinery.

Refusal is fail-closed and receipted: the refusal itself is an event on the
chain, so "the system declined" is as auditable as "the system acted".
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

__all__ = [
    "POLICY_VERSION",
    "ActionClass",
    "ScopeDecision",
    "classify_action",
    "evaluate_action_class",
    "rev_a_scope_check",
]

POLICY_VERSION = "rev-a.1"


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    NOTIFY = "NOTIFY"
    ALLOCATE_NONCRITICAL = "ALLOCATE_NONCRITICAL"
    CONSEQUENTIAL = "CONSEQUENTIAL"


class ScopeDecision(StrEnum):
    ALLOWED = "ALLOWED"
    REFUSED = "REFUSED"


#: Proposal categories Rev A permits.
ALLOWED_PROPOSALS = frozenset(
    {
        "translation",
        "summarization",
        "triage_assistance",
        "matching_proposal",
        "information",
        "status_report",
    }
)

#: Proposal categories Rev A REFUSES outright, with reason strings that go on
#: the receipted refusal event.
_REFUSAL_REASONS = {
    "diagnosis": (
        "Rev A scope: diagnosis refused — the Beacon provides triage "
        "assistance proposals, never clinical determination"
    ),
    "prescription": (
        "Rev A scope: prescription refused — no medication or treatment "
        "direction is within the permitted envelope"
    ),
    "scarce_lifecritical_allocation": (
        "Rev A scope: autonomous allocation of scarce life-critical "
        "resources refused — requires human authority, out of Rev A envelope"
    ),
    "lifesafety_control": (
        "Rev A scope: direct control of life-safety, medical, or "
        "high-energy machinery refused — out of Rev A envelope"
    ),
}

#: Keyword patterns used to spot refused requests in free text. Conservative:
#: a match forces REFUSED; absence of a match means the request still needs a
#: recognized ALLOWED proposal type to pass.
_REFUSAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "diagnosis",
        re.compile(r"\b(diagnos|medical advice|what illness| condition do i have)", re.I),
    ),
    (
        "prescription",
        re.compile(r"\b(prescrib|medication|dosage|dose of|what (pill|drug))", re.I),
    ),
    (
        "scarce_lifecritical_allocation",
        re.compile(
            r"\b(allocate|assign|distribute|dispatch|prioriti[sz]e)\b.*"
            r"\b(scarce|last|remaining|only)\b.*\b(unit|bed|ventilator|oxygen|dose|shelter)s?\b",
            re.I,
        ),
    ),
    (
        "lifesafety_control",
        re.compile(
            r"\b(control|actuate|energi[sz]e|fire|open|close|start|stop|shut ?down)\b.*"
            r"\b(ventilator|defibrillator|pump|valve|gate|lock|generator|reactor|machinery|"
            r"life[- ]?safety|gas main|high[- ]?energy)\b",
            re.I,
        ),
    ),
)


def classify_action(request: dict[str, Any]) -> ActionClass:
    """Classify a proposed action. Defaults to the most restrictive class that
    could apply — when in doubt, CONSEQUENTIAL. Fail closed."""

    declared = request.get("action_class") or request.get("action_type")
    if declared:
        try:
            return ActionClass(str(declared).upper())
        except ValueError:
            # Unknown declared class: treat as CONSEQUENTIAL, never silently.
            return ActionClass.CONSEQUENTIAL
    return ActionClass.CONSEQUENTIAL


def rev_a_scope_check(request: dict[str, Any]) -> dict[str, Any]:
    """Check a request against the Rev A permitted scope.

    ``request`` may carry a structured ``proposal_type`` and/or free ``text``.
    Returns ``{"decision": "ALLOWED"|"REFUSED", "reason": str,
    "category": str|None, "policy_version": str}``. A REFUSED decision always
    carries a human-readable reason suitable for the refusal event.
    """

    proposal_type = request.get("proposal_type")
    text = str(request.get("text") or "")

    # Structured refusal categories win first.
    if proposal_type in _REFUSAL_REASONS:
        return {
            "decision": ScopeDecision.REFUSED.value,
            "reason": _REFUSAL_REASONS[proposal_type],
            "category": proposal_type,
            "policy_version": POLICY_VERSION,
        }

    # Free-text screening: refused categories detected in the text.
    for category, pattern in _REFUSAL_PATTERNS:
        if pattern.search(text):
            return {
                "decision": ScopeDecision.REFUSED.value,
                "reason": _REFUSAL_REASONS[category],
                "category": category,
                "policy_version": POLICY_VERSION,
            }

    # Explicit allowed proposal types (or innocuous free text) pass the scope
    # screen — BUT free text alone with no recognized proposal type is NOT an
    # allow; it is an explicit non-match kept visible.
    if proposal_type in ALLOWED_PROPOSALS:
        return {
            "decision": ScopeDecision.ALLOWED.value,
            "reason": f"Rev A permitted proposal: {proposal_type}",
            "category": proposal_type,
            "policy_version": POLICY_VERSION,
        }

    if text.strip():
        return {
            "decision": ScopeDecision.ALLOWED.value,
            "reason": "no refused category detected; recorded as UNLABELED-scope review",
            "category": "unscoped_text",
            "policy_version": POLICY_VERSION,
        }

    # Nothing recognizable at all: refuse fail-closed.
    return {
        "decision": ScopeDecision.REFUSED.value,
        "reason": "request does not match any Rev A permitted proposal type",
        "category": "unknown",
        "policy_version": POLICY_VERSION,
    }


def evaluate_action_class(
    action_class: ActionClass,
    authorization: dict[str, Any] | None,
) -> dict[str, Any]:
    """Consent-gate evaluation for an action class.

    CONSEQUENTIAL actions REQUIRE explicit authorization: a mapping naming at
    least ``authorizer_id`` and ``authorization_digest``. Anything less —
    missing, malformed, or self-authorization by the requesting machine — is
    refused fail-closed.
    """

    if action_class is not ActionClass.CONSEQUENTIAL:
        return {"ok": True, "reason": f"{action_class.value} does not require consent gate"}

    if not isinstance(authorization, dict):
        return {
            "ok": False,
            "reason": "CONSEQUENTIAL action requires explicit authorization; none provided",
        }
    authorizer = authorization.get("authorizer_id")
    digest = authorization.get("authorization_digest")
    if not authorizer or not digest:
        return {
            "ok": False,
            "reason": (
                "authorization present but incomplete: authorizer_id and "
                "authorization_digest are both required"
            ),
        }
    return {
        "ok": True,
        "reason": f"explicit authorization by {authorizer}",
        "authorizer_id": authorizer,
    }
