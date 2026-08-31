"""szl-alignment — the org alignment engine for the szl-holdings estate.

Control before action. Evidence after.

The package is deliberately layered:

- :mod:`szl_alignment.const`   — shared constants (regexes, markers, paths).
- :mod:`szl_alignment.inspect` — read-only measurement of one repo.
- :mod:`szl_alignment.plan`    — deterministic RepoReport -> [Action].
- :mod:`szl_alignment.apply`   — dry-run diffs; optional branch+commit apply.
- :mod:`szl_alignment.report`  — org-level matrix + markdown report.
- :mod:`szl_alignment.cli`     — ``python -m szl_alignment``.
"""

from szl_alignment.const import (
    ALLOWLIST_PATTERN,
    FORBIDDEN_PATTERN,
    HEADER_MARKER,
    __version__,
)
from szl_alignment.inspect import ForbiddenScan, RepoReport, Violation, inspect_repo
from szl_alignment.plan import Action, ActionKind, plan_alignment

__all__ = [
    "ALLOWLIST_PATTERN",
    "FORBIDDEN_PATTERN",
    "HEADER_MARKER",
    "Action",
    "ActionKind",
    "ForbiddenScan",
    "RepoReport",
    "Violation",
    "__version__",
    "inspect_repo",
    "plan_alignment",
]
