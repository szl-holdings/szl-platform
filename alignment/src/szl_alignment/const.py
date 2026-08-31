"""Shared constants for the szl-alignment engine.

Everything the whole estate agrees on lives here so the modules, templates
and tests can never drift apart: the forbidden-domain rule, the doctrine
header marker, license labels, and standard target paths.

Control before action. Evidence after.
"""

from __future__ import annotations

import re

__version__ = "14.0.0"

# ---------------------------------------------------------------------------
# The forbidden-domain rule (release-blocking CRITICAL, validated on the live
# org and mirrored 1:1 into templates/workflows/forbidden-domain.yml).
#
# ``(?<!-)`` keeps the canonical product surface ``a-11-oy.com`` from ever
# matching (a hyphen immediately precedes ``a11oy`` there... actually the
# canonical name inserts hyphens *inside* the string, so it never contains
# the contiguous ``a11oy.com`` at all), while still catching the bare
# lookalike inside URLs such as ``https://a11oy.com`` and excluding
# hyphen-prefixed variants like ``my-a11oy.com``.
FORBIDDEN_PATTERN = r"(?<!-)a11oy\.com"
FORBIDDEN_RE = re.compile(FORBIDDEN_PATTERN)

# A forbidden-regex hit is ALLOWED when the same line is a prohibition/guard
# context — doctrine notes, blocklist entries, guard assertions.
ALLOWLIST_PATTERN = (
    r"never|forbidden|not in|assertNotIn|does not appear|is not a surface|blocklist"
)
ALLOWLIST_RE = re.compile(ALLOWLIST_PATTERN, re.IGNORECASE)

# ---------------------------------------------------------------------------
# Doctrine header. HEADER_MARKER is the idempotency marker embedded in
# templates/README_HEADER.md; DOCTRINE_LINE is the sentence that defines
# "header present" semantically (RepoReport.doctrine_header_present).
HEADER_MARKER = "<!-- szl:header v1 -->"
DOCTRINE_LINE = "Control before action"

# ---------------------------------------------------------------------------
# License classification labels (RepoReport.license_kind). Licenses are legal
# statements and are NEVER written by this tool — only detected here.
LICENSE_UNKNOWN = "UNKNOWN"
LICENSE_APACHE = "APACHE_2"
LICENSE_SZL_PROP = "SZL_PROPRIETARY"
LICENSE_NONE = "NONE"  # no license file found at all

# Candidate license file names at the repo root, in sniff order.
LICENSE_CANDIDATES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING")

# ---------------------------------------------------------------------------
# Alignment infrastructure target paths, relative to the repo root.
SECURITY_PATH = "SECURITY.md"
CONTRIBUTING_PATH = "CONTRIBUTING.md"
COC_PATH = "CODE_OF_CONDUCT.md"
PR_TEMPLATE_PATH = ".github/PULL_REQUEST_TEMPLATE.md"
ISSUE_TEMPLATES_DIR = ".github/ISSUE_TEMPLATE"
WORKFLOWS_DIR = ".github/workflows"
BASE_PYTHON_CI_PATH = ".github/workflows/base-python-ci.yml"
FORBIDDEN_DOMAIN_PATH = ".github/workflows/forbidden-domain.yml"
SUGGESTED_LICENSE_PATH = "LICENSE"

# Languages: extensions used by the source detectors.
PY_EXTENSIONS = frozenset({".py", ".pyi", ".pyx"})
TS_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"})

# Forbidden-scan text extensions (lowercase, dot-prefixed). Extensionless
# files are skipped — the gate's job is source/docs/config, not binaries.
TEXT_SCAN_EXTENSIONS = frozenset(
    {
        ".md", ".txt", ".rst", ".adoc",
        ".py", ".pyi", ".pyx",
        ".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs",
        ".json", ".jsonc", ".json5",
        ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".conf",
        ".html", ".htm", ".xml", ".css", ".scss", ".less", ".svg",
        ".go", ".rs", ".java", ".c", ".h", ".cpp", ".hpp", ".cs",
        ".rb", ".sh", ".bash", ".zsh", ".ps1",
        ".sql", ".graphql", ".proto", ".tf", ".hcl",
    }
)

# Directories never traversed by any walk. ``.git`` mirrors the CI gate's
# ``--hidden --glob '!.git'``; the rest are generated/dependency trees.
# ``dist``/``build`` are deliberately NOT skipped: checked-in artifacts are
# real surfaces (the live org's violations included published JSON copies).
SKIP_SCAN_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", ".tox", ".mypy_cache", ".pytest_cache",
        "node_modules", "__pycache__", "venv", ".venv",
        ".next", ".nuxt", "coverage", ".nyc_output",
    }
)

# Forbidden scan file size cap. Larger files are counted as skipped (and
# surfaced as an open question) rather than silently half-scanned.
MAX_FILE_BYTES = 1_048_576  # 1 MiB

# The canonical alignment branch (never the default branch, never force-pushed).
ALIGNMENT_BRANCH = "szl/alignment-v14"

# Workflow file name the planner requires to consider base Python CI present.
BASE_CI_NAME = "base-python-ci.yml"

# Canonical estate surfaces, linked from the doctrine header.
PRODUCT_URL = "https://a-11-oy.com"
PROOF_URL = "https://a11oy.net"
ORG_URL = "https://github.com/szl-holdings"
