"""State machine tests: happy path, never-synonyms, consent gate, fail-closed."""

from __future__ import annotations

import pytest
from conftest import (
    add_witness,
    human,
    machine,
    open_through_action,
    open_through_policy,
    run_happy_path,
)
from szl_beacon import log as eventlog
from szl_beacon.labels import Label
from szl_beacon.protocol import OutcomeStatus, RealityTransaction, State, TransitionRefused
from szl_beacon.witness import WitnessClass


class TestHappyPath:
    def test_full_transaction_11_transitions_chain_verifies(
        self, tx: RealityTransaction, logdir
    ) -> None:
        assert eventlog.head(logdir) is None  # empty before

        run_happy_path(tx)

        events = eventlog.read_events(logdir)
        # 12 events: the spine visits all 11 states, with WITNESS entered
        # twice (two distinct witness classes) => 12 events, 11 transitions
        # covering every protocol state exactly.
        assert len(events) == 12
        visited = [e["state_to"] for e in events]
        assert set(visited) == {s.value for s in State}
        spine = [s for s in visited if s != "WITNESS"] + []
        assert spine == [
            "INTENT",
            "EVIDENCE",
            "PROPOSAL",
            "SIMULATION",
            "POLICY",
            "CONSENT",
            "ACTION",
            "OUTCOME",
            "RECONCILIATION",
            "RECEIPT",
        ]
        # Hash chain intact: seq strictly increasing, prev links correct.
        for index, event in enumerate(events):
            assert event["seq"] == index
            if index == 0:
                assert event["prev"] is None
            else:
                assert event["prev"] == events[index - 1]["event_id"]

        report = eventlog.verify(logdir)
        assert report.ok, report.to_dict()

        # Final receipt is honest about the outcome.
        receipt = events[-1]["payload"]["receipt"]
        assert receipt["outcome_status"] == "VERIFIED"
        assert receipt["open_debt"] == []
        assert receipt["physical_units_fielded"] == 0

    def test_every_transition_is_a_separate_event(
        self, tx: RealityTransaction, logdir
    ) -> None:
        open_through_policy(tx)
        events = eventlog.read_events(logdir)
        # INTENT + 4 advances = 5 distinct events with unique digests.
        assert len(events) == 5
        digests = [e["event_id"] for e in events]
        assert len(set(digests)) == 5

    def test_transaction_id_threaded_through_all_events(
        self, tx: RealityTransaction, logdir
    ) -> None:
        run_happy_path(tx)
        for event in eventlog.read_events(logdir):
            assert event["payload"]["transaction_id"] == tx.transaction_id


class TestNeverSynonyms:
    """Requested action, executed action, verified outcome: three records."""

    def test_outcome_cannot_be_entered_from_action(
        self, tx: RealityTransaction
    ) -> None:
        open_through_action(tx)
        assert tx.state is State.ACTION
        with pytest.raises(TransitionRefused):
            tx.advance(State.OUTCOME, actor=human("operator-1"))
        # State unchanged after refusal.
        assert tx.state is State.ACTION

    def test_outcome_refused_without_any_witness(self, tx: RealityTransaction) -> None:
        # Even if the state somehow sat at WITNESS-not-yet-witnessed, the
        # diversity gate refuses: simulate by advancing ACTION -> WITNESS
        # with an invalid witness payload is not possible (payload enforced
        # at construction), so verify the gate itself: one witness short.
        open_through_action(tx)
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
        # Only ONE distinct class: gate requires >= 2.
        with pytest.raises(TransitionRefused) as excinfo:
            tx.advance(State.OUTCOME, actor=human("operator-1"))
        assert "witness diversity insufficient" in excinfo.value.reason
        assert tx.outcome_status is OutcomeStatus.UNVERIFIED
        assert tx.state is State.WITNESS  # unchanged

    def test_refusal_event_appended_on_denied_outcome(
        self, tx: RealityTransaction, logdir
    ) -> None:
        open_through_action(tx)
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
        before = len(eventlog.read_events(logdir))
        with pytest.raises(TransitionRefused):
            tx.advance(State.OUTCOME, actor=human("operator-1"))
        after = eventlog.read_events(logdir)
        assert len(after) == before + 1
        refusal = after[-1]
        assert refusal["payload"]["type"] == "TRANSITION_REFUSED"
        assert "OUTCOME" in refusal["payload"]["reason"]
        # Chain still verifies after the refusal event.
        assert eventlog.verify(logdir).ok


