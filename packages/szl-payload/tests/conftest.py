"""Shared fixtures: synthetic package trees (in tmp_path) + real-tree paths.

Gate tests run against small synthetic sections in tmp_path so each test
controls exactly the text under scrutiny. End-to-end tests run against the
real sections/ tree only when it is present (the package ships it; the
skip guards keep unit tests runnable from a bare checkout of src/ alone).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the package importable when tests run from its directory without an
# install (pyproject pythonpath covers the repo-root invocation; this covers
# `pytest tests/` from the package dir).
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

RECEIPTS_SRC = PACKAGE_ROOT.parent / "szl-receipts" / "src"
if RECEIPTS_SRC.is_dir() and str(RECEIPTS_SRC) not in sys.path:
    sys.path.insert(0, str(RECEIPTS_SRC))

#: The real doctrine tree (used by end-to-end tests).
REAL_SECTIONS_DIR = PACKAGE_ROOT / "sections"

# Lint defaults mirroring lint/forbidden.txt + lint/banned_claims.txt. The
# real files are preferred when present so tests exercise shipped rules.
FORBIDDEN_DEFAULT = """\
# forbidden patterns
sha256\\(\\s*["'][A-Za-z0-9_/-]+["']\\s*\\.encode\\(\\)\\s*\\)
"sig"\\s*:\\s*""
keyid"\\s*:\\s*"PENDING-SIGSTORE
specVersion"\\s*:\\s*"1\\.6"
api/collections\\?author=
print\\([^)]*(TOKEN|SECRET|API_KEY|PAT)\\b
(?<!-)a11oy\\.com
"""

BANNED_DEFAULT = """\
# banned claims
first governance kernel
state of the art
production-ready
world.?first
signed within 200 chars of unsigned\\.json
"""


def lint_text(name: str) -> str:
    """Lint file content — real file when present, embedded mirror otherwise."""
    real = PACKAGE_ROOT / "lint" / name
    if real.is_file():
        return real.read_text(encoding="utf-8")
    return FORBIDDEN_DEFAULT if name == "forbidden.txt" else BANNED_DEFAULT


#: Canonical synthetic section bodies: satisfy their own must_contain tokens
#: and never trip forbidden/banned gates.
DNS_OK = (
    "# Phase -1 DNS\n\n"
    "/user/tokens/verify · Zone:DNS:Edit · 185.199.108.153 · hf.space · HSTS · rollback · 1033\n"
)
DNS_TOKENS = [
    "/user/tokens/verify",
    "Zone:DNS:Edit",
    "185.199.108.153",
    "hf.space",
    "HSTS",
    "rollback",
    "1033",
]
TRAIN_OK = (
    "# Phase 7 Train SFT\n\n"
    "baseline-first: run the unmodified base on the sealed suite; the delta is the only claim.\n"
)
TRAIN_TOKENS = ["baseline-first", "unmodified base", "sealed suite", "delta is the only claim"]
GENERIC_OK = "# Phase 0 Doctor\n\nBLOCKERS THAT OUTRANK ALL COSMETIC WORK\n"
GENERIC_TOKENS = ["BLOCKERS THAT OUTRANK ALL COSMETIC WORK"]

EXTRACT_OK = (
    "# Scaffold\n\n"
    "<!-- extract: scaffold/run.sh mode=755 -->\n"
    "```bash\n"
    "echo scaffold-ok\n"
    "```\n"
    "\n"
    "<!-- extract: configs/policy.json mode=644 -->\n"
    "```json\n"
    '{"cyclonedx_spec_version": "1.7"}\n'
    "```\n"
)
EXTRACT_TOKENS = ["scaffold"]


def toml_quote(value: str) -> str:
    """Quote a string as a TOML basic string (JSON syntax is a subset)."""
    return json.dumps(value)


def write_package(
    root: Path,
    sections: list[tuple[str, str, list[str]]],
    *,
    require_dns_first: bool = True,
) -> Path:
    """Write a complete synthetic package (manifest + sections + lint) to *root*.

    *sections* is a list of (id, body_text, must_contain_tokens) in manifest
    order. Returns *root*.
    """
    (root / "sections").mkdir(parents=True, exist_ok=True)
    (root / "lint").mkdir(parents=True, exist_ok=True)
    (root / "lint" / "forbidden.txt").write_text(lint_text("forbidden.txt"), encoding="utf-8")
    (root / "lint" / "banned_claims.txt").write_text(
        lint_text("banned_claims.txt"), encoding="utf-8"
    )

    lines = [
        '[output]',
        'path = "dist/SZL_MASTER_PAYLOAD_V14.md"',
        "",
        "[export]",
        'dir = "dist/export"',
        "embed_build_time_in_body = false",
        "publication_eligible = false",
        "",
        "[gates]",
        f"require_dns_first = {'true' if require_dns_first else 'false'}",
        'forbidden_patterns = "lint/forbidden.txt"',
        'banned_claims = "lint/banned_claims.txt"',
        "",
    ]
    for section_id, body, tokens in sections:
        filename = f"sections/{section_id}.md"
        (root / filename).write_text(body, encoding="utf-8")
        token_list = ", ".join(toml_quote(token) for token in tokens)
        lines += [
            "[[sections]]",
            f"id = {toml_quote(section_id)}",
            f"path = {toml_quote(filename)}",
            f"must_contain = [{token_list}]",
            "",
        ]
    (root / "manifest.toml").write_text("\n".join(lines), encoding="utf-8")
    return root


@pytest.fixture
def pkg(tmp_path):
    """Factory: write a synthetic package into tmp_path, return its root."""

    def _make(sections, *, require_dns_first: bool = True) -> Path:
        return write_package(tmp_path, sections, require_dns_first=require_dns_first)

    return _make


@pytest.fixture
def std_sections():
    """The canonical three-section synthetic package content."""
    return [
        ("phase_neg1_dns", DNS_OK, DNS_TOKENS),
        ("phase0_doctor", GENERIC_OK, GENERIC_TOKENS),
        ("phase7_train_sft", TRAIN_OK, TRAIN_TOKENS),
    ]
