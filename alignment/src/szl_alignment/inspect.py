"""Read-only measurement of one repository — the "control before action" half.

:func:`inspect_repo` walks a repo and returns a :class:`RepoReport` describing
which alignment pieces exist, which are missing, and where the
release-blocking forbidden-domain rule is violated.

Design contract:

- **Never raises on a weird repo.** Missing directories, unreadable files,
  non-UTF-8 encodings, broken symlinks, vanished paths — all degrade to
  UNKNOWN-ish fields plus an entry in ``open_questions``. The estimator of an
  org of a hundred repos must survive every one of them being strange.
- **Read-only.** inspect opens nothing for writing, follows no network, and
  does not shell out. ``rg`` is deliberately not required: the regex lives in
  Python so the result is identical in tests, CI and on a bare machine.
- **Everything counted.** Guard-context (prohibition) hits are allowed but
  still counted as ``guard_mentions`` — visibility first, verdict second.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from szl_alignment.const import (
    ALLOWLIST_RE,
    COC_PATH,
    CONTRIBUTING_PATH,
    DOCTRINE_LINE,
    FORBIDDEN_RE,
    HEADER_MARKER,
    LICENSE_APACHE,
    LICENSE_CANDIDATES,
    LICENSE_NONE,
    LICENSE_SZL_PROP,
    LICENSE_UNKNOWN,
    MAX_FILE_BYTES,
    PR_TEMPLATE_PATH,
    PY_EXTENSIONS,
    SECURITY_PATH,
    SKIP_SCAN_DIRS,
    TEXT_SCAN_EXTENSIONS,
    TS_EXTENSIONS,
    WORKFLOWS_DIR,
)

# Number of lines suffixed "..." in violation text before we stop trusting
# that what we store is the whole line (cosmetic truncation only).
_MAX_VIOLATION_TEXT = 300


class LicenseKind(StrEnum):
    """Detected license family. NEVER overwrite an existing LICENSE — this is
    detection only; a missing/odd license is advice, not an action."""

    APACHE_2 = LICENSE_APACHE
    SZL_PROPRIETARY = LICENSE_SZL_PROP
    NONE = LICENSE_NONE
    UNKNOWN = LICENSE_UNKNOWN


@dataclass
class Violation:
    """One true forbidden-domain hit (a guard-context hit never becomes this).

    ``file`` is repo-relative POSIX. ``scan_error`` carries why the scan is
    incomplete when ``error`` is not None.
    """

    file: str
    line: int
    text: str  # truncated to a few hundred chars, newline-stripped


@dataclass
class ForbiddenScan:
    """Result of the release-blocking forbidden-domain gate."""

    violations: list[Violation] = field(default_factory=list)
    guard_mentions: int = 0  # allowed: prohibition/assertNotIn/blocklist lines
    files_scanned: int = 0
    files_skipped: int = 0  # non-text, oversized, unreadable — all counted
    error: str | None = None  # set when the scan itself degraded


@dataclass
class RepoReport:
    """Everything the planner needs to know about one repository.

    All filesystem errors collapse into UNKNOWN fields and ``open_questions``;
    constructing a RepoReport never raises.
    """

    name: str
    path: str = ""
    has_readme: bool = False
    has_license: bool = False
    license_kind: str = LicenseKind.UNKNOWN.value  # APACHE_2 | SZL_PROPRIETARY | NONE | UNKNOWN
    license_file: str | None = None  # e.g. "LICENSE", repo-relative
    has_security: bool = False
    has_contributing: bool = False
    has_coc: bool = False
    has_pr_template: bool = False
    has_issue_templates: bool = False
    ci_workflows: list[str] = field(default_factory=list)  # workflow file names
    python_detected: bool = False
    typescript_detected: bool = False
    forbidden_scan: ForbiddenScan = field(default_factory=ForbiddenScan)
    doctrine_header_present: bool = False  # README mentions the doctrine line
    header_marker_present: bool = False  # idempotency marker <!-- szl:header v1 -->
    open_questions: list[str] = field(default_factory=list)

    # -- convenience accessors ------------------------------------------------

    @property
    def true_violations(self) -> list[Violation]:
        """True forbidden-domain violations (guard mentions excluded)."""
        return self.forbidden_scan.violations


# ---------------------------------------------------------------------------
# small helpers — every one of them is silent-on-failure by design
# ---------------------------------------------------------------------------


def _read_text(path: Path, max_bytes: int = MAX_FILE_BYTES) -> str | None:
    """Read a file as UTF-8, silently returning None on any failure.

    Truncates at ``max_bytes`` so a pathological multi-hundred-MB checked-in
    blob never stalls the scan; a partial read is always better than a crash.
    """
    try:
        with path.open("rb") as fh:
            raw = fh.read(max_bytes)
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return None


def _sniff_license(path: Path) -> str:
    """Classify a LICENSE file by sniffing its first lines.

    - 'Apache License' (the canonical title)  -> APACHE_2
    - 'LicenseRef-SZL-Proprietary' recorded anywhere in the header -> SZL_PROPRIETARY
    - anything readable but unrecognized       -> UNKNOWN
    """
    text = _read_text(path, max_bytes=32_768)
    if text is None:
        return LICENSE_UNKNOWN
    head = text[:4096]
    if "Apache License" in head:
        return LICENSE_APACHE
    if "LicenseRef-SZL-Proprietary" in head or "SZL Proprietary" in head:
        return LICENSE_SZL_PROP
    return LICENSE_UNKNOWN


def _detect_license(repo: Path) -> tuple[bool, str, str | None]:
    """Find and classify the top-level LICENSE file, if any."""
    for name in LICENSE_CANDIDATES:
        candidate = repo / name
        if candidate.is_file():
            return True, _sniff_license(candidate), name
    return False, LICENSE_NONE, None


def _walk(repo: Path):
    """Yield ``Path``\\ s under ``repo`` skipping generated/dependency dirs.

    Uses os.walk (not rglob) so that pruning is cheap and symlink loops
    cannot happen (followlinks defaults to False). Never raises: a single
    unreadable directory is silently skipped — an incomplete scan is an
    UNKNOWN-flavored report, not an exception.
    """
    for root, dirs, files in os.walk(repo, followlinks=False):
        # prune skip-dirs in place so os.walk does not descend into them
        dirs[:] = [d for d in dirs if d not in SKIP_SCAN_DIRS]
        root_path = Path(root)
        for fname in files:
            yield root_path, fname


def _detect_languages(repo: Path) -> tuple[bool, bool]:
    """Detect Python and TypeScript/JavaScript from manifest presence or sources.

    Manifest probe (fast path, no deep walk):

    - Python:     pyproject.toml or setup.py (or setup.cfg) at the root
    - TypeScript: package.json or tsconfig.json at the root

    Source probe: any ``**/*.py`` / ``**/*.{ts,tsx,js,...}`` file outside the
    skipped trees. A repo that only contains a Python *tool* directory is
    still Python-detected — the base CI simply no-ops ruff/pytest if there is
    nothing to run.
    """
    python = (repo / "pyproject.toml").is_file() or (repo / "setup.py").is_file()
    typescript = (repo / "package.json").is_file() or (repo / "tsconfig.json").is_file()
    if python and typescript:
        return python, typescript
    for root_path, fname in _walk(repo):  # noqa: B007 — root_path is the walk context
        suffix = Path(fname).suffix.lower()
        if not python and suffix in PY_EXTENSIONS:
            python = True
        if not typescript and suffix in TS_EXTENSIONS:
            typescript = True
        if python and typescript:
            break
    return python, typescript


def _list_ci_workflows(repo: Path) -> list[str]:
    """Names of workflow files under .github/workflows/, sorted."""
    wf = repo / WORKFLOWS_DIR
    names: list[str] = []
    try:
        if wf.is_dir():
            for child in sorted(wf.iterdir()):
                if child.is_file() and child.suffix.lower() in {".yml", ".yaml"}:
                    names.append(child.name)
    except OSError:
        pass
    return names


def _find_readme(repo: Path) -> Path | None:
    """Locate the repo's README (README.md preferred, any case/extension after)."""
    preferred = ["README.md", "readme.md", "README.markdown", "README.txt", "README", "Readme.md"]
    for name in preferred:
        candidate = repo / name
        if candidate.is_file():
            return candidate
    try:
        for child in sorted(repo.iterdir()):
            if child.is_file() and child.name.upper().startswith("README"):
                return child
    except OSError:
        pass
    return None


