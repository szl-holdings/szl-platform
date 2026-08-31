"""Offline-first sync tests: union, dedup, conflict -> debt + counterfactual."""

from __future__ import annotations

import json
import time
from pathlib import Path

from conftest import build_chain, fixed_clock
from szl_beacon import events as ev
from szl_beacon import log as eventlog
from szl_beacon.labels import Label
from szl_beacon.sync import export_bundle, import_bundle, merge_logs


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", fixed_clock())


def _event(seq: int, prev: str | None, marker: str) -> dict:
    return ev.new_event(
        seq=seq,
        prev=prev,
        state_from=None if seq == 0 else "EVIDENCE",
        state_to="EVIDENCE",
        actor={"kind": "node", "id": f"node-{marker}"},
        payload={"marker": marker, "seq": seq},
        evidence_refs=[],
        label=Label.UNVERIFIED,
        created_at=_now(),
    )


def _divergent_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Two logs sharing genesis, diverging at seq 1."""

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    genesis = _event(0, None, "shared")
    eventlog.append_event(dir_a, genesis)
    eventlog.append_event(dir_b, genesis)
    a1 = _event(1, genesis["event_id"], "alpha")
    b1 = _event(1, genesis["event_id"], "bravo")
    eventlog.append_event(dir_a, a1)
    eventlog.append_event(dir_b, b1)
    eventlog.append_event(dir_a, _event(2, a1["event_id"], "alpha"))
    eventlog.append_event(dir_b, _event(2, b1["event_id"], "bravo"))
    return dir_a, dir_b


class TestBundleRoundtrip:
    def test_export_import_preserves_chain(self, tmp_path) -> None:
        source = tmp_path / "node-a"
        chain = build_chain(source, 4)
        bundle = tmp_path / "bundle"
        manifest = export_bundle(source, bundle)
        assert manifest["event_count"] == 4
        assert manifest["head_digest"] == chain[-1]["event_id"]

        imported = tmp_path / "node-b"
        report = import_bundle(bundle, imported)
        assert report["ok"]
        assert report["transport_digest_match"]
        assert report["chain_ok"]
        assert eventlog.read_events(imported) == eventlog.read_events(source)

    def test_tampered_bundle_refused(self, tmp_path) -> None:
        source = tmp_path / "node-a"
        build_chain(source, 2)
        bundle = tmp_path / "bundle"
        export_bundle(source, bundle)
        logfile = bundle / eventlog.LOG_FILENAME
        logfile.write_text(
            logfile.read_text(encoding="utf-8") + "garbage\n", encoding="utf-8"
        )
        report = import_bundle(bundle, tmp_path / "node-b")
        assert not report["ok"]
        assert not report["transport_digest_match"]


class TestMergeIdentical:
    def test_identical_logs_dedupe(self, tmp_path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        chain = build_chain(dir_a, 3)
        for event in chain:
            eventlog.append_event(dir_b, event)
        out = tmp_path / "out"
        report = merge_logs(dir_a, dir_b, out)
        assert report["ok"]
        assert report["merged_events"] == 3
        assert report["duplicates_removed"] == 3
        assert report["conflicts"] == []
        assert eventlog.verify(out).ok


class TestMergeConflict:
    def test_conflict_opens_debt_and_retains_both(self, tmp_path) -> None:
        dir_a, dir_b = _divergent_pair(tmp_path)
        out = tmp_path / "out"
        report = merge_logs(dir_a, dir_b, out)

        assert report["ok"]
        assert len(report["conflicts"]) == 2  # seq 1 and seq 2 both diverge
        assert report["debt"], "conflicting evidence must open Reality Debt"
        assert all(item["kind"] == "EVIDENCE_CONFLICT" for item in report["debt"])
        assert all(item["state"] == "OPEN" for item in report["debt"])
        assert report["debt_state"].startswith("OPEN")

        # Both copies retained: counterfactual record on disk.
        counterfactuals = list((out / "counterfactual").glob("*.json"))
        assert len(counterfactuals) == 2
        retained_digests = {
            json.loads(p.read_text(encoding="utf-8"))["event_id"] for p in counterfactuals
        }
        digests_a = {e["event_id"] for e in eventlog.read_events(dir_a)}
        digests_b = {e["event_id"] for e in eventlog.read_events(dir_b)}
        # The non-mainline side's conflicting events are the retained ones.
        assert retained_digests <= (digests_a | digests_b)
        assert len(retained_digests) == 2

        # The merged chain is internally consistent and carries an explicit
        # CONFLICTING_EVIDENCE record per conflict.
        assert eventlog.verify(out).ok
        merged = eventlog.read_events(out)
        conflict_records = [
            e for e in merged if e["payload"].get("type") == "CONFLICT_DETECTED"
        ]
        assert len(conflict_records) == 2
        assert all(e["label"] == "CONFLICTING_EVIDENCE" for e in conflict_records)
        # Both conflicting digests are referenced as evidence on the record.
        refs = conflict_records[0]["evidence_refs"]
        assert len(refs) == 2

    def test_merge_is_deterministic(self, tmp_path) -> None:
        dir_a, dir_b = _divergent_pair(tmp_path)
        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        report1 = merge_logs(dir_a, dir_b, out1)
        report2 = merge_logs(dir_a, dir_b, out2)
        main1 = [e["event_id"] for e in eventlog.read_events(out1)]
        main2 = [e["event_id"] for e in eventlog.read_events(out2)]
        # Mainline (excluding timestamped conflict records) is deterministic.
        spine1 = [
            d
            for d, e in zip(main1, eventlog.read_events(out1), strict=True)
            if e["payload"].get("type") != "CONFLICT_DETECTED"
        ]
        spine2 = [
            d
            for d, e in zip(main2, eventlog.read_events(out2), strict=True)
            if e["payload"].get("type") != "CONFLICT_DETECTED"
        ]
        assert spine1 == spine2
        assert report1["merged_events"] == report2["merged_events"]

    def test_merge_missing_log_reports_not_raises(self, tmp_path) -> None:
        dir_a = tmp_path / "a"
        build_chain(dir_a, 2)
        report = merge_logs(dir_a, tmp_path / "nonexistent", tmp_path / "out")
        assert not report["ok"]
        assert report["notes"]
