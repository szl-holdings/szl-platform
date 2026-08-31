"""Shared fixtures and helpers for the szl-beacon test suite."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Make the package importable without installation (src layout).
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from szl_beacon import events as ev  # noqa: E402
from szl_beacon import log as eventlog  # noqa: E402
from szl_beacon.labels import Label  # noqa: E402
from szl_beacon.protocol import RealityTransaction, State  # noqa: E402
from szl_beacon.witness import WitnessClass, witness_event_payload  # noqa: E402

FIXED_EPOCH = 1_800_000_000


def fixed_clock() -> time.struct_time:
    return time.gmtime(FIXED_EPOCH)


@pytest.fixture()
def logdir(tmp_path: Path) -> Path:
    return tmp_path / "log"


@pytest.fixture()
def tx(logdir: Path) -> RealityTransaction:
    return RealityTransaction(logdir, node_id="beacon-test-00", clock=fixed_clock)


def human(name: str) -> dict:
    return {"kind": "human", "id": name}


def machine(name: str) -> dict:
    return {"kind": "machine", "id": name}


def open_through_policy(tx: RealityTransaction) -> None:
    """Drive a transaction INTENT -> POLICY (5 transitions)."""

    tx.open_intent(
        actor=human("resident-1"),
        summary="help request",
        label=Label.COMMUNITY_REPORT,
        request={"proposal_type": "matching_proposal"},
    )
    tx.advance(State.EVIDENCE, actor=human("resident-1"), label=Label.COMMUNITY_REPORT)
    tx.advance(State.PROPOSAL, actor=machine("a11oy-1"), label=Label.MACHINE_INFERENCE)
    tx.advance(State.SIMULATION, actor=machine("a11oy-1"), label=Label.MACHINE_INFERENCE)
    tx.advance(State.POLICY, actor=human("operator-1"), label=Label.AUTHORIZED_OPERATOR)


def open_through_action(tx: RealityTransaction) -> None:
    """Drive INTENT -> ACTION with a NOTIFY action class."""

    open_through_policy(tx)
    tx.advance(
        State.CONSENT,
        actor=human("operator-1"),
        payload={"action_class": "NOTIFY"},
        label=Label.AUTHORIZED_OPERATOR,
    )
    tx.advance(State.ACTION, actor=human("helper-1"), label=Label.VERIFIED_SOURCE)


def add_witness(tx: RealityTransaction, wclass: WitnessClass, observer: str) -> dict:
    return tx.advance(
        State.WITNESS,
        actor={"kind": "sensor", "id": observer},
        payload=witness_event_payload(
            wclass, f"ev:{observer}", observer_id=observer, observation="corroborated"
        ),
        label=Label.VERIFIED_SOURCE,
    )


def run_happy_path(tx: RealityTransaction) -> list[dict]:
    """Full 11-transition transaction; returns the events in order."""

    events: list[dict] = []
    open_through_action(tx)
    add_witness(tx, WitnessClass.INDEPENDENT_SENSOR, "sensor-1")
    add_witness(tx, WitnessClass.RECIPIENT_CONFIRMATION, "recipient-1")
    events.append(tx.advance(State.OUTCOME, actor=human("operator-1")))
    tx.advance(
        State.RECONCILIATION,
        actor=human("operator-1"),
        payload={"open_debt": []},
        label=Label.AUTHORIZED_OPERATOR,
    )
    events.append(tx.advance(State.RECEIPT, actor=human("operator-1")))
    return events


def build_chain(logdir: Path, count: int, *, payloads: list[dict] | None = None) -> list[dict]:
    """Build a standalone chain of ``count`` raw events and append them."""

    built: list[dict] = []
    prev = None
    for seq in range(count):
        payload = payloads[seq] if payloads else {"n": seq}
        event = ev.new_event(
            seq=seq,
            prev=prev,
            state_from=None if seq == 0 else "EVIDENCE",
            state_to="EVIDENCE",
            actor={"kind": "node", "id": "chain-builder"},
            payload=payload,
            evidence_refs=[],
            label=Label.UNVERIFIED,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", fixed_clock()),
        )
        eventlog.append_event(logdir, event)
        built.append(event)
        prev = event["event_id"]
    return built
