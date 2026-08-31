"""Tests for szl_alignment.report — scores, matrix.csv, ALIGNMENT_REPORT.md."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from szl_alignment.inspect import inspect_repo
from szl_alignment.report import (
    org_totals,
    render_org_report,
    score_repo,
    totals_line,
)


def test_score_complete_repo(complete_repo: Path) -> None:
    # non-Python repo with everything present except the base Python gate ->
    # that 5-point line is granted entirely to non-Python repos by design.
    assert score_repo(inspect_repo(complete_repo)) == 100


def test_score_bare_repo_is_low(bare_repo: Path) -> None:
    # bare repo: README(10) + non-Python base-CI credit(5) + zero true
    # violations(10) = 25
    assert score_repo(inspect_repo(bare_repo)) == 25


def test_score_penalizes_true_violations(command_lab_repo: Path) -> None:
    report = inspect_repo(command_lab_repo)
    assert len(report.true_violations) >= 2
    before = score_repo(report)
    report.forbidden_scan.violations.clear()
    assert score_repo(report) == before + 10  # the violations cost exactly 10


def test_render_org_report_returns_both_artifacts(command_lab_repo, bare_repo: Path) -> None:
    reports = [inspect_repo(command_lab_repo), inspect_repo(bare_repo)]
    md, csv_text = render_org_report(reports)
    assert "# SZL Holdings — Alignment Report" in md
    assert "## TRUE FORBIDDEN VIOLATIONS" in md
    assert "src/lib/publish.ts:37" in md  # file:line format, per the spec
    assert "src/lib/publish.ts:41" in md
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 2
    by_name = {r["repo"]: r for r in rows}
    assert by_name["szl-command-lab"]["true_forbidden_violations"] == "4"
    assert by_name["szl-command-lab"]["guard_mentions"] == "2"
    assert by_name["bare-repo"]["license_kind"] == "NONE"


def test_csv_is_parseable_and_sorted(command_lab_repo, bare_repo: Path) -> None:
    reports = [inspect_repo(command_lab_repo), inspect_repo(bare_repo)]
    _, csv_text = render_org_report(reports)
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[0][0] == "repo"  # header row
    names = [r[0] for r in rows[1:]]
    assert names == sorted(names, key=str.lower)


def test_org_totals_and_line(command_lab_repo, bare_repo, complete_repo: Path) -> None:
    reports = [inspect_repo(r) for r in (command_lab_repo, bare_repo, complete_repo)]
    t = org_totals(reports)
    assert t.repos == 3
    assert t.total_true_violations == 4
    assert t.repos_with_violations == 1
    assert 0.0 < t.mean_score <= 100.0
    line = totals_line(reports)
    assert "3 repos scored" in line
    assert "4 true forbidden violations" in line
    assert "mean score" in line


def test_szl_command_lab_fixture_exact_violations(command_lab_repo: Path) -> None:
    """The fixture mirrors the live finding: exactly 2 true violations in publish.ts."""
    report = inspect_repo(command_lab_repo)
    publish = [v for v in report.true_violations if v.file == "src/lib/publish.ts"]
    assert len(publish) == 2
    texts = "\n".join(v.text for v in publish)
    assert 'host: "a11oy.com",' in texts
    assert 'href: "https://a11oy.com",' in texts
