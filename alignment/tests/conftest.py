"""Shared pytest fixtures: tmp_path repo builders and a git helper.

Every builder returns a ``pathlib.Path`` to a fresh repo under ``tmp_path`` —
no network, no shared state, no reliance on the real org mirror. The git
fixture runs real ``git init`` so apply tests exercise true plumbing.
"""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404 — git plumbing in tests is fixed-argv, no shell
from pathlib import Path

import pytest

from szl_alignment.plan import template_text

FIXTURES_DIR = Path(__file__).parent / "fixtures"
COMMAND_LAB_FIXTURE = FIXTURES_DIR / "szl-command-lab"

GIT_AVAILABLE = shutil.which("git") is not None


def _write(root: Path, files: dict[str, str]) -> Path:
    """Materialize a dict of {relative_path: content} under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def bare_repo(tmp_path: Path) -> Path:
    """A repo missing everything: one README, nothing else."""
    return _write(tmp_path / "bare-repo", {"README.md": "# bare-repo\n\nNothing else yet.\n"})


@pytest.fixture
def complete_repo(tmp_path: Path) -> Path:
    """A fully aligned repo: doctrine header, governance files, both gates."""
    header = template_text("README_HEADER.md")
    return _write(
        tmp_path / "complete-repo",
        {
            "README.md": (
                "# complete-repo\n\n"
                "Some existing intro text the header must not clobber.\n\n"
                f"{header}\n"
            ),
            "LICENSE": "Apache License\nVersion 2.0, January 2004\n",
            "SECURITY.md": "# Security Policy\n",
            "CONTRIBUTING.md": "# Contributing\n",
            "CODE_OF_CONDUCT.md": "# Code of Conduct\n",
            ".github/PULL_REQUEST_TEMPLATE.md": "## Checklist\n",
            ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Bug report\n",
            ".github/ISSUE_TEMPLATE/config.yml": "blank_issues_enabled: false\n",
            ".github/workflows/forbidden-domain.yml": "name: forbidden-domain\n",
        },
    )


@pytest.fixture
def python_repo(tmp_path: Path) -> Path:
    """Python detected (pyproject + .py), some CI but not the base gate."""
    return _write(
        tmp_path / "python-repo",
        {
            "README.md": "# python-repo\n",
            "pyproject.toml": "[project]\nname = 'python-repo'\n",
            "src/mod.py": "def f() -> int:\n    return 1\n",
            ".github/workflows/existing.yml": "name: existing\n",
        },
    )


@pytest.fixture
def command_lab_repo(tmp_path: Path) -> Path:
    """Copy of the szl-command-lab fixture (true forbidden violations)."""
    dest = tmp_path / "szl-command-lab"
    shutil.copytree(COMMAND_LAB_FIXTURE, dest)
    return dest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A real ``git init`` repo with one commit — for apply tests."""
    repo = _write(tmp_path / "git-repo", {"README.md": "# git-repo\n\nBody.\n"})
    subprocess.run(  # noqa: S603
        ["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True,
    )
    subprocess.run(  # noqa: S603
        ["git", "add", "-A"], cwd=repo, check=True, capture_output=True, text=True,
    )
    subprocess.run(  # noqa: S603
        [
            "git",
            "-c", "user.name=test", "-c", "user.email=test@example.com",
            "commit", "-m", "initial",
        ],
        cwd=repo, check=True, capture_output=True, text=True,
    )
    return repo