def scan_forbidden(repo: Path) -> ForbiddenScan:
    r"""Run the release-blocking forbidden-domain gate over one repo.

    Rule (validated against the live org): any line matching
    ``(?<!-)a11oy\.com`` is a violation UNLESS the same line matches the
    prohibition/guard allowlist (never|forbidden|not in|assertNotIn|does not
    appear|is not a surface|blocklist, case-insensitive). Guard lines are
    allowed but counted.

    Only text-ish files (by extension) below 1 MiB are scanned; everything
    skipped is counted so a report never silently claims "clean".
    """
    result = ForbiddenScan()
    try:
        for root_path, fname in _walk(repo):
            suffix = Path(fname).suffix.lower()
            if suffix not in TEXT_SCAN_EXTENSIONS:
                continue
            fpath = root_path / fname
            try:
                if fpath.stat().st_size > MAX_FILE_BYTES:
                    result.files_skipped += 1
                    continue
            except OSError:
                result.files_skipped += 1
                continue
            content = _read_text(fpath)
            if content is None:
                result.files_skipped += 1
                continue
            result.files_scanned += 1
            rel = fpath.relative_to(repo).as_posix()
            for lineno, line in enumerate(content.splitlines(), start=1):
                if FORBIDDEN_RE.search(line):
                    if ALLOWLIST_RE.search(line):
                        result.guard_mentions += 1
                    else:
                        snippet = line.strip()
                        if len(snippet) > _MAX_VIOLATION_TEXT:
                            snippet = snippet[:_MAX_VIOLATION_TEXT] + "..."
                        result.violations.append(Violation(file=rel, line=lineno, text=snippet))
    except OSError as exc:  # extremely defensive: _walk already swallows most
        result.error = f"scan degraded: {exc}"
    return result


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def inspect_repo(path: str | os.PathLike[str]) -> RepoReport:
    """Inspect one repository and return its RepoReport.

    ``path`` may be missing, empty, or not a git repo at all — the report
    simply reflects what was found, with an open question whenever the on-disk
    reality could not be read.
    """
    repo = Path(path)
    name = repo.resolve().name if repo.exists() else (repo.name or "UNKNOWN")
    report = RepoReport(name=name, path=str(repo))

    if not repo.exists():
        report.open_questions.append(f"path does not exist: {repo}")
        return report
    if not repo.is_dir():
        report.open_questions.append(f"path is not a directory: {repo}")
        return report

    # README + doctrine header ------------------------------------------------
    readme = _find_readme(repo)
    report.has_readme = readme is not None
    if readme is not None:
        text = _read_text(readme)
        if text is None:
            report.open_questions.append(f"README present but unreadable: {readme.name}")
        else:
            report.doctrine_header_present = DOCTRINE_LINE in text
            report.header_marker_present = HEADER_MARKER in text
    else:
        report.open_questions.append("no README found")

    # LICENSE -----------------------------------------------------------------
    report.has_license, report.license_kind, report.license_file = _detect_license(repo)
    if not report.has_license:
        report.open_questions.append(
            "no LICENSE found — LICENSE is never auto-written (legal statement); "
            "add one manually (Apache-2.0 or LicenseRef-SZL-Proprietary)"
        )
    elif report.license_kind == LICENSE_UNKNOWN:
        report.open_questions.append(f"LICENSE kind unrecognized in {report.license_file}")

    # Governance files ----------------------------------------------------------
    report.has_security = (repo / SECURITY_PATH).is_file()
    report.has_contributing = (repo / CONTRIBUTING_PATH).is_file()
    report.has_coc = (repo / COC_PATH).is_file()
    report.has_pr_template = (repo / PR_TEMPLATE_PATH).is_file()
    issue_dir = repo / ".github" / "ISSUE_TEMPLATE"
    report.has_issue_templates = any(_issue_template_files(issue_dir))

    # CI + languages -----------------------------------------------------------
    report.ci_workflows = _list_ci_workflows(repo)
    report.python_detected, report.typescript_detected = _detect_languages(repo)

    # Forbidden-domain gate -----------------------------------------------------
    report.forbidden_scan = scan_forbidden(repo)

    return report


def _issue_template_files(issue_dir: Path):
    """Yield files under an ISSUE_TEMPLATE dir (may be empty; never raises)."""
    try:
        for child in sorted(issue_dir.iterdir()):
            if child.is_file():
                yield child
    except OSError:
        return


# Re-export for convenience (tests and CLI import these names from here).
__all__ = [
    "ForbiddenScan",
    "LicenseKind",
    "RepoReport",
    "Violation",
    "inspect_repo",
    "scan_forbidden",
]
