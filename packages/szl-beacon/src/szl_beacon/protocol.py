"""The Reality Transaction state machine.

States (in canonical order)::

    INTENT -> EVIDENCE -> PROPOSAL -> SIMULATION -> POLICY -> CONSENT
    -> ACTION -> WITNESS -> OUTCOME -> RECONCILIATION -> RECEIPT

Core rules — these are the protocol, not implementation details:

  1. Each transition is a SEPARATE signed-style event on the append-only
     hash-chained log. There is no silent multi-state hop.
  2. A REQUESTED action, an EXECUTED action, and a VERIFIED PHYSICAL OUTCOME
     are NEVER synonyms. Enforcement: OUTCOME cannot be entered from ACTION
     without at least one accepted WITNESS event; the machine refuses the
     ACTION -> OUTCOME hop otherwise.
  3. CONSEQUENTIAL actions cannot pass POLICY -> CONSENT -> ACTION without
     explicit authorization (see :mod:`szl_beacon.policy`).
  4. Reality Debt is never auto-resolved; OPEN blocking debt keeps an
     outcome from being promoted to VERIFIED (see :mod:`szl_beacon.debt`).
  5. The machine is FAIL-CLOSED: any schema/validation failure means the
     transition is refused, a failure event is appended to the log (the
     refusal is itself on the record), and the state is unchanged.

This is a REFERENCE IMPLEMENTATION. Zero physical units exist; the state
machine models the protocol so software and firmware teams can build against
it before hardware EVT.
"""

from __future__ import annotations

import itertools
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import events as ev
from . import log as eventlog
from .debt import DebtKind, DebtRegister
from .labels import Label
from .policy import ActionClass, evaluate_action_class
from .witness import check_outcome_gate, evaluate_witnesses

__all__ = [
    "PROTOCOL_VERSION",
    "OutcomeStatus",
    "RealityTransaction",
    "State",
    "TransitionRefused",
]

PROTOCOL_VERSION = "beacon-reality-protocol/0.1-reference"


class State(StrEnum):
    INTENT = "INTENT"
    EVIDENCE = "EVIDENCE"
    PROPOSAL = "PROPOSAL"
    SIMULATION = "SIMULATION"
    POLICY = "POLICY"
    CONSENT = "CONSENT"
    ACTION = "ACTION"
    WITNESS = "WITNESS"
    OUTCOME = "OUTCOME"
    RECONCILIATION = "RECONCILIATION"
    RECEIPT = "RECEIPT"


#: The single forward edge per state (a transaction is a spine; evidence and
#: witness states may be revisited only through this spine).
_FORWARD = {
    State.INTENT: State.EVIDENCE,
    State.EVIDENCE: State.PROPOSAL,
    State.PROPOSAL: State.SIMULATION,
    State.SIMULATION: State.POLICY,
    State.POLICY: State.CONSENT,
    State.CONSENT: State.ACTION,
    State.ACTION: State.WITNESS,
    State.WITNESS: State.OUTCOME,
    State.OUTCOME: State.RECONCILIATION,
    State.RECONCILIATION: State.RECEIPT,
}


class OutcomeStatus(StrEnum):
    """Outcome is never silently 'fine'. One of these, always explicit."""

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"


