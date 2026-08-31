"""Witness diversity tests."""

from __future__ import annotations

import pytest
from conftest import add_witness, human, open_through_action
from szl_beacon.debt import DebtKind, DebtRegister
from szl_beacon.protocol import State, TransitionRefused
from szl_beacon.witness import (
    WitnessClass,
    WitnessError,
    check_outcome_gate,
    evaluate_witnesses,
    witness_event_payload,
)


def _witness_event(wclass: str, evidence_ref: str | None, observer: str = "obs") -> dict:
    payload = {"witness_class": wclass, "observer_id": observer, "observation": "saw it"}
    if evidence_ref is not None:
        payload["evidence_ref"] = evidence_ref
    return {"payload": payload, "evidence_refs": []}


class TestEvaluate:
    def test_two_distinct_classes_pass(self) -> None:
        report = evaluate_witnesses(
            [
                _witness_event("INDEPENDENT_SENSOR", "ev:1"),
                _witness_event("RECIPIENT_CONFIRMATION", "ev:2"),
            ]
        )
        assert report["ok"]
        assert report["count"] == 2
        assert set(report["distinct_classes"]) == {
            "INDEPENDENT_SENSOR",
            "RECIPIENT_CONFIRMATION",
        }

    def test_same_class_duplicates_do_not_count(self) -> None:
        report = evaluate_witnesses(
            [
                _witness_event("INDEPENDENT_SENSOR", "ev:1", "s1"),
                _witness_event("INDEPENDENT_SENSOR", "ev:2", "s2"),
                _witness_event("INDEPENDENT_SENSOR", "ev:3", "s3"),
            ]
        )
        assert not report["ok"]
        assert report["count"] == 1
        assert report["duplicates_ignored"] == 2

    def test_witness_without_evidence_ref_rejected(self) -> None:
        report = evaluate_witnesses(
            [
                _witness_event("INDEPENDENT_SENSOR", None),
                _witness_event("SECOND_NODE", "ev:2"),
            ]
        )
        assert not report["ok"]
        assert report["count"] == 1
        assert any("no evidence ref" in r for r in report["rejections"])

    def test_unknown_class_rejected(self) -> None:
        report = evaluate_witnesses([_witness_event("MY_BUDDY_SAID", "ev:1")])
        assert not report["ok"]
        assert report["count"] == 0
        assert report["rejections"]


class TestPayloadBuilder:
    def test_payload_carries_class_ref_observer(self) -> None:
        payload = witness_event_payload(
            WitnessClass.SECOND_NODE, "ev:abc", observer_id="node-2", observation="ok"
        )
        assert payload["witness_class"] == "SECOND_NODE"
        assert payload["evidence_ref"] == "ev:abc"
        assert payload["observer_id"] == "node-2"

    def test_missing_evidence_ref_refused(self) -> None:
        with pytest.raises(WitnessError):
            witness_event_payload(
                WitnessClass.SECOND_NODE, "", observer_id="n", observation="x"
            )

    def test_unknown_class_refused(self) -> None:
        with pytest.raises(WitnessError):
            witness_event_payload("TRUST_ME", "ev:1", observer_id="n", observation="x")


class TestOutcomeGate:
    def test_gate_blocked_by_open_debt(self) -> None:
        debt = DebtRegister()
        debt.open(DebtKind.EVIDENCE_CONFLICT, {"seq": 1}, opened_by="sync")
        gate = check_outcome_gate(
            [
                _witness_event("INDEPENDENT_SENSOR", "ev:1"),
                _witness_event("SECOND_NODE", "ev:2"),
            ],
            debt,
        )
        assert not gate["ok"]
        assert any("Reality Debt" in reason for reason in gate["reasons"])
        assert gate["blocking_debt"]

    def test_gate_reports_missing_witness_kind(self) -> None:
        gate = check_outcome_gate([_witness_event("INDEPENDENT_SENSOR", "ev:1")], DebtRegister())
        assert not gate["ok"]
        assert gate["missing_witness_kind"] == DebtKind.MISSING_WITNESS.value


class TestProtocolIntegration:
    def test_same_class_duplicates_rejected_at_outcome(self, tx) -> None:
        """Two witnesses of the SAME class cannot promote OUTCOME."""

        open_through_action(tx)
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-2")
        with pytest.raises(TransitionRefused) as excinfo:
            tx.advance(State.OUTCOME, actor=human("operator-1"))
        assert "1 distinct class" in excinfo.value.reason
        # A MISSING_WITNESS debt item was opened by the refusal path.
        kinds = {item["kind"] for item in tx.debt.open_items()}
        assert DebtKind.MISSING_WITNESS.value in kinds

    def test_two_distinct_classes_promote(self, tx) -> None:
        open_through_action(tx)
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
        add_witness(tx, WitnessClass.RECIPIENT_CONFIRMATION, "recipient-1")
        event = tx.advance(State.OUTCOME, actor=human("operator-1"))
        assert event["payload"]["status"] == "VERIFIED"
        assert len(event["payload"]["witness_classes"]) == 2
