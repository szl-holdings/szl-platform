"""Applying an alignment plan — dry-run by default, branch-based when real.

Control before action:

* **Dry-run is the default.** ``apply_plan(..., dry_run=True)`` computes every
  change as a unified diff and prints a summary; nothing touches the disk.
* **Real runs stay off the default branch.** Non-dry applies create (or
  switch to) ``szl/alignment-v14``, write files, and commit once with a
  signed-off message. The tool never force-pushes, never deletes files, and
  never writes a file whose existing content differs from the template —
  that is a human merge, not a tool decision.
* **Idempotent.** Marker comments (``<!-- szl:header v1 -->``) and content
  comparison make a second run produce zero changes; tested.
* **FIX_FORBIDDEN is prepared, never written.** Those actions surface as
  NEEDS_REVIEW with prepared-diff context in the summary and PR body.

A PR body (what changed, why, receipts) is generated for every run; non-dry
runs also write it to ``.git/SZL_ALIGNMENT_PR_BODY.md``.
"""

from __future__ import annotations

import difflib
import os
import subprocess  # noqa: S404 — subprocess is the only supported git transport
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from szl_alignment.const import (
    ALIGNMENT_BRANCH,
    HEADER_MARKER,
    ORG_URL,
    PRODUCT_URL,
    PROOF_URL,
    __version__,
)
from szl_alignment.plan import Action, ActionKind, template_text


class ApplyStatus(StrEnum):
    """Outcome of one action."""

    APPLIED = "APPLIED"  # written (or would be, in dry-run)
    DRY_RUN = "DRY_RUN"  # would change; shown as a diff only
    SKIPPED = "SKIPPED"  # already aligned / unsafe to change
    NEEDS_REVIEW = "NEEDS_REVIEW"  # FIX_FORBIDDEN & anything a human must decide


@dataclass
class AppliedAction:
    """One action after apply: status, explanation, and (for file changes)
    the unified diff of exactly what changed."""

    action: Action
    status: ApplyStatus
    detail: str = ""
    diff: str = ""


@dataclass
class ApplyResult:
    """Aggregate of one apply_plan call."""

    repo_path: str
    branch: str
    dry_run: bool
    items: list[AppliedAction] = field(default_factory=list)
    commit_sha: str | None = None
    pr_body: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> int:
        """How many actions would change / did change files."""
        return sum(1 for i in self.items if i.status in {ApplyStatus.APPLIED, ApplyStatus.DRY_RUN})

    @property
    def needs_review(self) -> int:
        return sum(1 for i in self.items if i.status is ApplyStatus.NEEDS_REVIEW)


class ApplyError(RuntimeError):
    """Refusal to apply (dirty tree, detached on default branch, git missing...).

    Never silently papered over: a refused apply is itself evidence."""


# ---------------------------------------------------------------------------
# Change computation — pure, shared by dry-run and real application
# ---------------------------------------------------------------------------


def _unified_diff(path: str, old: str, new: str) -> str:
    """Unified diff for one file transition (old may be '' for new files)."""
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _insert_header_after_h1(readme: str, header: str) -> str:
    """Insert the doctrine header right after the first ATX H1.

    Inserting anywhere else (before the H1, at the bottom) was tried on the
    live estate and read badly; after the H1 is where badges belong. If the
    README has no H1, the header goes at the very top. Blank lines are
    normalized so the result is stable across run one and run two.
    """
    lines = readme.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):  # first H1 (ATX); setext H1s are rare in this org
            insert_at = i + 1
            break
    header_block = header if header.endswith("\n") else header + "\n"
    pieces: list[str] = []
    # stay contiguous with the H1, then the header, then one blank line, then
    # whatever followed (leading blank lines collapsed to avoid runaway growth)
    pieces.extend(lines[:insert_at])
    pieces.append(header_block)
    rest = lines[insert_at:]
    while rest and rest[0].strip() == "":
        rest.pop(0)
    if rest:
        pieces.append("\n")
        pieces.extend(rest)
    return "".join(pieces)


