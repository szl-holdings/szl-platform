"""Alignment plans may not read or write through repository escape paths."""

import subprocess  # noqa: S404 — fixture-only fixed argv
from pathlib import Path

import pytest

from szl_alignment.apply import ApplyError, apply_plan
from szl_alignment.plan import Action, ActionKind


def _commit_fixture(repo: Path) -> None:
    for args in (
        ("add", "-A"),
        (
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "fixture symlink",
        ),
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)  # noqa: S603


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize(
    "layout", ["readme", "alternate_readme", "dangling_readme", "workflow_parent"]
)
def test_symlink_paths_are_rejected_before_git_or_file_changes(git_repo, tmp_path, dry_run, layout):
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "protected.md"
    if layout != "dangling_readme":
        victim.write_text("# External file\nuntouched\n", encoding="utf-8")
    before = victim.read_bytes() if victim.exists() else None
    if layout == "workflow_parent":
        (git_repo / ".github").symlink_to(outside, target_is_directory=True)
        action = Action(
            ActionKind.ADD_WORKFLOW,
            ".github/workflows/ci.yml",
            "workflows/base-python-ci.yml",
            "fixture",
        )
    else:
        (git_repo / "README.md").unlink()
        name = "readme.md" if layout == "alternate_readme" else "README.md"
        (git_repo / name).symlink_to(victim)
        action = Action(ActionKind.UPDATE_README_HEADER, "README.md", "README_HEADER.md", "fixture")
    _commit_fixture(git_repo)
    with pytest.raises(ApplyError, match="unsafe alignment path"):
        apply_plan(git_repo, [action], dry_run=dry_run)
    assert (victim.read_bytes() if victim.exists() else None) == before
    assert not (outside / "workflows").exists()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=git_repo,  # noqa: S603
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == "main"


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize(
    "target",
    [
        "../outside.md",
        "/outside.md",
        ".git/config",
        "a/../b",
        "a//b",
        "a\\b",
        "C:/escape.md",
        "bad\x00path",
    ],
)
def test_invalid_plan_paths_rejected_before_io(git_repo, monkeypatch, dry_run, target):
    def unexpected(*args, **kwargs):
        pytest.fail("unsafe path reached content or git operations")

    monkeypatch.setattr("szl_alignment.apply.template_text", unexpected)
    monkeypatch.setattr("szl_alignment.apply._prepare_branch", unexpected)
    action = Action(ActionKind.ADD_FILE, target, "SECURITY.md", "fixture")
    with pytest.raises(ApplyError, match="unsafe alignment path"):
        apply_plan(git_repo, [action], dry_run=dry_run)


def test_review_only_action_does_not_follow_symlink(bare_repo, tmp_path):
    external = tmp_path / "outside.md"
    external.write_text("outside", encoding="utf-8")
    (bare_repo / "linked.md").symlink_to(external)
    action = Action(ActionKind.FIX_FORBIDDEN, "linked.md", "", "review")
    with pytest.raises(ApplyError, match="unsafe alignment path"):
        apply_plan(bare_repo, [action])


def test_safe_missing_nested_parents_still_supported(git_repo):
    action = Action(ActionKind.ADD_FILE, "new/nested/SECURITY.md", "SECURITY.md", "fixture")
    result = apply_plan(git_repo, [action], dry_run=False)
    assert result.changed == 1
    assert (git_repo / action.path).is_file()
