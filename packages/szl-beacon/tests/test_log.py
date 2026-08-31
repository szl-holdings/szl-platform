"""Event log integrity tests: build, append, and every tamper class."""

from __future__ import annotations

import json
import time

from conftest import build_chain, fixed_clock
from szl_beacon import events as ev
from szl_beacon import log as eventlog
from szl_beacon.labels import Label


def _codes(report) -> set[str]:
    return {f["code"] for f in report.to_dict()["findings"]}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", fixed_clock())


def _line(event: dict) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class TestBuildAndVerify:
    def test_valid_chain_verifies(self, logdir) -> None:
        chain = build_chain(logdir, 5)
        report = eventlog.verify(logdir)
        assert report.ok, report.to_dict()
        assert report.events_checked == 5
        assert chain[-1]["seq"] == 4

    def test_append_validates_fail_closed(self, logdir) -> None:
        bad = {
            "event_id": "0" * 64,
            "seq": 0,
            "prev": None,
            "state_from": None,
            "state_to": "INTENT",
            "actor": {"kind": "node", "id": "x"},
            "payload": {},
            "evidence_refs": [],
            "label": "UNVERIFIED",
            "created_at": _now(),
        }
        # Digest does not match body -> refused before any write.
        import pytest

        with pytest.raises(ev.EventValidationError):
            eventlog.append_event(logdir, bad)
        assert not (logdir / eventlog.LOG_FILENAME).exists()

    def test_missing_log_reports_not_raises(self, tmp_path) -> None:
        report = eventlog.verify(tmp_path / "nothing-here")
        assert not report.ok
        assert "NO_LOG" in _codes(report)

    def test_head(self, logdir) -> None:
        assert eventlog.head(logdir) is None
        chain = build_chain(logdir, 3)
        assert eventlog.head(logdir)["event_id"] == chain[-1]["event_id"]


class TestTamperDetection:
    def test_truncation_detected(self, logdir) -> None:
        build_chain(logdir, 4)
        path = logdir / eventlog.LOG_FILENAME
        content = path.read_text(encoding="utf-8")
        # Simulate a torn write: partial final line.
        path.write_text(content + '{"event_id": "abc", "seq":', encoding="utf-8")
        report = eventlog.verify(logdir)
        assert not report.ok
        assert "MALFORMED_LINE" in _codes(report)
        assert "TRUNCATED" in _codes(report)

    def test_reorder_detected(self, logdir) -> None:
        build_chain(logdir, 4)
        path = logdir / eventlog.LOG_FILENAME
        lines = path.read_text(encoding="utf-8").splitlines()
        # Swap events at seq 1 and seq 2.
        lines[1], lines[2] = lines[2], lines[1]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = eventlog.verify(logdir)
        assert not report.ok
        assert "REORDERED" in _codes(report)

    def test_replay_duplicate_seq_detected(self, logdir) -> None:
        chain = build_chain(logdir, 3)
        assert len(chain) == 3
        path = logdir / eventlog.LOG_FILENAME
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_line(chain[1]) + "\n")  # replay seq 1 at the tail
        report = eventlog.verify(logdir)
        assert not report.ok
        assert "REPLAY_DUPLICATE_SEQ" in _codes(report)

    def test_fork_same_seq_different_digest_detected(self, logdir) -> None:
        chain = build_chain(logdir, 3)
        # Build a competing event at seq 1: same prev, different payload.
        forked = ev.new_event(
            seq=1,
            prev=chain[0]["event_id"],
            state_from="EVIDENCE",
            state_to="EVIDENCE",
            actor={"kind": "node", "id": "attacker"},
            payload={"n": 999},
            evidence_refs=[],
            label=Label.UNVERIFIED,
            created_at=_now(),
        )
        assert forked["event_id"] != chain[1]["event_id"]
        path = logdir / eventlog.LOG_FILENAME
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_line(forked) + "\n")
        report = eventlog.verify(logdir)
        assert not report.ok
        assert "FORK_SAME_SEQ_DIFFERENT_DIGEST" in _codes(report)

    def test_prev_break_detected(self, logdir) -> None:
        build_chain(logdir, 4)
        path = logdir / eventlog.LOG_FILENAME
        lines = path.read_text(encoding="utf-8").splitlines()
        del lines[2]  # remove seq 2: seq 3's prev now dangles
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = eventlog.verify(logdir)
        assert not report.ok
        codes = _codes(report)
        assert "PREV_BREAK" in codes

    def test_doctored_payload_detected(self, logdir) -> None:
        chain = build_chain(logdir, 3)
        tampered = dict(chain[1])
        tampered["payload"] = {"n": 1_000_000}  # digest no longer matches
        path = logdir / eventlog.LOG_FILENAME
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[1] = _line(tampered)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = eventlog.verify(logdir)
        assert not report.ok
        assert "INVALID_EVENT" in _codes(report)

    def test_verify_never_raises_on_garbage(self, tmp_path) -> None:
        logdir = tmp_path / "garbage"
        logdir.mkdir()
        (logdir / eventlog.LOG_FILENAME).write_bytes(
            b"\xff\xfe not json at all \x00\x01\n[]\n"
        )
        report = eventlog.verify(logdir)
        assert not report.ok  # a report, not a traceback


class TestEventModel:
    def test_canonical_form_sorted_no_whitespace(self) -> None:
        assert ev.canonical_dumps({"b": 1, "a": [True, None]}) == '{"a":[true,null],"b":1}'

    def test_noninteger_float_rejected(self) -> None:
        import pytest

        with pytest.raises(ev.EventValidationError):
            ev.canonical_dumps({"reading": 4.1})

    def test_integer_valued_float_accepted(self) -> None:
        assert "4.0" in ev.canonical_dumps({"reading": 4.0})

    def test_digest_is_content_address(self) -> None:
        base = dict(
            seq=0,
            prev=None,
            state_from=None,
            state_to="INTENT",
            actor={"kind": "node", "id": "n"},
            payload={"x": 1},
            evidence_refs=[],
            label="UNVERIFIED",
            created_at=_now(),
        )
        digest = ev.event_digest(base)
        assert digest == ev.event_digest({**base, "extra_ignored": True})
        changed = {**base, "payload": {"x": 2}}
        assert ev.event_digest(changed) != digest

    def test_event_missing_label_rejected(self) -> None:
        import pytest

        event = dict(
            event_id="0" * 64,
            seq=0,
            prev=None,
            state_from=None,
            state_to="INTENT",
            actor={"kind": "node", "id": "n"},
            payload={},
            evidence_refs=[],
            created_at=_now(),
        )
        with pytest.raises(ev.EventValidationError):
            ev.validate_event_dict(event)