def _compute_change(
    repo: Path, action: Action
) -> tuple[Action, str | None, str | None, str]:
    """Compute (effective_action, old, new, note) for one action without touching the disk.

    - ``(action, old, new, note)`` — real change; old may be None (new file).
      The returned action is the input unless UPDATE_README_HEADER retargets
      it to the README actually found on disk (e.g. ``readme.md``).
    - ``(action, None, None, "SKIP: ...")`` — already aligned or unsafe to change.
    - ``(action, None, None, "NEEDS_REVIEW: ...")`` — human decision required.
    """
    note_prefix_skip = "SKIP: "
    note_prefix_review = "NEEDS_REVIEW: "

    if action.kind is ActionKind.FIX_FORBIDDEN:
        # Prepared, never written: the correct fix (replace with a-11-oy.com
        # vs remove) is a context decision only a human can make.
        old = None
        target = repo / action.path
        try:
            old = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        return action, None, None, note_prefix_review + action.reason + (
            ""
            if old is None
            else "  [file readable in dry-run; diff left to the reviewer]"
        )

    template = template_text(action.template)

    if action.kind is ActionKind.UPDATE_README_HEADER:
        from szl_alignment.inspect import _find_readme  # local: keeps module graph flat

        readme_path = _find_readme(repo)
        if readme_path is None:
            # No README at all: seed one from the header so the repo at least
            # carries the doctrine; richer READMEs are a human's job.
            new_text = f"# {repo.name}\n\n{template}"
            return action, None, new_text, (
                "no README found — seeding README.md with the doctrine header"
            )
        old_text = readme_path.read_text(encoding="utf-8", errors="replace")
        if HEADER_MARKER in old_text:
            return action, None, None, (
                note_prefix_skip + "header marker already present (idempotent)"
            )
        new_text = _insert_header_after_h1(old_text, template)
        if new_text == old_text:
            return action, None, None, note_prefix_skip + "header insertion produced no change"
        # report against the canonical README.md name for readability
        rel = readme_path.relative_to(repo).as_posix()
        if rel != action.path:
            action = Action(action.kind, rel, action.template, action.reason, action.needs_review)
        return action, old_text, new_text, "insert doctrine header after first H1"

    if action.kind in {ActionKind.ADD_FILE, ActionKind.ADD_WORKFLOW}:
        target = repo / action.path
        if target.exists():
            existing = target.read_text(encoding="utf-8", errors="replace")
            if existing == template:
                return action, None, None, note_prefix_skip + "already aligned (content identical)"
            return action, None, None, note_prefix_skip + (
                f"{action.path} exists with different content — NEVER overwritten; "
                "merge manually"
            )
        return action, None, template, "add from template"

    return action, None, None, note_prefix_skip + f"unknown action kind {action.kind}"


