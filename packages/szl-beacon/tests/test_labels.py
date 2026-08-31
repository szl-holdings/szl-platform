"""Label enforcement tests: machine hard-typing, render separation."""

from __future__ import annotations

import time

import pytest
from conftest import fixed_clock
from szl_beacon import events as ev
from szl_beacon.labels import (
    Label,
    LabelError,
    coerce_label,
    render_labeled,
    validate_event_label,
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", fixed_clock())


class TestCoerce:
    def test_known_labels_round_trip(self) -> None:
        for label in Label:
            assert coerce_label(label.value) is label
            assert coerce_label(label) is label

    def test_unknown_label_refused(self) -> None:
        with pytest.raises(LabelError):
            coerce_label("TRUSTED")  # not a label; refused
        with pytest.raises(LabelError):
            coerce_label(None)
        with pytest.raises(LabelError):
            coerce_label(42)


class TestMachineHardTyping:
    def test_machine_with_authority_label_rejected(self) -> None:
        with pytest.raises(LabelError):
            validate_event_label(Label.VERIFIED_SOURCE, origin="machine")

    def test_machine_with_machine_label_accepted(self) -> None:
        assert validate_event_label(Label.MACHINE_INFERENCE, origin="machine") is (
            Label.MACHINE_INFERENCE
        )

    def test_machine_event_construction_rejected(self) -> None:
        """End-to-end: a machine event without MACHINE_INFERENCE is refused."""

        with pytest.raises(ev.EventValidationError):
            ev.new_event(
                seq=0,
                prev=None,
                state_from=None,
                state_to="INTENT",
                actor={"kind": "machine", "id": "a11oy-1"},
                payload={"summary": "official-looking output"},
                evidence_refs=[],
                label=Label.VERIFIED_SOURCE,  # machine wearing authority colors
                created_at=_now(),
            )

    def test_machine_event_with_machine_label_accepted(self) -> None:
        event = ev.new_event(
            seq=0,
            prev=None,
            state_from=None,
            state_to="PROPOSAL",
            actor={"kind": "machine", "id": "a11oy-1"},
            payload={"summary": "matching proposal"},
            evidence_refs=[],
            label=Label.MACHINE_INFERENCE,
            created_at=_now(),
        )
        assert event["label"] == "MACHINE_INFERENCE"


class TestRender:
    def test_machine_render_distinct_from_authority(self) -> None:
        machine_event = {
            "event_id": "ab" * 32,
            "label": "MACHINE_INFERENCE",
            "payload": {"summary": "model suggestion"},
        }
        authority_event = {
            "event_id": "cd" * 32,
            "label": "VERIFIED_SOURCE",
            "payload": {"summary": "sensor reading"},
        }
        machine_render = render_labeled(machine_event)
        authority_render = render_labeled(authority_event)
        assert "machine inference" in machine_render
        assert "not authority" in machine_render
        assert "[VERIFIED SOURCE]" in authority_render
        assert "not authority" not in authority_render

    def test_weak_labels_render_explicitly(self) -> None:
        for label, marker in (
            ("UNVERIFIED", "[UNVERIFIED]"),
            ("CONFLICTING_EVIDENCE", "CONFLICTING EVIDENCE"),
            ("COMMUNITY_REPORT", "unverified"),
        ):
            rendered = render_labeled({"label": label, "payload": {"summary": "x"}})
            assert marker in rendered

    def test_outcome_verified_render(self) -> None:
        rendered = render_labeled(
            {
                "event_id": "ef" * 32,
                "label": "OUTCOME_VERIFIED",
                "payload": {"summary": "delivered"},
            }
        )
        assert "[OUTCOME VERIFIED]" in rendered

    def test_render_without_summary_explicit_placeholder(self) -> None:
        rendered = render_labeled({"label": "UNVERIFIED", "payload": {}})
        assert "(no summary recorded)" in rendered

    def test_render_refuses_unknown_label(self) -> None:
        with pytest.raises(LabelError):
            render_labeled({"label": "OFFICIAL_DO_NOT_WORRY", "payload": {}})
