"""CLI tests, including the demo subprocess end-to-end."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
PKG_ROOT = Path(__file__).resolve().parent.parent


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argv list, shell=False, fixed executable
        [sys.executable, "-m", "szl_beacon", *argv],
        capture_output=True,
        text=True,
        env=_env(),
        timeout=60,
        check=False,
    )


class TestDemoSubprocess:
    def test_demo_exits_zero_and_chain_verifies(self, tmp_path) -> None:
        result = _run("demo", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)

        # 11 state transitions printed (12 events: WITNESS entered twice).
        assert data["transition_count"] == 12
        visited = [t["transition"].split(" -> ")[1] for t in data["transitions"]]
        assert visited[0] == "INTENT"
        assert visited[-1] == "RECEIPT"
        assert {"ACTION", "WITNESS", "OUTCOME", "RECEIPT"} <= set(visited)
        for transition in data["transitions"]:
            assert len(transition["event_id"]) == 64

        # The receipt is honest.
        assert data["receipt"]["outcome_status"] == "VERIFIED"
        assert data["receipt"]["physical_units_fielded"] == 0

        # Verify the printed chain through the CLI itself.
        logdir = data["logdir"]
        assert Path(logdir).is_dir()
        verify_result = _run("verify", logdir, "--json")
        assert verify_result.returncode == 0, verify_result.stderr
        report = json.loads(verify_result.stdout)
        assert report["ok"], report["findings"]
        assert report["events_checked"] == 12

    def test_demo_human_readable_still_exits_zero(self) -> None:
        result = _run("demo")
        assert result.returncode == 0, result.stderr
        assert "verifiable chain written to:" in result.stdout


class TestHelpAndJson:
    def test_top_level_help(self) -> None:
        result = _run("--help")
        assert result.returncode == 0
        for word in ("demo", "verify", "fleet", "rc1-test", "sync"):
            assert word in result.stdout

    def test_every_subcommand_help(self) -> None:
        for argv in (
            ("demo", "--help"),
            ("verify", "--help"),
            ("fleet", "--help"),
            ("fleet", "validate", "--help"),
            ("rc1-test", "--help"),
            ("sync", "--help"),
        ):
            result = _run(*argv)
            assert result.returncode == 0, (argv, result.stderr)
            assert "--json" in result.stdout or "usage" in result.stdout


class TestFleetCommand:
    def test_fleet_validate_shipped_yaml_passes(self) -> None:
        result = _run("fleet", "validate", str(PKG_ROOT / "fleet" / "fleet.yaml"))
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout
        assert "50 nodes" in result.stdout

    def test_fleet_validate_broken_yaml_fails(self, tmp_path) -> None:
        broken = tmp_path / "broken.yaml"
        broken.write_text(
            "schema: szl-beacon-fleet/1\n"
            "witness_groups:\n"
            "  thin: [INDEPENDENT_SENSOR]\n"
            "nodes:\n"
            "  - node_id: n1\n"
            "    role: FIELD\n"
            "    region: test\n"
            "    sync_window_minutes: 30\n"
            "    witness_groups: [thin]\n",
            encoding="utf-8",
        )
        result = _run("fleet", "validate", str(broken), "--json")
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert not data["ok"]
        codes = {f["code"] for f in data["findings"]}
        assert "FIELD_WITHOUT_DIVERSITY" in codes

    def test_fleet_validate_missing_file_exit_2(self, tmp_path) -> None:
        result = _run("fleet", "validate", str(tmp_path / "nope.yaml"))
        assert result.returncode == 2


class TestRc1Command:
    def test_rc1_test_all_four_pass(self) -> None:
        result = _run("rc1-test", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["simulation"] is True
        assert data["all_passed"] is True
        assert [r["test"] for r in data["results"]] == [
            "RC1-01",
            "RC1-02",
            "RC1-03",
            "RC1-04",
        ]


class TestSyncCommand:
    def test_sync_two_logs(self, tmp_path) -> None:
        from conftest import build_chain

        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        chain = build_chain(dir_a, 3)
        from szl_beacon import log as eventlog

        for event in chain:
            eventlog.append_event(dir_b, event)
        out = tmp_path / "out"
        result = _run("sync", str(dir_a), str(dir_b), str(out), "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["ok"]
        assert data["duplicates_removed"] == 3
