"""Append-only, hash-chained JSONL event log.

Every Reality Protocol transition appends one event. The log is the
counterfactual record: nothing is ever rewritten or deleted, so conflicting
evidence, refusals, and failures remain on the record forever.

Integrity model: each event carries ``prev`` = digest of its predecessor, so
truncation, reordering, replay (duplicate seq), forking (same seq, different
digest), and prev-breaks are all detectable offline by :func:`verify`.

``verify`` NEVER raises on bad input — it returns a report naming every
finding. That is the honesty doctrine applied to tooling: a broken log is a
report, not a traceback.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .events import EventValidationError, event_digest, validate_event_dict

__all__ = [
    "LOG_FILENAME",
    "append_event",
    "read_events",
    "head",
    "verify",
    "VerifyReport",
]

LOG_FILENAME = "events.jsonl"

#: Finding codes emitted by verify(). Stable identifiers for tooling.
F_TRUNCATED = "TRUNCATED"
F_REORDERED = "REORDERED"
F_REPLAY = "REPLAY_DUPLICATE_SEQ"
F_FORK = "FORK_SAME_SEQ_DIFFERENT_DIGEST"
F_PREV_BREAK = "PREV_BREAK"
F_INVALID_EVENT = "INVALID_EVENT"
F_MALFORMED_LINE = "MALFORMED_LINE"


def _log_path(logdir: Path | str) -> Path:
    path = Path(logdir)
    if path.is_dir() or path.suffix != ".jsonl":
        return path / LOG_FILENAME
    return path


def append_event(logdir: Path | str, event: dict) -> Path:
    """Validate and append one event to the log. Fail closed.

    The event is fully validated (schema, digest, label) before anything is
    written; on any validation failure nothing is appended. Appends are
    atomic at the line level (single write + flush + fsync).
    """

    import os

    validate_event_dict(event)
    path = _log_path(logdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def read_events(logdir: Path | str) -> list[dict]:
    """Read all events from the log, in file order.

    Raises :class:`ValueError` on a malformed line — reading is strict; use
    :func:`verify` when you need a never-raising report instead.
    """

    path = _log_path(logdir)
    if not path.exists():
        raise ValueError(f"no event log at {path}")
    events: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: malformed JSON line: {exc}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"{path}:{lineno}: event is not a JSON object")
            events.append(event)
    return events


def head(logdir: Path | str) -> dict | None:
    """Return the last event in the log, or None if the log is empty/missing."""

    path = _log_path(logdir)
    if not path.exists():
        return None
    last: dict | None = None
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if raw:
                last = json.loads(raw)
    return last


class VerifyReport:
    """Result of :func:`verify`. ``ok`` is True only with zero findings."""

    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []
        self.events_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings

    def add(self, code: str, detail: str, *, lineno: int | None = None) -> None:
        finding: dict[str, Any] = {"code": code, "detail": detail}
        if lineno is not None:
            finding["lineno"] = lineno
        self.findings.append(finding)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "events_checked": self.events_checked,
            "findings": list(self.findings),
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        status = "ok" if self.ok else f"{len(self.findings)} findings"
        return f"<VerifyReport {status}, {self.events_checked} events>"


def _check_line_structure(event: dict, lineno: int, report: VerifyReport) -> bool:
    try:
        validate_event_dict(event)
    except EventValidationError as exc:
        report.add(F_INVALID_EVENT, str(exc), lineno=lineno)
        return False
    return True


def verify(logdir: Path | str, events: Iterable[dict] | None = None) -> VerifyReport:
    """Verify a hash-chained log. NEVER raises on bad input.

    Detects, with explicit findings:
      * TRUNCATED      — file ends mid-chain is not directly knowable, but a
        log whose last line is malformed or whose events stop before the
        recorded head digest is reported; more practically: any structural
        break at the tail (malformed final line) is flagged, and callers can
        compare against a known head.
      * REORDERED      — seq values not strictly increasing by 1 from 0.
      * REPLAY_DUPLICATE_SEQ — the same seq appears twice with identical
        digest (a replayed copy appended).
      * FORK_SAME_SEQ_DIFFERENT_DIGEST — same seq, different content digest.
      * PREV_BREAK     — an event's ``prev`` does not match its predecessor's
        digest.
      * INVALID_EVENT / MALFORMED_LINE — schema, label, or digest failures.

    Returns a :class:`VerifyReport`; ``report.ok`` is the verdict.
    """

    report = VerifyReport()

    if events is None:
        path = _log_path(logdir)
        if not path.exists():
            report.add("NO_LOG", f"no event log at {path}")
            return report
        parsed: list[tuple[int, dict | None]] = []
        try:
            handle_cm = path.open(encoding="utf-8", errors="strict")
        except OSError as exc:
            report.add(F_MALFORMED_LINE, f"cannot open log: {exc}")
            return report
        with handle_cm as handle:
            try:
                raw_lines = list(handle)
            except (UnicodeDecodeError, OSError) as exc:
                report.add(F_MALFORMED_LINE, f"log is not decodable UTF-8 text: {exc}")
                return report
        for lineno, raw in enumerate(raw_lines, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                report.add(F_MALFORMED_LINE, f"malformed JSON: {exc}", lineno=lineno)
                parsed.append((lineno, None))
                continue
            if not isinstance(event, dict):
                report.add(F_MALFORMED_LINE, "line is not a JSON object", lineno=lineno)
                parsed.append((lineno, None))
                continue
            parsed.append((lineno, event))
        numbered = parsed
    else:
        numbered = [(index + 1, event) for index, event in enumerate(events)]

    seen_seqs: dict[int, str] = {}
    prev_digest: str | None = None
    expected_seq = 0
    order_broken = False

    for lineno, event in numbered:
        if event is None:
            # Already reported as malformed; the chain cannot continue past
            # it, which itself is a truncation-style break.
            report.add(F_TRUNCATED, "chain unverifiable past malformed line", lineno=lineno)
            break

        report.events_checked += 1
        if not _check_line_structure(event, lineno, report):
            prev_digest = None  # chain position unknown after invalid event
            expected_seq = -1
            order_broken = True
            continue

        seq = event["seq"]
        digest = event_digest(event)

        if seq in seen_seqs:
            if seen_seqs[seq] == digest:
                report.add(
                    F_REPLAY,
                    f"seq {seq} replayed: identical event appears again",
                    lineno=lineno,
                )
            else:
                report.add(
                    F_FORK,
                    f"seq {seq} has two different digests "
                    f"({seen_seqs[seq][:12]}… vs {digest[:12]}…)",
                    lineno=lineno,
                )
        else:
            seen_seqs[seq] = digest

        if not order_broken and seq != expected_seq:
            report.add(
                F_REORDERED,
                f"expected seq {expected_seq}, found {seq}",
                lineno=lineno,
            )
            order_broken = True

        if seq == 0:
            if event["prev"] is not None:
                report.add(F_PREV_BREAK, "genesis event has non-null prev", lineno=lineno)
        elif prev_digest is not None and event["prev"] != prev_digest:
            report.add(
                F_PREV_BREAK,
                f"event seq {seq} prev does not match predecessor digest",
                lineno=lineno,
            )

        prev_digest = digest
        if not order_broken:
            expected_seq = seq + 1

    return report
