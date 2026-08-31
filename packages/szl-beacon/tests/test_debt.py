"""Reality Debt register tests: open, block, explicit-only resolution."""

from __future__ import annotations

import pytest
from conftest import add_witness, human, open_through_action
from szl_beacon.debt import DebtError, DebtKind, DebtRegister
from szl_beacon.protocol import State, TransitionRefused
from szl_beacon.witness import WitnessClass


class TestRegister:
    def test_open_creates_open_item(self) -> None:
        register = DebtRegister()
        item = register.open(
            DebtKind.EVIDENCE_CONFLICT, {"seq": 3, "a": "x", "b": "y"}, opened_by="ev1"
        )
        assert item["state"] == "OPEN"
        assert item["kind"] == "EVIDENCE_CONFLICT"
        assert item["resolved_by"] is None
        assert item["id"].startswith("debt-")
        assert register.is_open(item["id"])

    def test_duplicate_open_is_idempotent(self) -> None:
        register = DebtRegister()
        first = register.open(DebtKind.MISSING_WITNESS, {"have": 1}, opened_by="ev1")
        second = register.open(DebtKind.MISSING_WITNESS, {"have": 1}, opened_by="ev1")
        assert first["id"] == second["id"]
        assert len(register) == 1

    def test_resolve_only_explicit(self) -> None:
        register = DebtRegister()
        item = register.open(DebtKind.UNVERIFIED_CLAIM, {"claim": "x"}, opened_by="ev1")
        resolved = register.resolve(item["id"], resolved_by="rec-event-digest")
        assert resolved["state"] == "RESOLVED"
        assert resolved["resolved_by"] == "rec-event-digest"
        assert not register.is_open(item["id"])

    def test_resolving_unknown_debt_refused(self) -> None:
        register = DebtRegister()
        with pytest.raises(DebtError):
            register.resolve("debt-doesnotexist", resolved_by="x")

    def test_double_resolution_refused(self) -> None:
        register = DebtRegister()
        item = register.open(DebtKind.MISSING_WITNESS, {}, opened_by="ev1")
        register.resolve(item["id"], resolved_by="r1")
        with pytest.raises(DebtError):
            register.resolve(item["id"], resolved_by="r2")

    def test_blocking_kinds_gate_verification(self) -> None:
        register = DebtRegister()
        blocking = [
            DebtKind.EVIDENCE_CONFLICT,
            DebtKind.MISSING_WITNESS,
            DebtKind.VERIFICATION_FAILED,
        ]
        for kind in blocking:
            fresh = DebtRegister()
            fresh.open(kind, {"k": kind.value}, opened_by="ev1")
            assert fresh.blocks_verification(), kind
        # UNVERIFIED_CLAIM is visible but non-blocking by policy.
        register.open(DebtKind.UNVERIFIED_CLAIM, {"claim": "x"}, opened_by="ev1")
        assert not register.blocks_verification()
        assert register.open_items()  # still on the record

    def test_no_auto_resolution(self) -> None:
        register = DebtRegister()
        item = register.open(DebtKind.EVIDENCE_CONFLICT, {"s": 1}, opened_by="ev1")
        # Time passing, witnesses arriving, nothing closes it but reconcile.
        assert register.is_open(item["id"])
        assert register.blocks_verification()


class TestDebtBlocksOutcome:
    def test_conflicting_evidence_blocks_outcome_until_reconciled(
        self, tx, logdir
    ) -> None:
        from szl_beacon import log as eventlog

        open_through_action(tx)
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
        add_witness(tx, WitnessClass.SECOND_NODE, "node-peer-7")

        # Conflicting evidence surfaces -> debt opens.
        conflict = tx.debt.open(
            DebtKind.EVIDENCE_CONFLICT,
            {"seq": 9, "digest_a": "aa", "digest_b": "bb"},
            opened_by="sync-merge",
        )

        # OUTCOME promotion refused while the debt is OPEN.
        with pytest.raises(TransitionRefused) as excinfo:
            tx.advance(State.OUTCOME, actor=human("operator-1"))
        assert "Reality Debt" in excinfo.value.reason
        assert tx.outcome_status.value == "UNVERIFIED"

        # Explicit reconciliation naming the debt id closes it.
        tx.reconcile(
            actor=human("operator-1"),
            debt_id=conflict["id"],
            resolution="operator reviewed both records; b is authoritative",
        )
        assert not tx.debt.blocks_verification()

        # Now OUTCOME passes and the chain still verifies.
        event = tx.advance(State.OUTCOME, actor=human("operator-1"))
        assert event["label"] == "OUTCOME_VERIFIED"
        assert eventlog.verify(logdir).ok

    def test_reconciliation_names_debt_id(self, tx) -> None:
        open_through_action(tx)
        add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
        item = tx.debt.open(DebtKind.MISSING_WITNESS, {"have": 1}, opened_by="gate")
        event = tx.reconcile(
            actor=human("operator-1"), debt_id=item["id"], resolution="witness arrived"
        )
        assert event["payload"]["debt_id"] == item["id"]
        assert tx.debt.to_list()[0]["resolved_by"] == event["event_id"]
