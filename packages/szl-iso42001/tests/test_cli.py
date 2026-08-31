"""CLI tests — in-process for logic, subprocess for the real entry contract.

The subprocess smoke tests run `python -m szl_iso42001` exactly as a user
would, with PYTHONPATH pointed at src/ so no install is required. They are
fully offline.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from szl_iso42001 import __version__
from szl_iso42001.cli import (
    EXIT_OK,
    EXIT_TEMPLATE_GENERATED,
    main,
)
from szl_iso42001.controls import DISCLAIMER, load_controls

PKG_SRC = Path(__file__).resolve().parent.parent / "src"


def run_module(*argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m szl_iso42001 ...` in a subprocess, offline, no install."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(  # noqa: S603 — argv is test-authored, never user input
        [sys.executable, "-m", "szl_iso42001", *argv],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# In-process behavior tests (fast, precise)
# ---------------------------------------------------------------------------

def test_check_missing_answers_writes_template_and_exits_2(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    code = main(["check", "--answers", str(answers), "--out", str(tmp_path)])
    assert code == EXIT_TEMPLATE_GENERATED
    assert answers.exists()

    # The template must cover every control, all set to unknown.
    content = answers.read_text(encoding="utf-8")
    for c in load_controls():
        assert f'{c.id}: "unknown"' in content
    out = capsys.readouterr().out
    assert "unknown" in out.lower()
    assert "fill it in" in out  # the message tells the user what to do next


def test_check_template_json_mode(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    code = main(["check", "--answers", str(answers), "--out", str(tmp_path), "--json"])
    assert code == EXIT_TEMPLATE_GENERATED
    payload = json.loads(capsys.readouterr().out)
    assert payload["event"] == "template_generated"
    assert payload["exit_code"] == EXIT_TEMPLATE_GENERATED
    assert payload["control_count"] == len(load_controls())


def test_check_runs_end_to_end(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    main(["check", "--answers", str(answers)])  # generates template
    capsys.readouterr()
    out_dir = tmp_path / "out"
    code = main(["check", "--answers", str(answers), "--out", str(out_dir)])
    assert code == EXIT_OK
    captured = capsys.readouterr().out
    assert "NOT_READY" in captured  # all-unknown template => honest NOT_READY

    report = (out_dir / "readiness-report.md").read_text(encoding="utf-8")
    assert DISCLAIMER in report
    assert "**Band:** `NOT_READY`" in report
    # Receipt file exists — unsigned in this sandbox, named honestly.
    receipts = list(out_dir.glob("readiness-receipt*"))
    assert len(receipts) == 1
    if receipts[0].name.endswith(".unsigned.json"):
        body = json.loads(receipts[0].read_text(encoding="utf-8"))
        assert body["signatures"] == []


def test_check_json_mode_is_parseable(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    main(["check", "--answers", str(answers)])
    capsys.readouterr()
    code = main(
        ["check", "--answers", str(answers), "--out", str(tmp_path), "--json"]
    )
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["band"] == "NOT_READY"
    assert payload["answer_counts"]["unknown"] == len(load_controls())
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["receipt"]["sha256"]


def test_check_all_yes_is_ready(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    answers.write_text(
        "\n".join(f'{c.id}: "yes"' for c in load_controls()) + "\n",
        encoding="utf-8",
    )
    code = main(["check", "--answers", str(answers), "--out", str(tmp_path)])
    assert code == EXIT_OK
    assert "READY_FOR_STAGE1_AUDIT" in capsys.readouterr().out


def test_check_invalid_answer_exits_1(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    answers.write_text('ISO42001-A2-01: "definitely"\n', encoding="utf-8")
    code = main(["check", "--answers", str(answers), "--out", str(tmp_path)])
    assert code == 1
    assert "error" in capsys.readouterr().err


def test_check_unknown_control_id_exits_1(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    answers.write_text('ISO42001-TYPO-99: "yes"\n', encoding="utf-8")
    code = main(["check", "--answers", str(answers), "--out", str(tmp_path)])
    assert code == 1
    assert "unknown control ids" in capsys.readouterr().err


def test_list_groups_by_instrument_and_domain(capsys):
    code = main(["list"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "ISO/IEC 42001" in out
    assert "Article 50" in out
    assert DISCLAIMER in out
    for c in load_controls():
        assert c.id in out


def test_list_json_mode(capsys):
    code = main(["list", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["instruments"]) == {"ISO42001", "AIACT-A50"}
    total = sum(len(v) for v in payload["instruments"].values())
    assert total == len(load_controls())


# ---------------------------------------------------------------------------
# Subprocess smoke tests — the real user contract
# ---------------------------------------------------------------------------

def test_module_help_works():
    proc = run_module("--help")
    assert proc.returncode == 0
    assert "list" in proc.stdout and "check" in proc.stdout
    # The epilog carries the honesty disclaimer; argparse wraps long lines, so
    # compare with whitespace normalized.
    assert DISCLAIMER in " ".join(proc.stdout.split())


def test_module_version_works():
    proc = run_module("--version")
    assert proc.returncode == 0
    assert __version__ in proc.stdout


def test_module_list_smoke():
    proc = run_module("list")
    assert proc.returncode == 0
    assert "ISO42001-A2-01" in proc.stdout
    assert "AIACT-A50-06" in proc.stdout


def test_module_check_smoke_end_to_end(tmp_path):
    answers = tmp_path / "answers.yaml"
    out_dir = tmp_path / "out"

    # First run: template generation path, exit 2.
    first = run_module("check", "--answers", str(answers), "--out", str(out_dir))
    assert first.returncode == 2
    assert answers.exists()

    # Second run on the untouched template: honest NOT_READY, exit 0.
    second = run_module("check", "--answers", str(answers), "--out", str(out_dir))
    assert second.returncode == 0
    assert "NOT_READY" in second.stdout
    assert (out_dir / "readiness-report.md").exists()
    assert list(out_dir.glob("readiness-receipt*"))


def test_module_check_missing_answers_arg_fails_parse():
    proc = run_module("check")
    assert proc.returncode != 0
    assert "answers" in proc.stderr


def test_no_command_fails_parse():
    proc = run_module()
    assert proc.returncode != 0
