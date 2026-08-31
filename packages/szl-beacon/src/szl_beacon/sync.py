"""Offline-first peer sync.

Two Beacon nodes exchange signed events over any transport — Ethernet, Wi-Fi,
BLE, LoRa, cellular, or a USB drive carried by hand. The transport carries
the SAME events; nothing about the merge semantics depends on the link. In
this reference implementation the transport is file-based: a node exports a
bundle directory, the peer imports it. Production wraps the identical event
identity model in authenticated sessions per transport.

Merge semantics:

  * Merge is a digest-set union: every event from both logs enters the
    merged log.
  * Identical events (same content digest) dedupe to one copy.
  * Two events at the same ``seq`` with DIFFERENT digests are a
    conflict. Conflicts are NEVER silently resolved: both copies are
    retained (counterfactual record), and a CONFLICTING_EVIDENCE Reality
    Debt item is opened. The conflicting records are also appended to the
    merged chain as explicit CONFLICTING_EVIDENCE-labeled events.
  * The merged mainline is a deterministic FILE-ORDER choice only — it is
    not, and must never be presented as, a verdict on which side is true.
    Truth resolution is reconciliation by human/witness authority.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import events as ev
from . import log as eventlog
from .debt import DebtKind, DebtRegister
from .labels import Label

__all__ = [
    "SyncReport",
    "export_bundle",
    "import_bundle",
    "merge_logs",
]

BUNDLE_MANIFEST = "manifest.json"
COUNTERFACTUAL_DIR = "counterfactual"
SYNC_REPORT = "sync_report.json"


def _utc_now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class SyncReport(dict):
    """A sync report is a JSON-able dict with an ``ok`` flag."""


def export_bundle(logdir: Path | str, bundle_dir: Path | str) -> dict[str, Any]:
    """Export a node's log as a transport-neutral bundle directory.

    The bundle contains the event log verbatim plus a manifest with the
    event count, the head digest, and a sha256 digest of the log file
    itself, so the receiving side can detect transport corruption before
    any merge runs.
    """

    source = Path(logdir)
    bundle = Path(bundle_dir)
    events = eventlog.read_events(source)
    bundle.mkdir(parents=True, exist_ok=True)
    log_bytes = (source / eventlog.LOG_FILENAME).read_bytes()
    shutil.copyfile(source / eventlog.LOG_FILENAME, bundle / eventlog.LOG_FILENAME)
    manifest = {
        "format": "szl-beacon-bundle/1",
        "created_at": _utc_now(),
        "event_count": len(events),
        "head_digest": events[-1]["event_id"] if events else None,
        "log_sha256": hashlib.sha256(log_bytes).hexdigest(),
        "note": (
            "Transport-neutral bundle. Ethernet/Wi-Fi/BLE/LoRa/cellular carry "
            "the same signed events in production."
        ),
    }
    (bundle / BUNDLE_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def import_bundle(bundle_dir: Path | str, logdir: Path | str) -> dict[str, Any]:
    """Import a bundle into a local log directory after integrity checks.

    Transport corruption (bundle digest mismatch) fails the import BEFORE
    any event is read. Chain integrity of the imported log is then verified;
    a broken chain still imports (fail-closed verification happens against
    it later) but the report says so explicitly.
    """

    bundle = Path(bundle_dir)
    manifest = json.loads((bundle / BUNDLE_MANIFEST).read_text(encoding="utf-8"))
    log_bytes = (bundle / eventlog.LOG_FILENAME).read_bytes()
    digest = hashlib.sha256(log_bytes).hexdigest()
    report: dict[str, Any] = {
        "ok": digest == manifest.get("log_sha256"),
        "transport_digest_match": digest == manifest.get("log_sha256"),
        "manifest": manifest,
    }
    if not report["transport_digest_match"]:
        report["error"] = "bundle log digest mismatch: transport corruption; import refused"
        return report
    target = Path(logdir)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundle / eventlog.LOG_FILENAME, target / eventlog.LOG_FILENAME)
    verify_report = eventlog.verify(target)
    report["chain_ok"] = verify_report.ok
    report["chain_findings"] = verify_report.to_dict()["findings"]
    return report


def _load_events_safely(logdir: Path | str) -> tuple[list[dict], str | None]:
    """Read a log without raising. Returns (events, error_or_none)."""

    try:
        return eventlog.read_events(logdir), None
    except ValueError as exc:
        return [], str(exc)


def merge_logs(dir_a: Path | str, dir_b: Path | str, out_dir: Path | str) -> SyncReport:
    """Merge two event logs into ``out_dir``. NEVER raises on bad input.

    Output layout::

        out_dir/events.jsonl        merged mainline (deterministic file order)
        out_dir/counterfactual/     the non-mainline copies of conflicts
        out_dir/sync_report.json    this report, including Reality Debt opened

    Mainline rule (documented and deterministic): the two chains share a
    common prefix from genesis. At the FIRST conflicting seq, the side whose
    conflicting event digest is lexicographically smaller supplies the
    mainline at that seq AND for every later seq (switching sides mid-fork
    would break prev-links). This is file order, not truth — the debt item
    says so.
    """

    report: dict[str, Any] = {
        "ok": True,
        "conflicts": [],
        "debt": [],
        "duplicates_removed": 0,
        "notes": [],
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counter_dir = out / COUNTERFACTUAL_DIR

    events_a, err_a = _load_events_safely(dir_a)
    events_b, err_b = _load_events_safely(dir_b)
    if err_a:
        report["ok"] = False
        report["notes"].append(f"side a unreadable: {err_a}")
    if err_b:
        report["ok"] = False
        report["notes"].append(f"side b unreadable: {err_b}")
    if err_a or err_b:
        _write_report(out, report)
        return SyncReport(report)

    report["a_events"] = len(events_a)
    report["b_events"] = len(events_b)

    by_seq_a = _index_by_seq(events_a)
    by_seq_b = _index_by_seq(events_b)
    all_seqs = sorted(set(by_seq_a) | set(by_seq_b))

    debt = DebtRegister()
    mainline: list[dict] = []
    pinned_side: str | None = None  # after a fork, mainline follows one side

    for seq in all_seqs:
        in_a = by_seq_a.get(seq)
        in_b = by_seq_b.get(seq)
        if in_a is not None and in_b is not None:
            if in_a["event_id"] == in_b["event_id"]:
                mainline.append(in_a)
                report["duplicates_removed"] += 1
                continue
            # Conflict at this seq. Never silently resolved.
            item = debt.open(
                DebtKind.EVIDENCE_CONFLICT,
                {
                    "seq": seq,
                    "digest_a": in_a["event_id"],
                    "digest_b": in_b["event_id"],
                },
                opened_by="sync-merge",
            )
            counter_dir.mkdir(parents=True, exist_ok=True)
            report["conflicts"].append(
                {
                    "seq": seq,
                    "digest_a": in_a["event_id"],
                    "digest_b": in_b["event_id"],
                    "debt_id": item["id"],
                }
            )
            if pinned_side is None:
                ordered = sorted(
                    (("a", in_a), ("b", in_b)), key=lambda pair: pair[1]["event_id"]
                )
                pinned_side = ordered[0][0]
                mainline.append(ordered[0][1])
                non_mainline = ordered[1]
                _retain(counter_dir, seq, non_mainline[0], non_mainline[1])
            else:
                chosen = in_a if pinned_side == "a" else in_b
                other = in_b if pinned_side == "a" else in_a
                mainline.append(chosen)
                _retain(counter_dir, seq, "b" if pinned_side == "a" else "a", other)
        else:
            event = in_a if in_a is not None else in_b
            side = "a" if in_a is not None else "b"
            if pinned_side is not None and side != pinned_side:
                # Post-fork event from the non-mainline side: retain as
                # counterfactual, keep mainline chain integrity.
                _retain(counter_dir, seq, side, event)
                report["notes"].append(
                    f"seq {seq} from side {side} retained as counterfactual "
                    f"(mainline pinned to side {pinned_side})"
                )
                continue
            mainline.append(event)

    merged_path = out / eventlog.LOG_FILENAME
    with merged_path.open("w", encoding="utf-8") as handle:
        for event in mainline:
            handle.write(
                json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            )

    # Make every conflict explicit ON the merged chain itself: append one
    # CONFLICTING_EVIDENCE-labeled record per conflict. The append-only log
    # admits the disagreement; it does not adjudicate it.
    for conflict in report["conflicts"]:
        _append_conflict_record(out, conflict, report)

    merged_verify = eventlog.verify(out)
    report["merged_events"] = len(mainline)
    report["merged_chain_ok"] = merged_verify.ok
    if not merged_verify.ok:
        report["ok"] = False
        report["notes"].append(
            "merged mainline failed verification: "
            + "; ".join(f["code"] for f in merged_verify.to_dict()["findings"])
        )
    report["mainline_pinned_side"] = pinned_side
    report["debt"] = debt.to_list()
    report["debt_state"] = (
        "OPEN — conflicts await explicit reconciliation; never auto-resolved"
        if report["debt"]
        else "none"
    )
    _write_report(out, report)
    return SyncReport(report)


def _write_report(out: Path, report: dict[str, Any]) -> None:
    (out / SYNC_REPORT).write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def _index_by_seq(events: list[dict]) -> dict[int, dict]:
    """Index a log by seq; same-seq duplicates within one side keep first."""

    result: dict[int, dict] = {}
    for event in events:
        seq = event.get("seq")
        if isinstance(seq, int) and seq not in result:
            result[seq] = event
    return result


def _retain(counter_dir: Path, seq: int, side: str, event: dict) -> None:
    """Retain a non-mainline conflicting copy as the counterfactual record."""

    name = f"seq{seq:06d}-side{side}-{event['event_id'][:12]}.json"
    (counter_dir / name).write_text(
        json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _append_conflict_record(out: Path, conflict: dict, report: dict) -> None:
    """Append a CONFLICTING_EVIDENCE record to the merged chain."""

    head = eventlog.head(out)
    if head is None:
        return
    event = ev.new_event(
        seq=int(head["seq"]) + 1,
        prev=str(head["event_id"]),
        state_from=str(head["state_to"]),
        state_to="EVIDENCE",
        actor={"kind": "node", "id": "sync-merge"},
        payload={
            "type": "CONFLICT_DETECTED",
            "seq": conflict["seq"],
            "digest_a": conflict["digest_a"],
            "digest_b": conflict["digest_b"],
            "debt_id": conflict["debt_id"],
            "note": (
                "Counterfactual record: both copies retained; Resolution is "
                "human reconciliation, never automatic."
            ),
        },
        evidence_refs=[conflict["digest_a"], conflict["digest_b"]],
        label=Label.CONFLICTING_EVIDENCE,
        created_at=_utc_now(),
    )
    eventlog.append_event(out, event)
