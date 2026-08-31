"""Tests for szl_alignment.plan — deterministic, rule-driven action lists."""

from __future__ import annotations

from pathlib import Path

from szl_alignment.inspect import inspect_repo
from szl_alignment.plan import ActionKind, plan_alignment


def _kinds(plan):
    return [a.kind for a in plan]


def _paths(plan):
    return {a.path for a in plan}


def test_bare_repo_gets_full_plan(bare_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(bare_repo))
    kinds = _kinds(plan)
    paths = _paths(plan)

    # the full complement of governance + gates
    assert ActionKind.UPDATE_README_HEADER in kinds
    assert ActionKind.ADD_FILE in kinds
    assert ActionKind.ADD_WORKFLOW in kinds

    assert "SECURITY.md" in paths
    assert "CONTRIBUTING.md" in paths
    assert "CODE_OF_CONDUCT.md" in paths
    assert ".github/PULL_REQUEST_TEMPLATE.md" in paths
    assert ".github/ISSUE_TEMPLATE/bug_report.yml" in paths
    assert ".github/ISSUE_TEMPLATE/config.yml" in paths
    assert ".github/workflows/forbidden-domain.yml" in paths


def test_complete_repo_gets_empty_plan(complete_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(complete_repo))
    assert plan == []


def test_license_never_planned(bare_repo: Path) -> None:
    """A missing LICENSE is advice-only, never an action."""
    plan = plan_alignment(inspect_repo(bare_repo))
    assert "LICENSE" not in _paths(plan)
    assert all("LICENSE" not in a.template for a in plan)
    report = inspect_repo(bare_repo)
    assert any("LICENSE" in q for q in report.open_questions)


def test_python_repo_gets_base_ci(python_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(python_repo))
    assert ".github/workflows/base-python-ci.yml" in _paths(plan)


def test_python_repo_with_python_named_ci_skipped(tmp_path: Path) -> None:
    """Existing CI named like the base gate means no duplicate."""
    wf = tmp_path / "r" / ".github" / "workflows"
    wf.mkdir(parents=True)
    (tmp_path / "r" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (wf / "python-ci.yml").write_text("name: python-ci\n", encoding="utf-8")
    plan = plan_alignment(inspect_repo(tmp_path / "r"))
    assert ".github/workflows/base-python-ci.yml" not in _paths(plan)


def test_python_repo_with_base_ci_skipped(tmp_path: Path) -> None:
    wf = tmp_path / "r" / ".github" / "workflows"
    wf.mkdir(parents=True)
    (tmp_path / "r" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (wf / "base-python-ci.yml").write_text("name: base-python-ci\n", encoding="utf-8")
    plan = plan_alignment(inspect_repo(tmp_path / "r"))
    assert ".github/workflows/base-python-ci.yml" not in _paths(plan)


def test_non_python_repo_gets_no_base_ci(bare_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(bare_repo))
    assert ".github/workflows/base-python-ci.yml" not in _paths(plan)


def test_forbidden_gate_added_to_every_repo(bare_repo: Path, complete_repo: Path) -> None:
    assert ".github/workflows/forbidden-domain.yml" in _paths(
        plan_alignment(inspect_repo(bare_repo))
    )
    # complete repo already has it -> not planned again
    assert ".github/workflows/forbidden-domain.yml" not in _paths(
        plan_alignment(inspect_repo(complete_repo))
    )


def test_fix_forbidden_per_true_violation(command_lab_repo: Path) -> None:
    plan = plan_alignment(inspect_repo(command_lab_repo))
    fixes = [a for a in plan if a.kind is ActionKind.FIX_FORBIDDEN]
    # the publish.ts fixture flags 2 violations; the two publish-map.json
    # copies flag 1 each, like on the live org
    assert len(fixes) == 4
    for fix in fixes:
        assert fix.needs_review is True
        assert fix.template == ""
        assert "MUST be reviewed" in fix.reason
        assert "a-11-oy.com" in fix.reason
    assert {f.path for f in fixes} == {
        "src/lib/publish.ts",
        "src/data/publish-map.json",
        "public/data/publish-map.json",
    }
    assert sum(1 for f in fixes if f.path == "src/lib/publish.ts") == 2


def test_guard_mentions_produce_no_fix_actions(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "policy.py").write_text(
        'assertNotIn("a11oy.com", out)  # never the lookalike\n', encoding="utf-8"
    )
    plan = plan_alignment(inspect_repo(tmp_path / "r"))
    assert ActionKind.FIX_FORBIDDEN not in _kinds(plan)


def test_plan_is_deterministic(command_lab_repo: Path) -> None:
    report = inspect_repo(command_lab_repo)
    plan_a = plan_alignment(report)
    plan_b = plan_alignment(report)
    assert plan_a == plan_b


def test_header_not_planned_when_marker_present(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "README.md").write_text(
        "# r\n\n<!-- szl:header v1 -->\n...rest...\n", encoding="utf-8"
    )
    plan = plan_alignment(inspect_repo(tmp_path / "r"))
    assert ActionKind.UPDATE_README_HEADER not in _kinds(plan)


def test_every_action_has_reason_and_path(bare_repo: Path) -> None:
    for action in plan_alignment(inspect_repo(bare_repo)):
        assert action.path, action
        assert action.reason, action
