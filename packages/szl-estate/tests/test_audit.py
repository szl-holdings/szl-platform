"""Offline tests for per-repo audit: rendering, rollups, UNKNOWN honesty, and
the forbidden-link regex that guards the estate's real front doors."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from conftest import FakeProc, make_repo
from szl_estate import BLOCKERS_HEADER, FORBIDDEN_LINK_RE, audit
from szl_estate.audit import RepoMetadata

FIXTURE = Path(__file__).parent / "fixtures" / "gh_repo_list.json"
# Deterministic "now" so STALE/ACTIVE classification never flakes: the fixture
# capture was taken 2026-08-31, so a clock one day later keeps pushes ACTIVE.
NOW = datetime(2026, 9, 1, tzinfo=UTC)


class TestForbiddenLinkRegex:
    """The doctrine regex, unit-tested against its exact acceptance criteria."""

    @pytest.mark.parametrize(
        "text",
        [
            "https://a11oy.com/x",
            "a11oy.com",
            "visit www.a11oy.com today",
            "redirect: a11oy.com?utm=x",
        ],
    )
    def test_forbidden_strings_match(self, text: str) -> None:
        assert FORBIDDEN_LINK_RE.search(text), f"must match: {text}"

    @pytest.mark.parametrize(
        "text",
        [
            "a-11-oy.com",  # the real product origin — must never match
            "xa11oy.com",  # a different domain sharing the suffix
            "ba11oy.com",  # any word-char prefix is a different domain
            "a11oy.net",  # the proof origin — different TLD
            "https://a-11-oy.com/docs",
            "subdomain.a11oy.net",
        ],
    )
    def test_allowed_strings_do_not_match(self, text: str) -> None:
        assert not FORBIDDEN_LINK_RE.search(text), f"must NOT match: {text}"


class TestAuditRendering:
    def test_one_file_per_repo_and_matrix_rows(self, tmp_path: Path) -> None:
        audits = audit.audit_org(
            "szl-holdings", out=tmp_path, offline=True, fixture=FIXTURE, now=NOW
        )
        expected = len(json.loads(FIXTURE.read_text()))
        assert len(audits) == expected

        md_files = sorted((tmp_path / "repos").glob("*.md"))
        assert len(md_files) == expected, "one audit file per enumerated repo"
        assert (tmp_path / "repos" / "a11oy.md").exists()

        with (tmp_path / "REPOSITORY_MATRIX.csv").open() as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == expected, "CSV must have exactly N repo rows"
        assert list(rows[0].keys()) == list(audit.MATRIX_COLUMNS), "stable column order"

        summary = (tmp_path / "ESTATE_SUMMARY.md").read_text()
        assert BLOCKERS_HEADER in summary
        # The blockers header is the FIRST section header of the report.
        first_header = next(line for line in summary.splitlines() if line.startswith("## "))
        assert first_header == f"## {BLOCKERS_HEADER}"

    def test_offline_probes_are_unknown_never_zero(self, tmp_path: Path) -> None:
        audits = audit.audit_org(
            "szl-holdings", out=tmp_path, offline=True, fixture=FIXTURE, now=NOW
        )
        for a in audits:
            assert a.probes["open_prs"].value is None
            assert "not attempted in offline mode" in (a.probes["open_prs"].error or "")
            assert a.probes["ci_latest"].value is None
            assert a.probes["forbidden_link"].value is None
        with (tmp_path / "REPOSITORY_MATRIX.csv").open() as fh:
            rows = list(csv.DictReader(fh))
        assert all(r["open_prs"] == "UNKNOWN" for r in rows)
        assert all(r["ci_latest"] == "UNKNOWN" for r in rows)

    def test_repos_yaml_is_sorted(self, tmp_path: Path) -> None:
        audit.audit_org("szl-holdings", out=tmp_path, offline=True, fixture=FIXTURE, now=NOW)
        names = [r["name"] for r in yaml.safe_load((tmp_path / "repos.yaml").read_text())]
        assert names == sorted(names)


class TestUnknownPropagation:
    """When a probe raises, the audit records UNKNOWN + the error — never 0."""

    def _repo(self) -> RepoMetadata:
        return RepoMetadata.model_validate(
            {
                "name": "demo",
                "visibility": "PUBLIC",
                "is_private": False,
                "is_archived": False,
                "is_empty": False,
                "description": "d",
                "primary_language": "Python",
                "license_spdx": "apache-2.0",
                "default_branch": "main",
                "pushed_at": "2026-08-30T00:00:00Z",
                "stargazer_count": 0,
                "url": "https://github.com/szl-holdings/demo",
            }
        )

    def test_probe_exception_becomes_unknown_with_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(cmd):  # noqa: ANN001, ANN202
            raise subprocess.TimeoutExpired(cmd, 60)

        monkeypatch.setattr(audit, "_run_gh", boom)
        result = audit.audit_repo("szl-holdings", self._repo(), now=NOW)
        assert result.probes["open_prs"].value is None
        assert "could not run" in (result.probes["open_prs"].error or "")
        assert result.probes["ci_latest"].value is None
        assert result.probes["forbidden_link"].value is None
        # Findings must surface the UNKNOWNs, not swallow them.
        codes = {f.code for f in result.findings}
        assert "README_PROBE_UNKNOWN" in codes
        assert "CI_PROBE_UNKNOWN" in codes
        assert "PR_COUNT_UNKNOWN" in codes

    def test_nonzero_exit_never_becomes_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail(cmd):  # noqa: ANN001, ANN202
            return FakeProc(returncode=1, stderr="HTTP 403: API rate limit exceeded")

        monkeypatch.setattr(audit, "_run_gh", fail)
        result = audit.audit_repo("szl-holdings", self._repo(), now=NOW)
        assert result.probes["open_prs"].value is None
        assert result.probes["open_prs"].value != 0  # the failure must not launder into 0
        assert "rate limit" in (result.probes["open_prs"].error or "").lower()

    def test_forbidden_link_finding_is_critical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def routing(cmd):  # noqa: ANN001, ANN202
            joined = " ".join(cmd)
            if "pr" in cmd:
                return FakeProc(stdout="[]")
            if "run" in cmd:
                return FakeProc(stdout='[{"conclusion": "success", "createdAt": "2026-08-30"}]')
            if "readme" in joined:
                return FakeProc(stdout="# demo\nSee https://a11oy.com/x for details\n")
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(audit, "_run_gh", routing)
        result = audit.audit_repo("szl-holdings", self._repo(), now=NOW)
        assert result.probes["forbidden_link"].value == "FORBIDDEN_LINK"
        critical = [f for f in result.findings if f.severity == "CRITICAL"]
        assert len(critical) == 1
        assert critical[0].code == "FORBIDDEN_LINK"
        # A clean probe result must still render in the per-repo markdown.
        rendered = audit._render_repo_audit(result)
        assert "FORBIDDEN_LINK" in rendered
        assert "CRITICAL" in rendered

    def test_open_prs_count_is_computed_from_parsed_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def routing(cmd):  # noqa: ANN001, ANN202
            if "pr" in cmd:
                return FakeProc(stdout=json.dumps([{"number": 1}, {"number": 2}, {"number": 3}]))
            return FakeProc(returncode=1, stderr="boom")

        monkeypatch.setattr(audit, "_run_gh", routing)
        result = audit.audit_repo("szl-holdings", self._repo(), now=NOW)
        assert result.probes["open_prs"].value == 3


class TestStateComputation:
    def _repo(self, **overrides) -> RepoMetadata:
        base = {"name": "demo", "pushed_at": "2026-08-30T00:00:00Z"}
        base.update(overrides)
        return RepoMetadata.model_validate(base)

    def test_archived_wins(self) -> None:
        assert audit.compute_state(self._repo(is_archived=True)) == "ARCHIVED"

    def test_empty(self) -> None:
        assert audit.compute_state(self._repo(is_empty=True)) == "EMPTY"

    def test_missing_push_date_is_unknown_not_fresh(self) -> None:
        assert audit.compute_state(self._repo(pushed_at=None)) == "UNKNOWN"

    def test_unparseable_push_date_is_unknown(self) -> None:
        assert audit.compute_state(self._repo(pushed_at="not-a-date")) == "UNKNOWN"

    def test_stale_after_threshold(self) -> None:
        assert audit.compute_state(self._repo(pushed_at="2025-01-01T00:00:00Z"), now=NOW) == "STALE"

    def test_active(self) -> None:
        assert audit.compute_state(self._repo(), now=NOW) == "ACTIVE"


def test_fixture_replay_uses_real_capture(tmp_path: Path) -> None:
    """The audit consumes exactly what enumerate wrote from the fixture."""
    audits = audit.audit_org("szl-holdings", out=tmp_path, offline=True, fixture=FIXTURE, now=NOW)
    by_name = {a.repo.name: a for a in audits}
    assert "a11oy" in by_name
    assert by_name["a11oy"].repo.primary_language == "Python"
    assert by_name["a11oy"].repo.license_spdx == "apache-2.0"


def test_summary_lists_critical_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A CRITICAL finding must appear under the blockers header, above HIGH."""

    def routing(cmd):  # noqa: ANN001, ANN202
        joined = " ".join(cmd)
        if "pr" in cmd:
            return FakeProc(stdout="[]")
        if "run" in cmd:
            return FakeProc(stdout='[{"conclusion": "failure", "createdAt": "2026-08-30"}]')
        if "readme" in joined and "/bad/" in joined:
            return FakeProc(stdout="go to a11oy.com now")
        if "readme" in joined:
            return FakeProc(stdout="clean readme")
        raise AssertionError(cmd)

    records = [
        make_repo("bad", url="https://github.com/szl-holdings/bad"),
        make_repo("good"),
    ]
    fixture = tmp_path / "fx.json"
    fixture.write_text(json.dumps(records))
    monkeypatch.setattr(audit, "_run_gh", routing)
    out = tmp_path / "o"
    # Seed the enumeration artifact offline, then let audit run its live
    # probes (faked above) against the seeded inventory.
    from szl_estate import enumerate as en

    en.enumerate_org("szl-holdings", out=out, offline=True, fixture=fixture)
    audits = audit.audit_org("szl-holdings", out=out, now=NOW)
    by_name = {a.repo.name: a for a in audits}
    assert by_name["bad"].findings[0].code == "FORBIDDEN_LINK"
    assert by_name["bad"].findings[0].severity == "CRITICAL"
    assert any(f.code == "CI_FAILING" and f.severity == "HIGH" for f in by_name["good"].findings)

    summary = (tmp_path / "o" / "ESTATE_SUMMARY.md").read_text()
    blocker_section = summary.split(BLOCKERS_HEADER, 1)[1]
    assert blocker_section.index("CRITICAL") < blocker_section.index("CI_FAILING")
