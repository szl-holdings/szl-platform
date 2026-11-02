"""An open-PR count is known only after the entire bounded inventory completes."""

from __future__ import annotations

import json
import subprocess
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import FakeProc
from szl_estate import audit


def _pulls(first: int, last: int) -> list[dict]:
    return [{"number": number, "state": "open"} for number in range(first, last + 1)]


@pytest.mark.parametrize("count", [0, 1, 30, 31, 100, 101, 205])
def test_count_includes_every_page(monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    rows = _pulls(1, count)

    def fetch(cmd):
        # Reproduce the old gh pr list default limit, not an unlimited fake.
        if cmd[:3] == ["gh", "pr", "list"]:
            return FakeProc(stdout=json.dumps(rows[:30]))
        assert cmd[:2] == ["gh", "api"]
        endpoint = next(arg for arg in cmd if arg.startswith("repos/"))
        query = parse_qs(urlsplit(endpoint).query)
        assert query["state"] == ["open"]
        assert query["per_page"] == ["100"]
        page = int(query["page"][0])
        return FakeProc(stdout=json.dumps(rows[(page - 1) * 100 : page * 100]))

    monkeypatch.setattr(audit, "_run_gh", fetch)
    result = audit.probe_open_prs("szl-holdings", "demo")
    assert result.value == count
    assert result.error is None


@pytest.mark.parametrize("failure", ["exit", "timeout", "json", "shape", "duplicate"])
def test_partial_inventory_never_becomes_a_count(monkeypatch: pytest.MonkeyPatch, failure: str):
    calls = []

    def fetch(cmd):
        calls.append(cmd)
        if len(calls) == 1:
            return FakeProc(stdout=json.dumps(_pulls(1, 100)))
        if failure == "exit":
            return FakeProc(returncode=1, stderr="HTTP 403: rate limit")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(cmd, 60)
        if failure == "json":
            return FakeProc(stdout="[truncated")
        if failure == "shape":
            return FakeProc(stdout='{"message": "unavailable"}')
        return FakeProc(stdout=json.dumps(_pulls(100, 101)))

    monkeypatch.setattr(audit, "_run_gh", fetch)
    result = audit.probe_open_prs("szl-holdings", "demo")
    assert result.value is None
    assert result.error
    assert len(calls) == 2


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {"number": True, "state": "open"},
        {"number": -1, "state": "open"},
        {"number": "1", "state": "open"},
        {"number": 1, "state": "closed"},
    ],
)
def test_malformed_rows_are_unknown(monkeypatch: pytest.MonkeyPatch, row):
    monkeypatch.setattr(audit, "_run_gh", lambda cmd: FakeProc(stdout=json.dumps([row])))
    result = audit.probe_open_prs("szl-holdings", "demo")
    assert result.value is None
    assert result.error


def test_page_bound_is_unknown(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fetch(cmd):
        calls.append(cmd)
        start = (len(calls) - 1) * 100 + 1
        return FakeProc(stdout=json.dumps(_pulls(start, start + 99)))

    monkeypatch.setattr(audit, "MAX_PR_PAGES", 2, raising=False)
    monkeypatch.setattr(audit, "_run_gh", fetch)
    result = audit.probe_open_prs("szl-holdings", "demo")
    assert result.value is None
    assert "bound" in result.error
    assert len(calls) == 2
