"""Tests for szl_alignment.cli — every subcommand, --help, exit codes."""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404 — fixed-argv module invocation
import sys
from pathlib import Path

import pytest
from conftest import GIT_AVAILABLE

from szl_alignment.cli import build_parser, main

# The suite runs without installation (pyproject sets pythonpath=["src"]), but
# subprocesses need PYTHONPATH spelled out explicitly.
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _run(argv: list[str]) -> tuple[int, str, str]:
    """Invoke the CLI as a real subprocess (python -m szl_alignment)."""
    env = dict(os.environ, PYTHONPATH=str(_SRC_DIR))
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "szl_alignment", *argv],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_root_help() -> None:
    code, out, _ = _run(["--help"])
    assert code == 0
    for word in ("inspect", "plan", "apply", "org-report"):
        assert word in out


@pytest.mark.parametrize("cmd", ["inspect", "plan", "apply", "org-report"])
def test_subcommand_help(cmd: str) -> None:
    code, out, _ = _run([cmd, "--help"])
    assert code == 0
    assert "usage:" in out


def test_no_args_is_usage_error() -> None:
    code, _, err = _run([])
    assert code == 2
    assert "usage:" in err


def test_inspect_plain(bare_repo: Path) -> None:
    code, out, _ = _run(["inspect", str(bare_repo)])
    assert code == 0
    assert "bare-repo" in out
    assert "license:" in out


def test_inspect_json(bare_repo: Path) -> None:
    code, out, _ = _run(["inspect", "--json", str(bare_repo)])
    assert code == 0
    data = json.loads(out)
    assert data["name"] == "bare-repo"
    assert data["has_security"] is False
    assert "score" in data


def test_plan_plain(bare_repo: Path) -> None:
    code, out, _ = _run(["plan", str(bare_repo)])
    assert code == 0
    assert "action(s)" in out
    assert "SECURITY.md" in out


def test_plan_json_complete_repo(complete_repo: Path) -> None:
    code, out, _ = _run(["plan", "--json", str(complete_repo)])
    assert code == 0
    assert json.loads(out) == []


def test_apply_dry_run_default(git_repo: Path) -> None:
    code, out, _ = _run(["apply", str(git_repo)])
    assert code == 0
    assert "DRY-RUN" in out
    # dry-run must not have created files
    assert not (git_repo / "SECURITY.md").exists()


def test_apply_json(git_repo: Path) -> None:
    code, out, _ = _run(["apply", "--json", str(git_repo)])
    assert code == 0
    data = json.loads(out)
    assert data["dry_run"] is True
    assert isinstance(data["items"], list)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git not on PATH")
def test_apply_real_on_git_repo(git_repo: Path) -> None:
    code, out, _ = _run(["apply", "--apply", str(git_repo)])
    assert code == 0
    assert "APPLIED" in out
    assert (git_repo / "SECURITY.md").is_file()


def test_apply_already_aligned(complete_repo: Path) -> None:
    code, out, _ = _run(["apply", str(complete_repo)])
    assert code == 0
    assert "fully aligned" in out


def test_org_report_writes_both_files(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    for name in ("alpha", "beta"):
        (mirror / name).mkdir(parents=True)
        (mirror / name / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    code, out, err = _run(["org-report", str(mirror), "--out", str(out_dir)])
    assert code == 0, err
    assert (out_dir / "ALIGNMENT_REPORT.md").is_file()
    assert (out_dir / "matrix.csv").is_file()
    assert "2 repos scored" in out
    assert "mean score" in out
    assert "true forbidden violations" in out
    report_md = (out_dir / "ALIGNMENT_REPORT.md").read_text(encoding="utf-8")
    assert "## TRUE FORBIDDEN VIOLATIONS" in report_md
    assert "alpha" in (out_dir / "matrix.csv").read_text(encoding="utf-8")


def test_org_report_rejects_missing_mirror(tmp_path: Path) -> None:
    code, _, err = _run(["org-report", str(tmp_path / "nope"), "--out", str(tmp_path / "o")])
    assert code == 2
    assert "not a directory" in err


def test_build_parser_directly() -> None:
    parser = build_parser()
    args = parser.parse_args(["inspect", "/nonexistent/x"])
    assert args.command == "inspect"
    args = parser.parse_args(["apply", "/nonexistent/x", "--apply", "--branch", "szl/custom"])
    assert args.apply is True
    assert args.branch == "szl/custom"


def test_main_returns_int(bare_repo: Path, capsys) -> None:
    assert main(["inspect", str(bare_repo)]) == 0
    capsys.readouterr()  # drain