class TestConsentGate:
    def test_consequential_without_authorization_refused(
        self, tx: RealityTransaction, logdir
    ) -> None:
        open_through_policy(tx)
        with pytest.raises(TransitionRefused) as excinfo:
            tx.advance(
                State.CONSENT,
                actor=human("operator-1"),
                payload={"action_class": "CONSEQUENTIAL"},
            )
        assert "explicit authorization" in excinfo.value.reason
        events = eventlog.read_events(logdir)
        refusal = events[-1]
        assert refusal["payload"]["type"] == "TRANSITION_REFUSED"
        assert refusal["payload"]["attempted_from"] == "POLICY"

    def test_consequential_with_incomplete_authorization_refused(
        self, tx: RealityTransaction
    ) -> None:
        open_through_policy(tx)
        with pytest.raises(TransitionRefused):
            tx.advance(
                State.CONSENT,
                actor=human("operator-1"),
                payload={
                    "action_class": "CONSEQUENTIAL",
                    "authorization": {"authorizer_id": "op-9"},  # digest missing
                },
            )

    def test_consequential_with_authorization_passes(
        self, tx: RealityTransaction
    ) -> None:
        open_through_policy(tx)
        event = tx.advance(
            State.CONSENT,
            actor=human("operator-1"),
            payload={
                "action_class": "CONSEQUENTIAL",
                "authorization": {
                    "authorizer_id": "duty-officer-3",
                    "authorization_digest": "ab" * 32,
                },
            },
        )
        assert event["state_to"] == "CONSENT"
        assert tx.state is State.CONSENT


class TestFailClosed:
    def test_illegal_transition_refused_and_logged(
        self, tx: RealityTransaction, logdir
    ) -> None:
        tx.open_intent(actor=human("a"), summary="s", label=Label.COMMUNITY_REPORT)
        with pytest.raises(TransitionRefused):
            tx.advance(State.POLICY, actor=human("a"))  # skips EVIDENCE, PROPOSAL
        assert tx.state is State.INTENT
        events = eventlog.read_events(logdir)
        assert events[-1]["payload"]["type"] == "TRANSITION_REFUSED"

    def test_advance_before_open_refused(self, tx: RealityTransaction) -> None:
        with pytest.raises(TransitionRefused):
            tx.advance(State.EVIDENCE, actor=human("a"))

    def test_advance_after_receipt_refused(self, tx: RealityTransaction) -> None:
        run_happy_path(tx)
        with pytest.raises(TransitionRefused) as excinfo:
            tx.advance(State.RECEIPT, actor=human("a"))
        assert "closed" in excinfo.value.reason

    def test_machine_actor_cannot_issue_authority_labeled_event(
        self, tx: RealityTransaction
    ) -> None:
        # A machine event wearing VERIFIED_SOURCE fails validation at event
        # construction -> the transition is refused before touching the log.
        tx.open_intent(actor=human("a"), summary="s", label=Label.COMMUNITY_REPORT)
        with pytest.raises(TransitionRefused) as excinfo:
            tx.advance(State.EVIDENCE, actor=machine("m-1"), label=Label.VERIFIED_SOURCE)
        assert "MACHINE_INFERENCE" in excinfo.value.reason

    def test_receipt_with_open_blocking_debt_refused(self, tx: RealityTransaction) -> None:
        open_through_action(tx)
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
        add_witness(tx, WitnessClass.RECIPIENT_CONFIRMATION, "recipient-1")
        tx.advance(State.OUTCOME, actor=human("operator-1"))
        from szl_beacon.debt import DebtKind

        tx.debt.open(
            DebtKind.VERIFICATION_FAILED, {"probe": "late failure"}, opened_by="late-check"
        )
        tx.advance(
            State.RECONCILIATION, actor=human("operator-1"), label=Label.AUTHORIZED_OPERATOR
        )
        with pytest.raises(TransitionRefused) as excinfo:
            tx.advance(State.RECEIPT, actor=human("operator-1"))
        assert "Reality Debt" in excinfo.value.reason
