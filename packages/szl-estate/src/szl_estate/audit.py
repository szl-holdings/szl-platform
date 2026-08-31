"""Per-repo audit of the enumerated estate.

For every repo that :mod:`szl_estate.enumerate` confirmed (or honestly
marked PARTIAL), this module renders ``templates/REPO_AUDIT.j2`` to
``<out>/repos/<name>.md`` and rolls the whole org up into
``<out>/REPOSITORY_MATRIX.csv`` and ``<out>/ESTATE_SUMMARY.md``.

Doctrine encodings:

  * Every GitHub probe (open PR count, latest CI run, README forbidden-link
    scan) degrades to UNKNOWN with the error attached on ANY failure. A failed
    probe is never recorded as 0, never as a passing conclusion.
  * The forbidden-link scan uses the doctrine regex
    :data:`szl_estate.FORBIDDEN_LINK_RE`; a match is a CRITICAL finding with
    code FORBIDDEN_LINK.
  * The estate summary's top header is the literal line
    ``BLOCKERS THAT OUTRANK ALL COSMETIC WORK`` and lists CRITICAL findings
    first, then HIGH.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

from szl_estate import (
    BLOCKERS_HEADER,
    FORBIDDEN_LINK_CODE,
    FORBIDDEN_LINK_RE,
    SEVERITIES,
    STALE_DAYS,
)
from szl_estate.enumerate import EnumerationError, enumerate_org

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

#: Stable column order for REPOSITORY_MATRIX.csv. Investors diff this file
#: between runs; column order is therefore part of the contract.
MATRIX_COLUMNS: tuple[str, ...] = (
    "state",
    "name",
    "visibility",
    "archived",
    "default_branch",
    "pushed_at",
    "primary_language",
    "license_spdx",
    "description_present",
    "open_prs",
    "ci_latest",
    "forbidden_link_scan",
    "findings_critical",
    "findings_high",
    "findings_total",
)


class ProbeResult(BaseModel):
    """One live probe: either a computed value or UNKNOWN + the error."""

    value: str | int | None = None  # None == UNKNOWN. Never fabricated.
    error: str | None = None

    @property
    def known(self) -> bool:
        return self.value is not None


class Finding(BaseModel):
    """An audit finding. severity is one of CRITICAL|HIGH|MEDIUM|LOW|INFO."""

    severity: str
    code: str
    detail: str


class RepoMetadata(BaseModel):
    """The repos.yaml record shape (post-normalization). All optional fields
    are None — not "", not 0 — when the enumeration did not provide them."""

    name: str
    visibility: str | None = None
    is_private: bool | None = None
    is_archived: bool | None = None
    is_empty: bool | None = None
    description: str | None = None
    primary_language: str | None = None
    license_spdx: str | None = None
    default_branch: str | None = None
    pushed_at: str | None = None
    stargazer_count: int | None = None
    url: str | None = None


class RepoAudit(BaseModel):
    """The complete audit record for one repository."""

    org: str
    repo: RepoMetadata
    state: str  # ACTIVE | ARCHIVED | STALE | EMPTY | UNKNOWN
    probes: dict[str, ProbeResult] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)


def _run_gh(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one gh command. Isolated so tests can monkeypatch exactly this.

    Never raise on non-zero exit: the caller decides how to degrade. Fixed
    argument list, no shell, so bandit S603 stays quiet about the vector.
    """
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def probe_open_prs(org: str, name: str) -> ProbeResult:
    """Open PR count via `gh pr list`. UNKNOWN on any failure — never 0."""
    try:
        proc = _run_gh(
            ["gh", "pr", "list", "-R", f"{org}/{name}", "--state", "open", "--json", "number"]
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ProbeResult(error=f"open-PR probe could not run: {exc}")
    if proc.returncode != 0:
        return ProbeResult(
            error=f"gh pr list exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return ProbeResult(error=f"gh pr list returned invalid JSON: {exc}")
    if not isinstance(data, list):
        return ProbeResult(error=f"gh pr list returned {type(data).__name__}, expected list")
    # The one number we may report: the length of a list we just parsed.
    return ProbeResult(value=len(data))


def probe_ci_latest(org: str, name: str) -> ProbeResult:
    """Latest CI run conclusion via `gh run list -L 1`. UNKNOWN on failure."""
    try:
        proc = _run_gh(
            [
                "gh",
                "run",
                "list",
                "-R",
                f"{org}/{name}",
                "-L",
                "1",
                "--json",
                "conclusion,createdAt",
            ]
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ProbeResult(error=f"CI probe could not run: {exc}")
    if proc.returncode != 0:
        return ProbeResult(
            error=f"gh run list exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return ProbeResult(error=f"gh run list returned invalid JSON: {exc}")
    if not isinstance(data, list):
        return ProbeResult(error=f"gh run list returned {type(data).__name__}, expected list")
    if not data:
        # Computed, not fabricated: the API itself says this repo has no runs.
        return ProbeResult(value="no_runs")
    conclusion = data[0].get("conclusion")
    if conclusion is None:
        # createdAt exists but the run is still in progress, or the shape
        # changed; say UNKNOWN rather than guessing a conclusion.
        return ProbeResult(error="latest run has no conclusion field (in progress or shape change)")
    return ProbeResult(value=str(conclusion))


def scan_readme_forbidden(org: str, name: str) -> ProbeResult:
    """Fetch the raw README and scan it for the forbidden domain.

    Value is "clean" or "FORBIDDEN_LINK" on success. Rate limits and 404s
    (no README at all) are UNKNOWN, because an unread README proves nothing
    either way — doctrine rule 1.
    """
    try:
        proc = _run_gh(
            ["gh", "api", f"repos/{org}/{name}/readme", "-H", "Accept: application/vnd.github.raw"]
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ProbeResult(error=f"README probe could not run: {exc}")
    if proc.returncode != 0:
        return ProbeResult(
            error=f"gh api readme exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )
    if not proc.stdout.strip():
        # Empty README: computed observation, nothing to scan.
        return ProbeResult(value="clean")
    if FORBIDDEN_LINK_RE.search(proc.stdout):
        return ProbeResult(value=FORBIDDEN_LINK_CODE)
    return ProbeResult(value="clean")


def _offline_probe(reason: str) -> ProbeResult:
    """Uniform UNKNOWN for probes that were never attempted."""
    return ProbeResult(error=reason)


def compute_state(repo: RepoMetadata, now: datetime | None = None) -> str:
    """Resolve the overall state of a repo from its own metadata.

    ARCHIVED and EMPTY come straight from flags GitHub computed. STALE is the
    one state this module computes: last push older than STALE_DAYS. A missing
    or unparseable pushedAt yields UNKNOWN — we never launder a missing date
    into "fresh".
    """
    if repo.is_archived:
        return "ARCHIVED"
    if repo.is_empty:
        return "EMPTY"
    if not repo.pushed_at:
        return "UNKNOWN"
    try:
        pushed = datetime.fromisoformat(repo.pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return "UNKNOWN"
    now = now or datetime.now(UTC)
    if (now - pushed).days > STALE_DAYS:
        return "STALE"
    return "ACTIVE"


def audit_repo(
    org: str,
    repo: RepoMetadata,
    *,
    offline: bool = False,
    now: datetime | None = None,
) -> RepoAudit:
    """Audit one repo: probe (unless offline), compute state, raise findings."""
    if offline:
        probes = {
            "open_prs": _offline_probe("not attempted in offline mode"),
            "ci_latest": _offline_probe("not attempted in offline mode"),
            "forbidden_link": _offline_probe("not attempted in offline mode"),
        }
    else:
        probes = {
            "open_prs": probe_open_prs(org, repo.name),
            "ci_latest": probe_ci_latest(org, repo.name),
            "forbidden_link": scan_readme_forbidden(org, repo.name),
        }

    state = compute_state(repo, now=now)
    findings: list[Finding] = []

    if probes["forbidden_link"].value == FORBIDDEN_LINK_CODE:
        findings.append(
            Finding(
                severity="CRITICAL",
                code=FORBIDDEN_LINK_CODE,
                detail="README links a11oy.com, a third-party domain the estate does not control",
            )
        )
    elif not probes["forbidden_link"].known:
        findings.append(
            Finding(
                severity="MEDIUM",
                code="README_PROBE_UNKNOWN",
                detail=f"forbidden-link scan could not run: {probes['forbidden_link'].error}",
            )
        )

    ci = probes["ci_latest"]
    if ci.value == "failure":
        findings.append(
            Finding(
                severity="HIGH",
                code="CI_FAILING",
                detail="latest workflow run conclusion is 'failure'",
            )
        )
    elif not ci.known:
        findings.append(
            Finding(
                severity="INFO", code="CI_PROBE_UNKNOWN", detail=f"CI state unknown: {ci.error}"
            )
        )

    if not probes["open_prs"].known:
        findings.append(
            Finding(
                severity="INFO",
                code="PR_COUNT_UNKNOWN",
                detail=f"open-PR count unknown: {probes['open_prs'].error}",
            )
        )

    if not repo.license_spdx:
        findings.append(
            Finding(severity="LOW", code="LICENSE_MISSING", detail="no license detected by GitHub")
        )
    if not repo.description:
        findings.append(
            Finding(severity="INFO", code="DESCRIPTION_MISSING", detail="repo has no description")
        )
    if state == "STALE":
        findings.append(
            Finding(
                severity="MEDIUM",
                code="STALE_REPO",
                detail=f"last push {repo.pushed_at} is older than {STALE_DAYS} days",
            )
        )
    elif state == "EMPTY":
        findings.append(Finding(severity="INFO", code="EMPTY_REPO", detail="repo has no commits"))
    elif state == "ARCHIVED":
        findings.append(Finding(severity="INFO", code="ARCHIVED_REPO", detail="repo is archived"))
    elif state == "UNKNOWN":
        findings.append(
            Finding(
                severity="MEDIUM",
                code="STATE_UNKNOWN",
                detail="pushedAt missing or unparseable; freshness could not be computed",
            )
        )

    return RepoAudit(org=org, repo=repo, state=state, probes=probes, findings=findings)


def _load_repo_records(out: Path) -> list[RepoMetadata]:
    """Load per-repo metadata from an existing <out>/repos.yaml."""
    repos_yaml = Path(out) / "repos.yaml"
    if not repos_yaml.exists():
        raise EnumerationError(
            f"{repos_yaml} not found — run `szl-estate enumerate --out {out}` first"
        )
    data = yaml.safe_load(repos_yaml.read_text(encoding="utf-8")) or []
    return [RepoMetadata.model_validate(record) for record in data]


def _render_repo_audit(audit: RepoAudit) -> str:
    """Render one repo's markdown from the bundled Jinja2 template."""
    env = Environment(  # noqa: S701 — markdown output, not HTML; no escaping wanted
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template("REPO_AUDIT.j2")
    return template.render(
        org=audit.org,
        repo=audit.repo,
        state=audit.state,
        probes=audit.probes,
        findings=audit.findings,
    )


def _cell(value: Any) -> str:
    """Matrix cell: UNKNOWN for None, plain text otherwise."""
    return "UNKNOWN" if value is None else str(value)


def _write_matrix(out: Path, audits: list[RepoAudit]) -> None:
    """Write REPOSITORY_MATRIX.csv: one row per repo, stable column order."""
    with (out / "REPOSITORY_MATRIX.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(MATRIX_COLUMNS))
        writer.writeheader()
        for audit in sorted(audits, key=lambda a: a.repo.name):
            repo = audit.repo
            severity_counts = {s: 0 for s in SEVERITIES}
            for finding in audit.findings:
                severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
            writer.writerow(
                {
                    "state": audit.state,
                    "name": repo.name,
                    "visibility": _cell(repo.visibility),
                    "archived": _cell(repo.is_archived),
                    "default_branch": _cell(repo.default_branch),
                    "pushed_at": _cell(repo.pushed_at),
                    "primary_language": _cell(repo.primary_language),
                    "license_spdx": _cell(repo.license_spdx),
                    "description_present": "yes" if repo.description else "no",
                    "open_prs": _cell(audit.probes["open_prs"].value),
                    "ci_latest": _cell(audit.probes["ci_latest"].value),
                    "forbidden_link_scan": _cell(audit.probes["forbidden_link"].value),
                    "findings_critical": severity_counts.get("CRITICAL", 0),
                    "findings_high": severity_counts.get("HIGH", 0),
                    "findings_total": len(audit.findings),
                }
            )


def _write_summary(out: Path, org: str, offline: bool, audits: list[RepoAudit]) -> None:
    """Write ESTATE_SUMMARY.md with the blockers header literally on top."""
    state_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {s: 0 for s in SEVERITIES}
    blockers: list[str] = []
    for audit in audits:
        state_counts[audit.state] = state_counts.get(audit.state, 0) + 1
        for finding in audit.findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
    for severity in ("CRITICAL", "HIGH"):  # CRITICAL first, then HIGH — by doctrine
        for audit in sorted(audits, key=lambda a: a.repo.name):
            for finding in audit.findings:
                if finding.severity == severity:
                    blockers.append(
                        f"- **{finding.severity}** `{finding.code}` "
                        f"— `{audit.repo.name}`: {finding.detail}"
                    )

    lines = [
        f"# Estate summary — {org}",
        "",
        f"Repos audited: {len(audits)} (mode: {'offline' if offline else 'live'})",
        "",
        f"## {BLOCKERS_HEADER}",
        "",
    ]
    lines.extend(blockers if blockers else ["No CRITICAL or HIGH findings in this run."])
    lines += ["", "## Counts by state", ""]
    for state in ("ACTIVE", "ARCHIVED", "STALE", "EMPTY", "UNKNOWN"):
        if state in state_counts:
            lines.append(f"- {state}: {state_counts[state]}")
    lines += ["", "## Findings by severity", ""]
    for severity in SEVERITIES:
        lines.append(f"- {severity}: {severity_counts.get(severity, 0)}")
    lines.append("")
    (out / "ESTATE_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def audit_org(
    org: str,
    *,
    out: Path,
    offline: bool = False,
    fixture: Path | None = None,
    now: datetime | None = None,
) -> list[RepoAudit]:
    """Audit every enumerated repo and write all rollups.

    Reuses an existing ``<out>/repos.yaml`` when present (so enumeration and
    audit can be two separately receipted steps); otherwise enumerates first.
    """
    out = Path(out)
    (out / "repos").mkdir(parents=True, exist_ok=True)
    if (out / "repos.yaml").exists():
        repos = _load_repo_records(out)
    else:
        evidence = enumerate_org(org, out=out, offline=offline, fixture=fixture)
        repos = _load_repo_records(out)
        # The audit report inherits enumeration honesty: a PARTIAL inventory is
        # still audited, but the summary says the mode and the evidence stays
        # on disk at enumeration.json for the reviewer.
        _ = evidence  # evidence file itself is the artifact; no further action

    audits = [audit_repo(org, repo, offline=offline, now=now) for repo in repos]
    for audit in audits:
        (out / "repos" / f"{audit.repo.name}.md").write_text(
            _render_repo_audit(audit), encoding="utf-8"
        )
    _write_matrix(out, audits)
    _write_summary(out, org, offline, audits)
    return audits


def main(argv: list[str] | None = None) -> int:
    """Module entry point: `python -m szl_estate.audit`."""
    parser = argparse.ArgumentParser(
        prog="szl_estate.audit",
        description="Per-repo audit: one markdown file per repo, plus matrix and summary rollups.",
    )
    parser.add_argument("--org", required=True, help="GitHub organization to audit")
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    parser.add_argument(
        "--offline", action="store_true", help="skip all live GitHub probes; record UNKNOWN"
    )
    parser.add_argument(
        "--fixture", type=Path, default=None, help="offline fixture for enumeration"
    )
    parser.add_argument("--json", action="store_true", help="print the audit records as JSON")
    args = parser.parse_args(argv)

    audits = audit_org(args.org, out=args.out, offline=args.offline, fixture=args.fixture)
    if args.json:
        print(json.dumps([a.model_dump(mode="json") for a in audits], indent=2))
    else:
        print(f"Audited {len(audits)} repos into {args.out}")
        print(f"  per-repo files: {args.out / 'repos'}")
        print(f"  rollups: {args.out / 'REPOSITORY_MATRIX.csv'}, {args.out / 'ESTATE_SUMMARY.md'}")
    # Findings — even CRITICAL ones — are audit output, not tool failure.
    # doctor owns fatal exits; a measurement tool exits 0 when it measured.
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
