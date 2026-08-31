"""Tests for szl_alignment.inspect — measurement must be exact and never raise."""

from __future__ import annotations

import os
from pathlib import Path

from szl_alignment.const import HEADER_MARKER
from szl_alignment.inspect import LicenseKind, inspect_repo, scan_forbidden


def test_bare_repo_missing_everything(bare_repo: Path) -> None:
    r = inspect_repo(bare_repo)
    assert r.has_readme is True
    assert r.has_license is False
    assert r.license_kind == LicenseKind.NONE.value
    assert r.has_security is False
    assert r.has_contributing is False
    assert r.has_coc is False
    assert r.has_pr_template is False
    assert r.has_issue_templates is False
    assert r.ci_workflows == []
    assert r.python_detected is False
    assert r.typescript_detected is False
    assert r.doctrine_header_present is False
    assert r.header_marker_present is False
    assert r.true_violations == []
    # missing LICENSE is reported as advice, not an action
    assert any("LICENSE" in q for q in r.open_questions)


def test_nonexistent_path_never_raises(tmp_path: Path) -> None:
    r = inspect_repo(tmp_path / "does-not-exist")
    assert r.has_readme is False
    assert r.true_violations == []
    assert any("does not exist" in q for q in r.open_questions)


def test_file_instead_of_dir_never_raises(tmp_path: Path) -> None:
    f = tmp_path / "a-file.py"
    f.write_text("x = 1\n", encoding="utf-8")
    r = inspect_repo(f)
    assert r.true_violations == []
    assert any("not a directory" in q for q in r.open_questions)


def test_license_sniffing_apache(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "LICENSE").write_text(
        "\n                                 Apache License\n"
        "                           Version 2.0, January 2004\n",
        encoding="utf-8",
    )
    r = inspect_repo(tmp_path / "r")
    assert r.has_license is True
    assert r.license_kind == LicenseKind.APACHE_2.value
    assert r.license_file == "LICENSE"


def test_license_sniffing_szl_proprietary(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "LICENSE").write_text(
        "SPDX-License-Identifier: LicenseRef-SZL-Proprietary\n\n"
        "Copyright (c) 2024-2026 SZL Holdings. All rights reserved.\n",
        encoding="utf-8",
    )
    r = inspect_repo(tmp_path / "r")
    assert r.has_license is True
    assert r.license_kind == LicenseKind.SZL_PROPRIETARY.value


def test_license_sniffing_unknown_kind(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "LICENSE").write_text("MIT License\n\nsome MIT text\n", encoding="utf-8")
    r = inspect_repo(tmp_path / "r")
    assert r.has_license is True
    assert r.license_kind == LicenseKind.UNKNOWN.value
    assert any("unrecognized" in q for q in r.open_questions)


def test_license_sniffing_missing(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    r = inspect_repo(tmp_path / "r")
    assert r.has_license is False
    assert r.license_kind == LicenseKind.NONE.value
    assert r.license_file is None


def test_language_detection_pyproject_and_sources(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    r = inspect_repo(tmp_path / "pkg")
    assert r.python_detected is True


def test_language_detection_deep_py_file(tmp_path: Path) -> None:
    deep = tmp_path / "deep" / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "tool.py").write_text("print('x')\n", encoding="utf-8")
    r = inspect_repo(tmp_path / "deep")
    assert r.python_detected is True
    assert r.typescript_detected is False


def test_language_detection_typescript(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "web" / "src").mkdir()
    (tmp_path / "web" / "src" / "app.tsx").write_text("export {};\n", encoding="utf-8")
    r = inspect_repo(tmp_path / "web")
    assert r.typescript_detected is True
    assert r.python_detected is False


def test_ci_workflows_listed_sorted(tmp_path: Path) -> None:
    wf = tmp_path / "r" / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "zeta.yml").write_text("name: z\n", encoding="utf-8")
    (wf / "alpha.yaml").write_text("name: a\n", encoding="utf-8")
    (wf / "not-a-workflow.txt").write_text("no\n", encoding="utf-8")
    r = inspect_repo(tmp_path / "r")
    assert r.ci_workflows == ["alpha.yaml", "zeta.yml"]


def test_doctrine_header_and_marker(complete_repo: Path) -> None:
    r = inspect_repo(complete_repo)
    assert r.doctrine_header_present is True
    assert r.header_marker_present is True


def test_marker_only_counts_for_plan_not_doctrine(tmp_path: Path) -> None:
    """A README with just the marker but no doctrine line: marker drives idempotency."""
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "README.md").write_text(
        f"# r\n\n{HEADER_MARKER}\n", encoding="utf-8"
    )
    r = inspect_repo(tmp_path / "r")
    assert r.header_marker_present is True
    assert r.doctrine_header_present is False


# ---------------------------------------------------------------------------
# forbidden-domain classification — the rule validated on the live org
# ---------------------------------------------------------------------------


def _write_lines(tmp_path: Path, lines: list[str]) -> Path:
    repo = tmp_path / "scan"
    repo.mkdir()
    (repo / "f.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return repo


def test_forbidden_true_violation_line(tmp_path: Path) -> None:
    repo = _write_lines(tmp_path, ['url = "https://a11oy.com/path"'])
    scan = scan_forbidden(repo)
    assert len(scan.violations) == 1
    assert scan.violations[0].file == "f.py"
    assert scan.violations[0].line == 1
    assert scan.guard_mentions == 0


def test_forbidden_never_line_is_guard(tmp_path: Path) -> None:
    repo = _write_lines(tmp_path, ["# Never a11oy.com — doctrine says so"])
    scan = scan_forbidden(repo)
    assert scan.violations == []
    assert scan.guard_mentions == 1


def test_forbidden_assertnotin_line_is_guard(tmp_path: Path) -> None:
    repo = _write_lines(tmp_path, ['assertNotIn("a11oy.com", rendered)  # guard'])
    scan = scan_forbidden(repo)
    assert scan.violations == []
    assert scan.guard_mentions == 1


def test_forbidden_mixed_lines(tmp_path: Path) -> None:
    repo = _write_lines(
        tmp_path,
        [
            'host: "a11oy.com",',  # violation
            "# never a11oy.com",  # guard
            'assert "a11oy.com" not in text',  # guard ('not in')
            '`a11oy.com` is not a surface of this project.',  # guard
            'canon = "https://a-11-oy.com"',  # canonical: no hit at all
        ],
    )
    scan = scan_forbidden(repo)
    assert len(scan.violations) == 1
    assert scan.violations[0].text.startswith('host:')
    assert scan.guard_mentions == 3


def test_canonical_domain_never_matches(tmp_path: Path) -> None:
    """a-11-oy.com and a11oy.net must never trip the gate."""
    repo = _write_lines(tmp_path, ['x = "https://a-11-oy.com" and "https://a11oy.net"'])
    scan = scan_forbidden(repo)
    assert scan.violations == []
    assert scan.guard_mentions == 0


def test_git_dir_never_scanned(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / ".git" / "objects").mkdir(parents=True)
    (repo / ".git" / "cached").mkdir()
    (repo / ".git" / "cached" / "blob.py").write_text('x = "a11oy.com"\n', encoding="utf-8")
    scan = scan_forbidden(repo)
    assert scan.violations == []


def test_skipped_files_are_counted(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "blob.bin").write_bytes(os.urandom(2048))  # non-text extension: ignored silently
    big = repo / "big.md"
    big.write_bytes(b"a" * (1_048_576 + 10))  # oversized text file: counted as skipped
    scan = scan_forbidden(repo)
    assert scan.files_skipped >= 1
    assert scan.violations == []
