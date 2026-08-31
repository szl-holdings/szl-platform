"""Offline tests for the two-source enumeration.

Fabricated sources are injected for both the CLI (monkeypatched subprocess)
and REST (injected transport/monkeypatched fetch), so nothing touches a
network or a real gh binary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from conftest import make_repo
from szl_estate import enumerate as en


class _Completed:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _good_cli(records: list[dict]):
    def fake_run(cmd, capture_output, text, timeout):  # noqa: ANN001, ANN202
        return _Completed(stdout=json.dumps(records))

    return fake_run


def _test_rest(records: list[dict]):
    """Fabricate Source B by monkeypatching the REST fetcher itself."""

    def fake_source_b(org, *, token=None, transport=None, max_pages=50):  # noqa: ANN001, ANN202
        return records

    return fake_source_b


def test_two_agreeing_sources_are_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    records = [make_repo("alpha"), make_repo("beta"), make_repo("gamma")]
    monkeypatch.setattr(en.subprocess, "run", _good_cli(records))
    monkeypatch.setattr(en, "enumerate_source_b", _test_rest(records))

    evidence = en.enumerate_org("szl-holdings", out=tmp_path)

    assert evidence.status == "COMPLETE"
    assert evidence.agreement is True
    assert evidence.repo_count == 3  # computed from the agreeing sets
    repos_yaml = yaml.safe_load((tmp_path / "repos.yaml").read_text())
    assert [r["name"] for r in repos_yaml] == ["alpha", "beta", "gamma"]
    assert repos_yaml[0]["license_spdx"] == "apache-2.0"
    written = json.loads((tmp_path / "enumeration.json").read_text())
    assert written["status"] == "COMPLETE"
    assert written["sources"]["source_a"]["ok"] is True
    assert written["sources"]["source_b"]["ok"] is True


def test_disagreement_is_partial_with_exact_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records_a = [make_repo("alpha"), make_repo("beta")]
    records_b = [make_repo("beta"), make_repo("gamma")]
    monkeypatch.setattr(en.subprocess, "run", _good_cli(records_a))
    monkeypatch.setattr(en, "enumerate_source_b", _test_rest(records_b))

    evidence = en.enumerate_org("szl-holdings", out=tmp_path)

    assert evidence.status == "PARTIAL"
    assert evidence.agreement is False
    assert evidence.repo_count is None  # doctrine: no total we did not compute
    assert evidence.missing_in_b == ["alpha"]
    assert evidence.missing_in_a == ["gamma"]

    text = en.format_human(evidence)
    # PARTIAL must print BOTH observed counts and the diff, never a single count.
    assert "observed 2 repos" in text
    assert "alpha" in text and "gamma" in text
    assert "3 repos confirmed" not in text


def test_cli_rate_limit_error_is_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    records = [make_repo("alpha")]

    def rate_limited(cmd, capture_output, text, timeout):  # noqa: ANN001, ANN202
        return _Completed(returncode=1, stderr="gh: API rate limit exceeded (HTTP 403)")

    monkeypatch.setattr(en.subprocess, "run", rate_limited)
    monkeypatch.setattr(en, "enumerate_source_b", _test_rest(records))

    evidence = en.enumerate_org("szl-holdings", out=tmp_path)

    assert evidence.status == "PARTIAL"
    assert evidence.sources["source_a"].ok is False
    assert "rate limit" in (evidence.sources["source_a"].error or "").lower()
    assert evidence.sources["source_b"].ok is True


def test_rest_rate_limit_error_is_named_and_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = [make_repo("alpha")]
    monkeypatch.setattr(en.subprocess, "run", _good_cli(records))

    def rate_limited_rest(org, *, token=None, transport=None, max_pages=50):  # noqa: ANN001, ANN202
        raise en.EnumerationError("source B (REST): HTTP 403 'API rate limit exceeded' on page 1")

    monkeypatch.setattr(en, "enumerate_source_b", rate_limited_rest)

    evidence = en.enumerate_org("szl-holdings", out=tmp_path)

    assert evidence.status == "PARTIAL"
    src_b = evidence.sources["source_b"]
    assert src_b.ok is False
    assert "API rate limit exceeded" in (src_b.error or "")


def test_offline_mode_replays_fixture_and_is_complete(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "gh_repo_list.json"
    evidence = en.enumerate_org("szl-holdings", out=tmp_path, offline=True, fixture=fixture)

    assert evidence.status == "COMPLETE"
    assert evidence.offline is True
    # 100 repos in the real 2026-08-31 capture — a count read back from the
    # fixture this test just used, not an asserted constant.
    expected = len(json.loads(fixture.read_text()))
    assert evidence.repo_count == expected
    repos_yaml = yaml.safe_load((tmp_path / "repos.yaml").read_text())
    assert len(repos_yaml) == expected
    names = [r["name"] for r in repos_yaml]
    assert names == sorted(names), "repos.yaml must be sorted"


def test_offline_missing_fixture_is_partial_not_a_lie(tmp_path: Path) -> None:
    evidence = en.enumerate_org(
        "szl-holdings", out=tmp_path, offline=True, fixture=tmp_path / "nope.json"
    )
    assert evidence.status == "PARTIAL"
    assert evidence.repo_count is None
    assert evidence.sources["source_a"].ok is False


def test_source_b_pagination_and_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """REST source must paginate until a short page and must send the token."""
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload, text: str = "") -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = text or json.dumps(payload)

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *, timeout, headers, transport=None):  # noqa: ANN001
            calls.append({"headers": dict(headers)})

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, params=None):  # noqa: ANN001, ANN202
            page = int(params["page"])
            calls[-1][f"page{page}"] = url
            if page == 1:
                return FakeResponse(200, [{"name": f"r{i}"} for i in range(100)])
            return FakeResponse(200, [{"name": "r100"}])  # short page: stop

    monkeypatch.setattr(en.httpx, "Client", FakeClient)
    repos = en.enumerate_source_b("szl-holdings", token="ghp_test")  # noqa: S106 — fabricated test token
    assert len(repos) == 101
    assert calls[0]["headers"]["Authorization"] == "Bearer ghp_test"


def test_source_b_real_rate_limit_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 403
        text = '{"message": "API rate limit exceeded for user ID 1"}'

        def json(self):
            return {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr(en.httpx, "Client", FakeClient)
    with pytest.raises(en.EnumerationError, match="API rate limit exceeded"):
        en.enumerate_source_b("szl-holdings", token="ghp_test")  # noqa: S106 — inert test token