# ---------------------------------------------------------------------------
# git plumbing — every command is a fixed argv list, no shell, short timeout
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one git command. Fixed argv, no shell; the caller checks returncode."""
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607 — fixed tool name, resolved via PATH by design
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _git_checked(repo: Path, *args: str) -> str:
    """Run git and return stdout, raising ApplyError on any failure."""
    try:
        proc = _git(repo, *args)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ApplyError(f"git {' '.join(args)} failed to run: {exc}") from exc
    if proc.returncode != 0:
        raise ApplyError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


_DEFAULT_BRANCHES = {"main", "master"}


def _prepare_branch(repo: Path, branch: str) -> None:
    """Create-or-switch to the alignment branch; refuse the default branch.

    The default branch is never touched directly, and force-push is never
    used anywhere in this codebase (pushing is left to humans entirely).
    """
    current = _git_checked(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if current in _DEFAULT_BRANCHES and branch in _DEFAULT_BRANCHES:
        raise ApplyError(f"refusing to apply on default branch {current!r}")
    if current == branch:
        return
    exists = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--verify", branch],  # noqa: S607 — fixed argv, no shell
        cwd=repo, capture_output=True, text=True, timeout=30,
    ).returncode == 0
    if exists:
        _git_checked(repo, "switch", branch)
    elif current in _DEFAULT_BRANCHES:
        _git_checked(repo, "switch", "-c", branch)
    else:
        # non-default non-target branch (e.g. a feature branch): create from it
        _git_checked(repo, "switch", "-c", branch)


def _ensure_clean_tree(repo: Path) -> None:
    """Refuse to apply over a dirty worktree — receipts must be attributable."""
    status = _git_checked(repo, "status", "--porcelain")
    if status:
        raise ApplyError(
            "worktree has uncommitted changes; apply must start from a clean tree:\n" + status
        )


def _commit(repo: Path, plan: list[Action]) -> str | None:
    """Stage everything changed and commit with a signed-off message.

    Returns the commit SHA, or None when the plan produced no changes
    (idempotent second run — the empty-diff guarantee).
    """
    _git_checked(repo, "add", "-A")
    if _git(repo, "diff", "--cached", "--quiet").returncode == 0:
        return None
    lines = [
        "chore(alignment): bring repo up to the org standard",
        "",
        "Control before action. Evidence after.",
        "",
        "Planned by szl-alignment v" + __version__ + ":",
    ]
    lines.extend(f"- {a.kind} {a.path}" for a in plan if a.kind is not ActionKind.FIX_FORBIDDEN)
    forbidden = [a for a in plan if a.kind is ActionKind.FIX_FORBIDDEN]
    if forbidden:
        lines.append("")
        lines.append(
            f"NEEDS REVIEW: {len(forbidden)} forbidden-domain violation(s) detected; "
            "prepared but NOT auto-fixed (replace with a-11-oy.com or remove)."
        )
    # -s appends Signed-off-by using the identity set below (fixed identity for
    # attribution; humans re-sign when they adopt the branch).
    _git_checked(
        repo,
        "-c", "user.name=szl-alignment",
        "-c", "user.email=alignment@a-11-oy.com",
        "commit", "-s", "-m", "\n".join(lines),
    )
    return _git_checked(repo, "rev-parse", "HEAD")


def _write_pr_body(repo: Path, body: str) -> None:
    """Stash the PR body in .git/ (untracked — never commits itself)."""
    git_dir = _git_checked(repo, "rev-parse", "--git-dir")
    target = Path(git_dir)
    if not target.is_absolute():
        target = repo / target
    try:
        (target / "SZL_ALIGNMENT_PR_BODY.md").write_text(body, encoding="utf-8")
    except OSError:
        pass  # cosmetic; the body is still printed and returned


# ---------------------------------------------------------------------------
# PR body — what changed, why, receipts
# ---------------------------------------------------------------------------


def render_pr_body(repo_name: str, result: ApplyResult) -> str:
    """Render the pull-request body for one alignment run."""
    changed = [i for i in result.items if i.status in {ApplyStatus.APPLIED, ApplyStatus.DRY_RUN}]
    review = [i for i in result.items if i.status is ApplyStatus.NEEDS_REVIEW]
    skipped = [i for i in result.items if i.status is ApplyStatus.SKIPPED]

    lines = [
        "## Alignment run — what changed and why",
        "",
        "Prepared by `szl-alignment` v" + __version__ + " for the szl-holdings org standard.",
        "",
        "### What changed",
        "",
    ]
    if changed:
        for item in changed:
            lines.append(f"- **{item.action.kind.value}** `{item.action.path}` — {item.detail}")
    else:
        lines.append("- (nothing — repo already aligned)")
    lines += ["", "### NEEDS REVIEW — human review required", ""]
    if review:
        lines.append(
            "These items were detected and prepared but **not** auto-applied "
            "— replace with `a-11-oy.com` or remove, judged case by case:"
        )
        lines.append("")
        for item in review:
            lines.append(f"- [ ] `{item.action.path}` — {item.action.reason}")
    else:
        lines.append("- None.")
    lines += [
        "",
        "### Alignment checklist",
        "",
        "- [x] One doctrine header (idempotency marker `<!-- szl:header v1 -->`)",
        "- [x] One security policy (`SECURITY.md`)",
        "- [x] One contribution path (`CONTRIBUTING.md`, PR + issue templates)",
        "- [x] One CI gate (`forbidden-domain.yml`; `base-python-ci.yml` for Python repos)",
        "- [ ] No new a11oy.com references (gate must stay green)",
        "- [ ] UNKNOWN not claimed as PASS",
        "- [ ] Receipts updated — attach the CI run for this PR as the receipt",
        "",
        "### Receipts",
        "",
        f"- Receipt verification: {PROOF_URL}",
        f"- Product surface: {PRODUCT_URL}",
        f"- Org: {ORG_URL}",
        "",
        f"_Skipped as already-aligned/unsafe: {len(skipped)} item(s); see the run log._",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# the entry point
# ---------------------------------------------------------------------------


def apply_plan(
    repo_path: str | os.PathLike[str],
    plan: list[Action],
    branch: str = ALIGNMENT_BRANCH,
    dry_run: bool = True,
) -> ApplyResult:
    """Apply (or, in dry-run, preview) one plan against one repo.

    Dry-run: computes unified diffs for every action and returns/prints the
    summary. Non-dry: prepares ``branch`` via git (creating it from the
    current branch when needed), requires a clean worktree, writes the files,
    commits once with a Signed-off-by trailer, and writes the PR body into
    ``.git/SZL_ALIGNMENT_PR_BODY.md``.
    """
    repo = Path(repo_path)
    result = ApplyResult(repo_path=str(repo), branch=branch, dry_run=dry_run)

    if not repo.is_dir():
        raise ApplyError(f"not a directory: {repo}")

    # 1 — compute every change (identical code path for dry-run and real)
    computed = [_compute_change(repo, a) for a in plan]

    # 2 — classify
    for action, old, new, note in computed:
        if note.startswith("NEEDS_REVIEW: "):
            result.items.append(
                AppliedAction(action, ApplyStatus.NEEDS_REVIEW, note[len("NEEDS_REVIEW: "):])
            )
        elif note.startswith("SKIP: "):
            result.items.append(
                AppliedAction(action, ApplyStatus.SKIPPED, note[len("SKIP: "):])
            )
        else:
            diff = _unified_diff(action.path, old or "", new or "")
            status = ApplyStatus.DRY_RUN if dry_run else ApplyStatus.APPLIED
            result.items.append(AppliedAction(action, status, note, diff))

    result.pr_body = render_pr_body(repo.name, result)

    # 3 — dry-run stops here: print the diff summary and return
    if dry_run:
        return result

    # 4 — real run: guard rails before any write
    _ensure_clean_tree(repo)
    _prepare_branch(repo, branch)

    changed_items = [i for i in result.items if i.status is ApplyStatus.APPLIED]
    for item in changed_items:
        # new text is recoverable from the diff, but re-computing is cheaper
        # to reason about and guarantees what we write is what we diffed
        effective, _, new, note = _compute_change(repo, item.action)
        item.action = effective
        target = repo / effective.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if new is None:
            # became a skip between compute and write (e.g. another path shot first)
            item.status = ApplyStatus.SKIPPED
            item.detail = note.removeprefix("SKIP: ").removeprefix("NEEDS_REVIEW: ")
            item.diff = ""
            continue
        target.write_text(new, encoding="utf-8")

    result.commit_sha = _commit(repo, [i.action for i in result.items])
    if result.commit_sha is None:
        result.notes.append("no changes to commit — repo already aligned (idempotent run)")
    _write_pr_body(repo, result.pr_body)

    # 5 — never leave the repo on the alignment branch without telling anyone:
    # the caller (or the human) decides what happens next; we never push.
    result.notes.append(f"changes committed on {branch!r}; push and open a PR manually")
    return result


def format_summary(result: ApplyResult) -> str:
    """Human-readable summary of one apply result, with unified diffs."""
    mode = "DRY-RUN (no changes written)" if result.dry_run else "APPLIED"
    lines = [
        f"# szl-alignment apply — {mode}",
        f"repo: {result.repo_path}",
        f"branch: {result.branch}",
        "",
        (
            f"{len(result.items)} action(s): "
            f"{result.changed} change(s), {result.needs_review} need review, "
            f"{sum(1 for i in result.items if i.status is ApplyStatus.SKIPPED)} skipped"
        ),
    ]
    if result.commit_sha:
        lines.append(f"commit: {result.commit_sha}")
    for note in result.notes:
        lines.append(f"note: {note}")
    lines.append("")
    for item in result.items:
        lines.append(f"## [{item.status.value}] {item.action.kind.value} {item.action.path}")
        if item.detail:
            lines.append(f"    {item.detail}")
        if item.diff:
            lines.append("    " + item.diff.replace("\n", "\n    ").rstrip())
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "ApplyError",
    "AppliedAction",
    "ApplyResult",
    "ApplyStatus",
    "apply_plan",
    "format_summary",
    "render_pr_body",
]
