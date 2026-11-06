"""Regression contract for the estate-wide forbidden-domain workflow template.

The gate is release-blocking, so the template must (a) scan with a tool that
every GitHub-hosted Ubuntu runner ships, (b) never turn a scanner error into a
clean result, and (c) apply exactly the rule the Python engine applies
(``szl_alignment.const``). The earlier template piped ``rg`` through
``|| true``; ripgrep is not installed on the runners, so every run logged
``rg: command not found`` and then printed "OK". The behavioural tests below
execute the template's own scan script, extracted from the YAML, against
throwaway trees.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # noqa: S404 — fixed-argv bash invocation of the template script
from pathlib import Path

import pytest

from szl_alignment.const import ALLOWLIST_PATTERN, FORBIDDEN_PATTERN

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "templates" / "workflows" / "forbidden-domain.yml"
)
STEP_NAME = "Scan for forbidden domain references"
BASH = shutil.which("bash")
GREP = shutil.which("grep")


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _scan_script() -> str:
    """Return the literal ``run: |`` block of the scan step, dedented."""
    lines = _template().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {STEP_NAME}")
    run_at = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body: list[str] = []
    indent: int | None = None
    for line in lines[run_at + 1 :]:
        if not line.strip():
            body.append("")
            continue
        current = len(line) - len(line.lstrip(" "))
        if indent is None:
            indent = current
        if current < indent:
            break
        body.append(line[indent:])
    return "\n".join(body).rstrip() + "\n"


def _gnu_grep_with_pcre() -> bool:
    if BASH is None or GREP is None:
        return False
    probe = subprocess.run(  # noqa: S603
        [GREP, "-qP", r"(?<!-)a11oy\.com", "-"],
        input="https://a11oy.com\n",
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


needs_gnu_grep = pytest.mark.skipif(
    not _gnu_grep_with_pcre(),
    reason="needs bash and GNU grep with -P (PCRE), as on GitHub-hosted Ubuntu runners",
)


def _run_gate(tmp_path: Path, files: dict[str, bytes], path_env: str | None = None):
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel, data in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    script = tmp_path / "gate.sh"  # outside the scanned tree
    script.write_text(_scan_script(), encoding="utf-8")
    env = dict(os.environ)
    if path_env is not None:
        env["PATH"] = path_env
    return subprocess.run(  # noqa: S603
        [BASH, str(script)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",  # a reported line may carry the non-UTF-8 bytes it matched
        check=False,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# static contract
# ---------------------------------------------------------------------------


def test_template_rule_mirrors_engine_constants() -> None:
    script = _scan_script()
    pattern = re.search(r"grep -rnIP --exclude-dir=\.git '([^']+)' \.", script)
    guards = re.search(r"grep -viE '([^']+)'", script)
    assert pattern is not None and guards is not None
    assert pattern.group(1) == FORBIDDEN_PATTERN
    assert guards.group(1) == ALLOWLIST_PATTERN


def test_template_never_masks_scanner_errors() -> None:
    script = _scan_script()
    assert "|| true" not in script
    assert "set +e" not in script
    assert not re.search(r"(^|[\s|(])rg\s", script), "ripgrep is not on the hosted runners"
    assert "continue-on-error" not in _template()
    assert script.count('if [ "$status" -gt 1 ]; then') == 2
    assert script.count("refusing to report clean") == 2


def test_template_is_least_privilege_and_sha_pinned() -> None:
    workflow = _template()
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    uses = re.findall(r"uses:\s*(\S+)", workflow)
    assert uses, "the scan needs a checkout"
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), ref


# ---------------------------------------------------------------------------
# behaviour: run the template's own script
# ---------------------------------------------------------------------------


@needs_gnu_grep
def test_gate_passes_a_clean_tree(tmp_path: Path) -> None:
    proc = _run_gate(
        tmp_path,
        {
            "README.md": b"Product: https://a-11-oy.com  Proof: https://a11oy.net\n",
            "src/app.py": b'print("hello")\n',
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: no forbidden domain references" in proc.stdout


@needs_gnu_grep
def test_gate_fails_on_a_true_violation(tmp_path: Path) -> None:
    proc = _run_gate(
        tmp_path,
        {
            "docs/links.md": b"Visit https://a11oy.com/docs\n",
            "notes.md": b"# never link a11oy.com\n",
        },
    )
    assert proc.returncode == 1
    assert "::error::Forbidden domain references found" in proc.stdout
    assert "docs/links.md:1:" in proc.stdout
    assert "notes.md" not in proc.stdout  # the guard line is not reported
    assert "OK:" not in proc.stdout


@needs_gnu_grep
def test_gate_allows_guard_contexts_and_documented_disavowals(tmp_path: Path) -> None:
    proc = _run_gate(
        tmp_path,
        {
            "a.md": b"a11oy.com is not a surface of this project.\n",
            "b.py": b'assert "a11oy.com" not in text\n',
            "c.md": b"SZL is not affiliated with a11oy.com.\n",
            "d.md": b"Do not treat a11oy.com as canonical.\n",
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: no forbidden domain references" in proc.stdout


@needs_gnu_grep
def test_gate_scans_hidden_dirs_and_non_utf8_files_but_not_git(tmp_path: Path) -> None:
    proc = _run_gate(
        tmp_path,
        {
            ".git/config": b"url = https://a11oy.com/x\n",
            ".github/workflows/deploy.yml": b"url: https://a11oy.com/deploy\n",
            "legacy.txt": b"caf\xe9 \xff https://a11oy.com/latin1\n",
        },
    )
    assert proc.returncode == 1
    assert ".github/workflows/deploy.yml:1:" in proc.stdout
    assert "legacy.txt:1:" in proc.stdout
    assert ".git/config" not in proc.stdout


@needs_gnu_grep
def test_gate_fails_closed_when_the_scanner_errors(tmp_path: Path) -> None:
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    stub = stub_dir / "grep"
    stub.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    stub.chmod(0o755)
    proc = _run_gate(
        tmp_path,
        {"README.md": b"clean\n"},
        path_env=f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    )
    assert proc.returncode == 2
    assert "refusing to report clean" in proc.stdout
    assert "OK:" not in proc.stdout


@needs_gnu_grep
def test_gate_fails_closed_when_the_scanner_is_missing(tmp_path: Path) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    proc = _run_gate(tmp_path, {"README.md": b"clean\n"}, path_env=str(empty_bin))
    assert proc.returncode != 0
    assert "refusing to report clean" in proc.stdout
    assert "OK:" not in proc.stdout
