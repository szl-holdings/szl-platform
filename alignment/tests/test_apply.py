"""Tests for szl_alignment.apply — dry-run purity, real apply, idempotency."""

from __future__ import annotations

import subprocess  # noqa: S404 — fixed-argv git plumbing in tests
from pathlib import Path

import pytest
from conftest import GIT_AVAILABLE  # pytest adds tests/ to sys.path

from szl_alignment.apply import ApplyStatus, apply_plan, format_summary
from szl_alignment.const import HEADER_MARKER
from szl_alignment.inspect import inspect_repo
from szl_alignment.plan import ActionKind, plan_alignment

needs_git = pytest.mark.skipif(not GIT_AVAILABLE, reason="git not on PATH")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _worktree_snapshot(repo: Path) -> dict[str, bytes | None]:
    """Capture paths and file bytes while excluding Git's transient internals."""
    snapshot: dict[str, bytes | None] = {}
    for path in repo.rglob("*"):
        relative = path.relative_to(repo)
        if relative.parts and relative.parts[0] == ".git":
            continue
        snapshot[relative.as_posix()] = path.read_bytes() if path.is_file() else None
    return snapshot


def test_dry_run_writes_nothing(git_repo: Path) -> None:
    before = _worktree_snapshot(git_repo)
    plan = plan_alignment(inspect_repo(git_repo))
    result = apply_plan(git_repo, plan, dry_run=True)
    after = _worktree_snapshot(git_repo)
    assert before == after  # dry-run must not alter worktree paths or bytes
    assert result.dry_run is True
    assert result.changed == len(plan)
    assert "DRY-RUN" in format_summary(result)


def test_dry_run_diffs_present(git_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(git_repo))
    result = apply_plan(git_repo, plan, dry_run=True)
    summary = format_summary(result)
    assert "+++ b/SECURITY.md" in summary
    assert "+# Security Policy" in summary
    # doctrine header diff inserts the marker into README.md
    assert HEADER_MARKER in summary


@needs_git
def test_real_apply_creates_branch_and_commit(git_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(git_repo))
    result = apply_plan(git_repo, plan, dry_run=False)
    assert result.commit_sha is not None
    assert _git(git_repo, "rev-parse", "--abbrev-ref", "HEAD") == "szl/alignment-v14"
    # files really landed
    assert (git_repo / "SECURITY.md").is_file()
    assert (git_repo / ".github" / "workflows" / "forbidden-domain.yml").is_file()
    assert HEADER_MARKER in (git_repo / "README.md").read_text(encoding="utf-8")
    # signed-off commit
    body = _git(git_repo, "log", "-1", "--format=%B")
    assert "Signed-off-by:" in body
    assert "chore(alignment)" in body
    # PR body stashed in .git (untracked)
    assert (git_repo / ".git" / "SZL_ALIGNMENT_PR_BODY.md").is_file()
    assert result.pr_body  # also returned for the caller


@needs_git
def test_idempotent_second_run(git_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(git_repo))
    apply_plan(git_repo, plan, dry_run=False)
    # second run: fresh plan on the now-aligned repo must be empty
    plan2 = plan_alignment(inspect_repo(git_repo))
    assert plan2 == []
    # ...and applying the ORIGINAL plan again is a no-op too
    result2 = apply_plan(git_repo, plan, dry_run=False)
    assert result2.changed == 0
    assert result2.commit_sha is None  # nothing staged -> no empty commit
    assert any("idempotent" in n for n in result2.notes)
    # dry-run of the stale plan also shows zero changes
    result3 = apply_plan(git_repo, plan, dry_run=True)
    assert result3.changed == 0


@needs_git
def test_never_touches_default_branch(git_repo: Path) -> None:
    main_sha_before = _git(git_repo, "rev-parse", "main")
    plan = plan_alignment(inspect_repo(git_repo))
    apply_plan(git_repo, plan, dry_run=False)
    main_sha_after = _git(git_repo, "rev-parse", "main")
    assert main_sha_before == main_sha_after  # alignment branch only


@needs_git
def test_existing_different_content_never_overwritten(git_repo: Path) -> None:
    (git_repo / "SECURITY.md").write_text("# custom policy\n", encoding="utf-8")
    _git(git_repo, "add", "-A")
    _git(git_repo, "-c", "user.name=t", "-c", "user.email=t@e.c", "commit", "-m", "custom security")
    plan = plan_alignment(inspect_repo(git_repo))
    assert any(a.path == "SECURITY.md" for a in plan) is False  # present -> not planned
    # construct the action manually to prove the guard works
    from szl_alignment.plan import Action

    manual = [Action(ActionKind.ADD_FILE, "SECURITY.md", "SECURITY.md", "forced")]
    result = apply_plan(git_repo, manual, dry_run=False)
    item = result.items[0]
    assert item.status is ApplyStatus.SKIPPED
    assert "NEVER overwritten" in item.detail
    assert (git_repo / "SECURITY.md").read_text(encoding="utf-8") == "# custom policy\n"


@needs_git
def test_fix_forbidden_needs_review_not_applied(command_lab_repo: Path, tmp_path: Path) -> None:
    _git_init(command_lab_repo)
    plan = plan_alignment(inspect_repo(command_lab_repo))
    result = apply_plan(command_lab_repo, plan, dry_run=False)
    review_items = [i for i in result.items if i.status is ApplyStatus.NEEDS_REVIEW]
    assert len(review_items) == 4  # publish.ts (2) + both publish-map.json copies
    # the file itself must be untouched — a human decides
    content = (command_lab_repo / "src" / "lib" / "publish.ts").read_text(encoding="utf-8")
    assert 'host: "a11oy.com",' in content
    assert 'href: "https://a11oy.com",' in content
    assert "NEEDS REVIEW" in result.pr_body
    assert "a-11-oy.com" in result.pr_body  # points the reviewer at the fix


@needs_git
def test_dirty_tree_refused(git_repo: Path) -> None:
    (git_repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    plan = plan_alignment(inspect_repo(git_repo))
    from szl_alignment.apply import ApplyError

    with pytest.raises(ApplyError, match="clean tree"):
        apply_plan(git_repo, plan, dry_run=False)


@needs_git
def test_header_inserted_after_first_h1(git_repo: Path) -> None:
    (git_repo / "README.md").write_text(
        "# git-repo\n\nIntro paragraph stays.\n", encoding="utf-8"
    )
    _git(git_repo, "add", "-A")
    _git(git_repo, "-c", "user.name=t", "-c", "user.email=t@e.c", "commit", "-m", "readme")
    plan = plan_alignment(inspect_repo(git_repo))
    apply_plan(git_repo, plan, dry_run=False)
    text = (git_repo / "README.md").read_text(encoding="utf-8")
    h1 = text.index("# git-repo")
    marker = text.index(HEADER_MARKER)
    intro = text.index("Intro paragraph stays.")
    assert h1 < marker < intro  # header after H1, before old body


def _git_init(repo: Path) -> None:
    subprocess.run(  # noqa: S603
        ["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True
    )
    subprocess.run(  # noqa: S603
        ["git", "add", "-A"], cwd=repo, check=True, capture_output=True, text=True
    )
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@e.c", "commit", "-m", "init"],
        cwd=repo, check=True, capture_output=True, text=True,
    )
