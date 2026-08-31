"""Org-level reporting: many RepoReports -> one matrix + one markdown report.

Two artifacts, one source of truth:

- ``matrix.csv``            — machine-readable, one row per repo;
- ``ALIGNMENT_REPORT.md``   — human-readable: org totals, the explicit
  'TRUE FORBIDDEN VIOLATIONS' section (every violation with file:line), and
  the per-repo alignment matrix.

Both are pure string builders — the CLI decides where they land. Scoring is
defined here (``score_repo``) so tests can pin the formula and the numbers
mean the same thing everywhere.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from szl_alignment.const import (
    BASE_PYTHON_CI_PATH,
    FORBIDDEN_DOMAIN_PATH,
    LICENSE_NONE,
    LICENSE_UNKNOWN,
    __version__,
)
from szl_alignment.inspect import RepoReport

# ---------------------------------------------------------------------------
# scoring — 100 points across the one-standard checklist, weights in comments.
# Criteria are read straight off RepoReport fields so a score is auditable.
# ---------------------------------------------------------------------------

_BASE_CI_NAME = BASE_PYTHON_CI_PATH.rsplit("/", 1)[-1]
_FORBIDDEN_WF_NAME = FORBIDDEN_DOMAIN_PATH.rsplit("/", 1)[-1]


def score_repo(report: RepoReport) -> int:
    """Alignment score 0..100. UNKNOWN-flavored states score 0, never partial credit."""
    score = 0
    if report.has_readme:
        score += 10
    if report.has_license:
        score += 10  # any recognized-or-not license present; kind shows in the matrix
    if report.has_security:
        score += 15
    if report.has_contributing:
        score += 10
    if report.has_coc:
        score += 5
    if report.has_pr_template:
        score += 5
    if report.has_issue_templates:
        score += 5
    if report.ci_workflows:
        score += 10  # some CI at all
    if (not report.python_detected) or _BASE_CI_NAME in report.ci_workflows:
        score += 5  # the base python gate where python lives
    if _FORBIDDEN_WF_NAME in report.ci_workflows:
        score += 10  # the release-blocking gate itself
    if not report.true_violations and report.forbidden_scan.error is None:
        score += 10  # zero TRUE violations (and the scan actually ran)
    if report.doctrine_header_present or report.header_marker_present:
        score += 5
    return score


@dataclass
class OrgTotals:
    """The headline numbers for the whole estate."""

    repos: int
    mean_score: float
    total_true_violations: int
    repos_with_violations: int
    license_gaps: int  # NONE + UNKNOWN — advice only, never auto-written
    missing_security: int
    missing_contributing: int


def org_totals(reports: list[RepoReport]) -> OrgTotals:
    """Compute the headline numbers; pure."""
    n = len(reports)
    mean = sum(score_repo(r) for r in reports) / n if n else 0.0
    return OrgTotals(
        repos=n,
        mean_score=round(mean, 1),
        total_true_violations=sum(len(r.true_violations) for r in reports),
        repos_with_violations=sum(1 for r in reports if r.true_violations),
        license_gaps=sum(
            1 for r in reports if r.license_kind in {LICENSE_NONE, LICENSE_UNKNOWN}
        ),
        missing_security=sum(1 for r in reports if not r.has_security),
        missing_contributing=sum(1 for r in reports if not r.has_contributing),
    )


def totals_line(reports: list[RepoReport]) -> str:
    """One-line summary, printed by the CLI and embedded in the report."""
    t = org_totals(reports)
    return (
        f"org totals: {t.repos} repos scored, mean score {t.mean_score}%, "
        f"{t.total_true_violations} true forbidden violations across "
        f"{t.repos_with_violations} repo(s)"
    )


# ---------------------------------------------------------------------------
# matrix.csv
# ---------------------------------------------------------------------------

_CSV_FIELDS = [
    "repo",
    "license_kind",
    "license_file",
    "has_readme",
    "has_security",
    "has_contributing",
    "has_coc",
    "has_pr_template",
    "has_issue_templates",
    "ci_workflows",
    "python_detected",
    "typescript_detected",
    "true_forbidden_violations",
    "guard_mentions",
    "doctrine_header",
    "score_pct",
    "open_questions",
]


def render_matrix_csv(reports: list[RepoReport]) -> str:
    """One row per repo, sorted by name. Boolean cells render as true/false."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_FIELDS)
    for r in sorted(reports, key=lambda x: x.name.lower()):
        writer.writerow(
            [
                r.name,
                r.license_kind,
                r.license_file or "",
                str(r.has_readme).lower(),
                str(r.has_security).lower(),
                str(r.has_contributing).lower(),
                str(r.has_coc).lower(),
                str(r.has_pr_template).lower(),
                str(r.has_issue_templates).lower(),
                ";".join(r.ci_workflows),
                str(r.python_detected).lower(),
                str(r.typescript_detected).lower(),
                len(r.true_violations),
                r.forbidden_scan.guard_mentions,
                str(r.doctrine_header_present or r.header_marker_present).lower(),
                score_repo(r),
                " | ".join(r.open_questions),
            ]
        )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# ALIGNMENT_REPORT.md
