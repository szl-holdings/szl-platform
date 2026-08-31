"""Shared fixtures for the szl-estate suite.

Everything here is offline: network surfaces are replaced with
httpx.MockTransport or injected callables, and `gh` subprocess calls are
replaced with fake runners. No test may touch the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture()
def gh_repo_list() -> list[dict[str, Any]]:
    """The real 2026-08-31 capture of `gh repo list szl-holdings` (100 repos)."""
    return json.loads((FIXTURES / "gh_repo_list.json").read_text(encoding="utf-8"))


@pytest.fixture()
def gh_repo_records(gh_repo_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alias with a name that reads like the fixture's role in a test."""
    return gh_repo_list


def make_repo(name: str, **overrides: Any) -> dict[str, Any]:
    """Fabricate one repo record in the `gh repo list` JSON shape."""
    record: dict[str, Any] = {
        "name": name,
        "isPrivate": False,
        "isArchived": False,
        "isEmpty": False,
        "pushedAt": "2026-08-30T00:00:00Z",
        "defaultBranchRef": {"name": "main"},
        "description": f"repo {name}",
        "primaryLanguage": {"name": "Python"},
        "licenseInfo": {"key": "apache-2.0", "name": "Apache License 2.0"},
        "url": f"https://github.com/szl-holdings/{name}",
        "visibility": "PUBLIC",
        "stargazerCount": 0,
    }
    record.update(overrides)
    return record


class FakeProc:
    """A stand-in for subprocess.CompletedProcess for fake gh/systemctl runners."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
