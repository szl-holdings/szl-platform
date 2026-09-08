"""Regression contract for the estate-wide Python workflow template."""

from __future__ import annotations

from pathlib import Path


TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "workflows"
    / "base-python-ci.yml"
)


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_template_installs_the_optional_extra_that_is_actually_declared() -> None:
    workflow = _template()

    assert "import tomllib" in workflow
    assert 'for candidate in ("dev", "test", "tests")' in workflow
    assert 'python -m pip install -e ".[${extra}]"' in workflow
    assert "if [ -n \"$extra\" ]; then" in workflow

    # This was the estate-wide bug: test/tests matched the regex, but the
    # workflow always installed a non-existent `dev` extra.
    assert "grep -qE '^\\s*(dev|test|tests)" not in workflow
    assert 'python -m pip install -e ".[dev]"' not in workflow


def test_template_preserves_fail_closed_defer_and_checkout_contracts() -> None:
    workflow = _template()

    assert workflow.count(".github/base-python-ci.defer") >= 4
    assert "must state a non-empty reason" in workflow
    assert "persist-credentials: false" in workflow
    assert "permissions:\n  contents: read" in workflow


def test_template_keeps_both_supported_python_versions_and_blocking_tests() -> None:
    workflow = _template()

    assert 'python-version: ["3.11", "3.12"]' in workflow
    assert 'name: "Ruff (blocking: E9/F)"' in workflow
    assert "pytest -q tests" in workflow