class TransitionRefused(RuntimeError):
    """Raised when a transition is refused. A failure event is on the log."""

    def __init__(self, reason: str, *, failure_event_id: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.failure_event_id = failure_event_id


class RealityTransaction:
    """One Reality Transaction against one event log.

    The transaction owns a DebtRegister; the log may be shared across
    transactions on the same node (seq allocation goes through the log head,
    so interleaved transactions still form one chain).
    """

    def __init__(
        self,
        logdir: Path | str,
        *,
        node_id: str,
        transaction_id: str | None = None,
        clock=time.gmtime,
    ) -> None:
        self.logdir = Path(logdir)
        self.node_id = node_id
        self.debt = DebtRegister()
        self._clock = clock
        self._state: State | None = None
        self._witness_events: list[dict] = []
        self._outcome_status = OutcomeStatus.PENDING
        self._action_class: ActionClass | None = None
        self._authorization: dict | None = None
        self._refusals: list[str] = []
        self._closed = False
        if transaction_id is None:
            transaction_id = "tx-" + ev.event_digest(
                {"node": node_id, "at": self._now(), "nonce": next(_NONCE)}
            )[:12]
        self.transaction_id = transaction_id

    # ------------------------------------------------------------------ util

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", self._clock())

    def _next_seq_prev(self) -> tuple[int, str | None]:
        head = eventlog.head(self.logdir)
        if head is None:
            return 0, ev.GENESIS_PREV
        return int(head["seq"]) + 1, str(head["event_id"])

    def _emit(
        self,
        state_to: State,
        *,
        actor: dict,
        payload: dict,
        label: Label,
        evidence_refs: list[str] | None = None,
        advance: bool = True,
    ) -> dict:
        seq, prev = self._next_seq_prev()
        event = ev.new_event(
            seq=seq,
            prev=prev,
            state_from=self._state.value if self._state else None,
            state_to=state_to.value,
            actor=actor,
            payload={"transaction_id": self.transaction_id, **payload},
            evidence_refs=evidence_refs,
            label=label,
            created_at=self._now(),
        )
        eventlog.append_event(self.logdir, event)
        if advance:
            self._state = state_to
        return event

    def _refuse(self, reason: str, *, label: Label = Label.UNVERIFIED) -> TransitionRefused:
        """Append a failure/refusal event and refuse. State is UNCHANGED."""

        event = self._emit(
            self._state or State.INTENT,
            actor={"kind": "node", "id": self.node_id},
            payload={
                "type": "TRANSITION_REFUSED",
                "reason": reason,
                "attempted_from": self._state.value if self._state else None,
            },
            label=label,
            advance=False,
        )
        self._refusals.append(event["event_id"])
        return TransitionRefused(reason, failure_event_id=event["event_id"])

    # ------------------------------------------------------------- interface

    @property
    def state(self) -> State | None:
        return self._state

    @property
    def outcome_status(self) -> OutcomeStatus:
        return self._outcome_status

    @property
    def refusals(self) -> list[str]:
        return list(self._refusals)

    def open_intent(
        self,
        *,
        actor: dict,
        summary: str,
        label: Label = Label.UNVERIFIED,
        request: dict | None = None,
        evidence_refs: list[str] | None = None,
    ) -> dict:
        """Genesis transition: enter INTENT (Proof of Intent)."""

        if self._state is not None:
            raise self._refuse("transaction already opened")
        return self._emit(
            State.INTENT,
            actor=actor,
            payload={"type": "INTENT", "summary": summary, "request": request or {}},
            label=label,
            evidence_refs=evidence_refs,
        )

    def advance(
        self,
        to_state: State | str,
        *,
        actor: dict,
        payload: dict | None = None,
        label: Label = Label.UNVERIFIED,
        evidence_refs: list[str] | None = None,
    ) -> dict:
        """Advance one transition along the spine. Fail closed on any rule."""

        to_state = State(to_state)
        payload = dict(payload or {})

        if self._closed:
            raise self._refuse("transaction is closed (RECEIPT issued)")
        if self._state is None:
            raise self._refuse("transaction not opened; call open_intent first")

        expected = _FORWARD.get(self._state)
        if to_state is not expected and to_state is not self._state:
            raise self._refuse(
                f"illegal transition {self._state.value} -> {to_state.value}; "
                f"expected {expected.value if expected else '(none)'}"
            )

        # Fail closed: any schema/label validation failure raised while
        # building the transition event becomes a receipted refusal with the
        # state unchanged, never a bare exception.
        try:
            return self._guarded_advance(
                to_state, actor=actor, payload=payload, label=label, evidence_refs=evidence_refs
            )
        except ValueError as exc:
            raise self._refuse(f"event validation failed: {exc}") from exc

    def _guarded_advance(
        self,
        to_state: State,
        *,
        actor: dict,
        payload: dict,
        label: Label,
        evidence_refs: list[str] | None,
    ) -> dict:
        if to_state is State.OUTCOME:
            return self._enter_outcome(actor=actor, payload=payload, evidence_refs=evidence_refs)
        if to_state is State.CONSENT:
            return self._enter_consent(actor=actor, payload=payload, label=label)
        if to_state is State.ACTION:
            return self._enter_action(actor=actor, payload=payload, label=label)
        if to_state is State.RECEIPT:
            return self._enter_receipt(actor=actor, payload=payload)

        if to_state is State.WITNESS:
            event = self._emit(
                to_state,
                actor=actor,
                payload=payload,
                label=label,
                evidence_refs=evidence_refs,
            )
            self._witness_events.append(event)
            return event
        # (generic transition)


        return self._emit(
            to_state, actor=actor, payload=payload, label=label, evidence_refs=evidence_refs
        )

    # (end advance)

    # ---------------------------------------------------- guarded transitions

    def _enter_consent(self, *, actor: dict, payload: dict, label: Label) -> dict:
        action_class = ActionClass(payload.get("action_class", ActionClass.OBSERVE.value))
        self._action_class = action_class
        gate = evaluate_action_class(action_class, payload.get("authorization"))
        if not gate["ok"]:
            raise self._refuse(
                f"consent gate refused {action_class.value}: {gate['reason']}",
                label=Label.UNVERIFIED,
            )
        self._authorization = payload.get("authorization")
        return self._emit(
            State.CONSENT,
            actor=actor,
            payload={"type": "CONSENT", "consent": gate},
            label=Label.AUTHORIZED_OPERATOR if action_class is ActionClass.CONSEQUENTIAL else label,
        )

    def _enter_action(self, *, actor: dict, payload: dict, label: Label) -> dict:
        if self._action_class is ActionClass.CONSEQUENTIAL and not self._authorization:
            raise self._refuse(
                "ACTION refused: CONSEQUENTIAL action has no authorization on record",
            )
        return self._emit(
            State.ACTION,
            actor=actor,
            payload={"type": "ACTION", "action": payload.get("action", payload)},
            label=label,
        )

    def _enter_outcome(
        self, *, actor: dict, payload: dict, evidence_refs: list[str] | None
    ) -> dict:
        """The never-synonyms rule, enforced.

        Reaching OUTCOME from WITNESS is not enough: the accumulated witness
        events must pass diversity and no OPEN blocking debt may exist.
        """

        gate = check_outcome_gate(self._witness_events, self.debt)
        if not gate["ok"]:
            if gate["witness_report"]["count"] < gate["witness_report"]["required"]:
                self.debt.open(
                    DebtKind.MISSING_WITNESS,
                    {
                        "have_classes": gate["witness_report"]["distinct_classes"],
                        "required": gate["witness_report"]["required"],
                    },
                    opened_by=actor.get("id", self.node_id),
                )
            self._outcome_status = OutcomeStatus.UNVERIFIED
            raise self._refuse(
                "OUTCOME promotion refused: " + "; ".join(gate["reasons"]),
                label=Label.UNVERIFIED,
            )

        self._outcome_status = OutcomeStatus.VERIFIED
        return self._emit(
            State.OUTCOME,
            actor=actor,
            payload={
                "type": "OUTCOME",
                "status": OutcomeStatus.VERIFIED.value,
                "witness_classes": gate["witness_report"]["distinct_classes"],
                **payload,
            },
            label=Label.OUTCOME_VERIFIED,
            evidence_refs=evidence_refs,
        )

    def reconcile(self, *, actor: dict, debt_id: str, resolution: str) -> dict:
        """Explicitly resolve a Reality Debt item. The ONLY way debt closes."""

        if self._state not in (State.OUTCOME, State.RECONCILIATION, State.WITNESS, State.ACTION):
            raise self._refuse("reconciliation only after ACTION")
        try:
            item = self.debt.resolve(debt_id, resolved_by="pending")
        except Exception as exc:
            raise self._refuse(f"reconciliation refused: {exc}") from exc

        # From OUTCOME the spine advances to RECONCILIATION; earlier in the
        # spine the reconciliation event is recorded WITHOUT moving the
        # state, so the transaction can still reach OUTCOME afterwards.
        advance = self._state is State.OUTCOME
        event = self._emit(
            State.RECONCILIATION,
            actor=actor,
            payload={
                "type": "RECONCILIATION",
                "debt_id": debt_id,
                "resolution": resolution,
            },
            label=Label.AUTHORIZED_OPERATOR,
            advance=advance,
        )
        item["resolved_by"] = event["event_id"]
        return event

    def _enter_receipt(self, *, actor: dict, payload: dict) -> dict:
        """Close the transaction with a receipt. Debt must be clean."""

        if self.debt.blocks_verification():
            self._outcome_status = OutcomeStatus.UNVERIFIED
            raise self._refuse(
                "RECEIPT refused: OPEN blocking Reality Debt remains; reconcile first"
            )
        receipt = self.build_receipt()
        event = self._emit(
            State.RECEIPT,
            actor=actor,
            payload={"type": "RECEIPT", "receipt": receipt, **payload},
            label=Label.OUTCOME_VERIFIED
            if self._outcome_status is OutcomeStatus.VERIFIED
            else Label.UNVERIFIED,
        )
        self._closed = True
        return event

    def build_receipt(self) -> dict[str, Any]:
        """The transaction receipt: an honest summary. No fake green."""

        return {
            "protocol": PROTOCOL_VERSION,
            "transaction_id": self.transaction_id,
            "node_id": self.node_id,
            "outcome_status": self._outcome_status.value,
            "witness_classes": evaluate_witnesses(self._witness_events)["distinct_classes"],
            "open_debt": [i["id"] for i in self.debt.open_items()],
            "refusals": list(self._refusals),
            "canonicalization": "json-sortkeys-nowhitespace (reference); RFC 8785 in production",
            "physical_units_fielded": 0,
        }


_NONCE = itertools.count()