# ---------------------------------------------------------------------------


def render_report_md(reports: list[RepoReport]) -> str:
    """The human report: doctrine, totals, TRUE FORBIDDEN VIOLATIONS, matrix."""
    t = org_totals(reports)
    ordered = sorted(reports, key=lambda x: x.name.lower())
    lines = [
        "# SZL Holdings — Alignment Report",
        "",
        "Generated by `szl-alignment` v" + __version__ + ".",
        "",
        "> Control before action. Evidence after.",
        "",
        "## Org totals",
        "",
        f"- Repos scored: **{t.repos}**",
        f"- Mean alignment score: **{t.mean_score}%**",
        f"- True forbidden-domain violations: **{t.total_true_violations}** "
        f"across {t.repos_with_violations} repo(s)",
        f"- Repos missing SECURITY.md: {t.missing_security}",
        f"- Repos missing CONTRIBUTING.md: {t.missing_contributing}",
        f"- License gaps (advice only — LICENSE is never auto-written): {t.license_gaps}",
        "",
        "## TRUE FORBIDDEN VIOLATIONS",
        "",
        "Rule: `(?<!-)a11oy\\.com` outside prohibition/guard contexts is "
        "release-blocking CRITICAL. Each entry below is `file:line — matched text`.",
        "",
    ]
    any_violations = False
    for r in ordered:
        if not r.true_violations:
            continue
        any_violations = True
        lines.append(f"### {r.name}")
        lines.append("")
        for v in sorted(r.true_violations, key=lambda x: (x.file, x.line)):
            lines.append(f"- `{v.file}:{v.line}` — {v.text}")
        lines.append("")
    if not any_violations:
        lines.append("None. (Guard-context mentions are allowed and counted in the matrix.)")
        lines.append("")

    lines += [
        "## Alignment matrix",
        "",
        "| Repo | License | README | SECURITY | CONTRIBUTING |"
        " CI | Gate | Header | Violations | Score |",
        "| ---- | ------- | ------ | -------- | ------------ |"
        " -- | ---- | ------ | ---------- | ----- |",
    ]
    for r in sorted(reports, key=lambda x: (-score_repo(x), x.name.lower())):
        header = _yesno(r.doctrine_header_present or r.header_marker_present)
        gate = _yesno(_FORBIDDEN_WF_NAME in r.ci_workflows)
        lines.append(
            f"| {r.name} | {r.license_kind} | {_yesno(r.has_readme)} | "
            f"{_yesno(r.has_security)} | {_yesno(r.has_contributing)} | "
            f"{len(r.ci_workflows)} | {gate} | {header} | "
            f"{len(r.true_violations)} | {score_repo(r)}% |"
        )
    lines += [
        "",
        "_Full machine-readable data: `matrix.csv` (same run, same numbers)._",
        "",
    ]
    return "\n".join(lines)


def _yesno(value: bool) -> str:
    return "yes" if value else "—"


def render_org_report(reports: list[RepoReport]) -> tuple[str, str]:
    """Return ``(ALIGNMENT_REPORT.md text, matrix.csv text)`` for the org."""
    return render_report_md(reports), render_matrix_csv(reports)


__all__ = [
    "OrgTotals",
    "org_totals",
    "render_matrix_csv",
    "render_org_report",
    "render_report_md",
    "score_repo",
    "totals_line",
]
