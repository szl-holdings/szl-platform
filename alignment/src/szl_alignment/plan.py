"""Deterministic planning: RepoReport -> list[Action].

The planner is a pure function of the inspection report — no filesystem, no
network, no clock — so a plan is reviewable, diffable, and identical on every
run. Application concerns (writing, git) live in :mod:`szl_alignment.apply`.

Action ordering is stable and meaningful:

1. ``UPDATE_README_HEADER`` — the visible doctrine layer first;
2. ``ADD_FILE``            — governance files (SECURITY, CONTRIBUTING, CoC,
                             PR + issue templates);
3. ``ADD_WORKFLOW``        — the two CI gates (forbidden-domain for every
                             repo, base-python-ci for Python repos);
4. ``FIX_FORBIDDEN``       — one action per true forbidden-domain violation,
                             ALWAYS flagged ``needs_review`` (the tool prepares
                             the diff; a human decides replace-with-a-11-oy.com
                             vs remove).

LICENSE is never planned: it is a legal statement, and the estate mixes
Apache-2.0 with LicenseRef-SZL-Proprietary. A missing/odd license surfaces as
an advice-only open question on the report instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from szl_alignment.const import (
    BASE_CI_NAME,
    BASE_PYTHON_CI_PATH,
    COC_PATH,
    CONTRIBUTING_PATH,
    FORBIDDEN_DOMAIN_PATH,
    HEADER_MARKER,
    ISSUE_TEMPLATES_DIR,
    PR_TEMPLATE_PATH,
    SECURITY_PATH,
)
from szl_alignment.inspect import RepoReport


class ActionKind(StrEnum):
    """The four ways the alignment engine may touch a repo."""

    ADD_FILE = "ADD_FILE"
    UPDATE_README_HEADER = "UPDATE_README_HEADER"
    ADD_WORKFLOW = "ADD_WORKFLOW"
    FIX_FORBIDDEN = "FIX_FORBIDDEN"


@dataclass(frozen=True)
class Action:
    """One proposed change. ``template`` is the resource path inside
    ``alignment/templates/`` (empty for free-form fixes); ``needs_review``
    marks actions a human must approve before anything is written."""

    kind: ActionKind
    path: str  # repo-relative POSIX target
    template: str  # template resource name, or "" (e.g. FIX_FORBIDDEN)
    reason: str
    needs_review: bool = False


# ---------------------------------------------------------------------------
# Template resolution — templates ship *next to* the package in the source
# checkout (alignment/templates), so walk up from this file until they appear.
# SZL_ALIGNMENT_TEMPLATES overrides for wheel/container layouts.
# ---------------------------------------------------------------------------

_TEMPLATES_ENV = "SZL_ALIGNMENT_TEMPLATES"


def templates_dir() -> Path:
    """Locate alignment/templates, raising a clear error if it cannot."""
    env = os.environ.get(_TEMPLATES_ENV)
    if env:
        path = Path(env)
        if path.is_dir():
            return path
        raise FileNotFoundError(f"{_TEMPLATES_ENV} set but not a directory: {env}")
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "templates"
        if candidate.is_dir() and (candidate / "README_HEADER.md").is_file():
            return candidate
    raise FileNotFoundError(
        f"alignment/templates not found above {__file__}; set {_TEMPLATES_ENV}"
    )


def template_text(name: str) -> str:
    """Return the raw text of one template resource (e.g. 'workflows/base-python-ci.yml')."""
    path = templates_dir() / name
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The gap -> action mapping (kept as data so tests can assert on it directly)
# ---------------------------------------------------------------------------

_GOVERNANCE_FILES: tuple[tuple[str, str, str, str], ...] = (
    # (report attr that means "present", target path, template, reason)
    (
        "has_security",
        SECURITY_PATH,
        "SECURITY.md",
        "SECURITY.md missing — one security policy across the org "
        "(disclosure, supported versions, receipt verification)",
    ),
    (
        "has_contributing",
        CONTRIBUTING_PATH,
        "CONTRIBUTING.md",
        "CONTRIBUTING.md missing — one contribution path: szl/<change> branches, "
        "conventional commits, sign-off, the three doctrine rules",
    ),
    (
        "has_coc",
        COC_PATH,
        "CODE_OF_CONDUCT.md",
        "CODE_OF_CONDUCT.md missing — one conduct baseline across the org",
    ),
    (
        "has_pr_template",
        PR_TEMPLATE_PATH,
        "PULL_REQUEST_TEMPLATE.md",
        "PR template missing — one review gate incl. 'no new a11oy.com references', "
        "'UNKNOWN not claimed as PASS', 'receipts updated'",
    ),
)

_ISSUE_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        f"{ISSUE_TEMPLATES_DIR}/bug_report.yml",
        "ISSUE_TEMPLATE/bug_report.yml",
        "issue templates missing — one structured bug-report form across the org",
    ),
    (
        f"{ISSUE_TEMPLATES_DIR}/config.yml",
        "ISSUE_TEMPLATE/config.yml",
        "issue templates missing — route security reports privately, disable blanks",
    ),
)


def _has_base_python_ci(report: RepoReport) -> bool:
    """True when an existing workflow is our base CI or clearly named like it.

    'Named like it' = exact template name, or a workflow whose name suggests
    the standard python lint/test pipeline — such a repo is already covered.
    """
    for name in report.ci_workflows:
        lower = name.lower()
        if name == BASE_CI_NAME:
            return True
        if "python" in lower and ("ci" in lower or "test" in lower or "lint" in lower):
            return True
    return False


def plan_alignment(report: RepoReport) -> list[Action]:
    """Compute the deterministic alignment plan for one repo."""
    actions: list[Action] = []

    # 1 — doctrine header -----------------------------------------------------
    # Present means: the marker from templates/README_HEADER.md is there, or
    # the doctrine sentence is (a hand-maintained equivalent counts; forcing a
    # duplicate header on top of an existing one would be worse).
    if not (report.header_marker_present or report.doctrine_header_present):
        actions.append(
            Action(
                kind=ActionKind.UPDATE_README_HEADER,
                path="README.md",
                template="README_HEADER.md",
                reason=(
                    "doctrine header absent — insert after the first H1 with "
                    f"idempotency marker {HEADER_MARKER!r}"
                ),
            )
        )

    # 2 — governance files ------------------------------------------------------
    for attr, path, template, reason in _GOVERNANCE_FILES:
        if not getattr(report, attr):
            actions.append(
                Action(kind=ActionKind.ADD_FILE, path=path, template=template, reason=reason)
            )
    if not report.has_issue_templates:
        for path, template, reason in _ISSUE_TEMPLATES:
            actions.append(
                Action(kind=ActionKind.ADD_FILE, path=path, template=template, reason=reason)
            )

    # Never planned: LICENSE. Advice-only — see RepoReport.open_questions.

    # 3 — workflows ------------------------------------------------------------
    if FORBIDDEN_DOMAIN_PATH.rsplit("/", 1)[-1] not in report.ci_workflows:
        actions.append(
            Action(
                kind=ActionKind.ADD_WORKFLOW,
                path=FORBIDDEN_DOMAIN_PATH,
                template="workflows/forbidden-domain.yml",
                reason=(
                    "every repo runs the release-blocking forbidden-domain gate "
                    "(rg-based, prohibition/guard allowlist)"
                ),
            )
        )
    if report.python_detected and not _has_base_python_ci(report):
        actions.append(
            Action(
                kind=ActionKind.ADD_WORKFLOW,
                path=BASE_PYTHON_CI_PATH,
                template="workflows/base-python-ci.yml",
                reason=(
                    "Python detected and no existing Python CI — add the base "
                    "ruff + pytest gate on 3.11/3.12"
                ),
            )
        )

    # 4 — true forbidden-domain violations (human review, always last) ---------
    for violation in sorted(report.true_violations, key=lambda v: (v.file, v.line)):
        actions.append(
            Action(
                kind=ActionKind.FIX_FORBIDDEN,
                path=violation.file,
                template="",
                reason=(
                    f"forbidden-domain violation at {violation.file}:{violation.line}: "
                    f"{violation.text!r} — replace with a-11-oy.com or remove; "
                    "MUST be reviewed by a human before merging"
                ),
                needs_review=True,
            )
        )

    return actions


__all__ = ["Action", "ActionKind", "plan_alignment", "template_text", "templates_dir"]
