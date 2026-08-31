"""szl-estate — the estate control plane for the SZL Holdings orgs.

This package measures the estate; it never flatters it. Three doctrine rules
are encoded here and enforced by every module:

1. UNKNOWN is never PASS. Any probe that cannot produce a computed value
   degrades to UNKNOWN carrying its error — never to 0, never to silence.
2. Never assert a number you did not compute in this run. Counts are either
   computed here or labeled as quoted claims awaiting recomputation.
3. The forbidden domain ``a11oy.com`` anywhere in any repo file is a CRITICAL
   finding with code FORBIDDEN_LINK.
"""

from __future__ import annotations

import re

__version__ = "0.1.0"

# --- Doctrine rule 3: the forbidden link -------------------------------------
#
# The doctrine states the base pattern as ``(?<!-)a11oy\.com``. That base alone
# is NOT sufficient for the stated acceptance criteria: the negative lookbehind
# ``(?<!-)`` only rejects a hyphen prefix, so the base pattern would still match
# inside ``xa11oy.com`` (the ``a11oy.com`` there is preceded by ``x``, not `-`).
# ``xa11oy.com`` is a *different domain* that merely ends in our forbidden
# string, and the doctrine says it must NOT match. We therefore widen the
# lookbehind to ``[\w-]`` (any word character or hyphen):
#
#   * ``https://a11oy.com/x``  -> MATCH (preceded by '/')        -> CRITICAL
#   * bare ``a11oy.com``       -> MATCH (start / whitespace)     -> CRITICAL
#   * ``www.a11oy.com``        -> MATCH (preceded by '.')        -> CRITICAL
#   * ``a-11-oy.com``          -> no contiguous "a11oy.com" exists at all
#   * ``xa11oy.com``           -> rejected: 'a' preceded by word char 'x'
#   * ``a11oy.net``            -> different TLD, never matches
#
# Why is a11oy.com forbidden at all? It is an unrelated third-party site; the
# estate's real front doors are a-11-oy.com and a11oy.net. Linking the wrong
# domain in a repo README funnels users — and investors — to a property we do
# not control. Hence CRITICAL, hence FORBIDDEN_LINK.
FORBIDDEN_LINK_RE: re.Pattern[str] = re.compile(r"(?<![\w-])a11oy\.com")

#: Finding code emitted when FORBIDDEN_LINK_RE matches scanned content.
FORBIDDEN_LINK_CODE = "FORBIDDEN_LINK"

#: Finding severities, highest to lowest. Rollups list them in this order.
SEVERITIES: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

#: Per-repo overall states. UNKNOWN exists because a missing/unparseable
#: pushedAt must never be laundered into a guessed state.
REPO_STATES: tuple[str, ...] = ("ACTIVE", "ARCHIVED", "STALE", "EMPTY", "UNKNOWN")

#: Doctor check statuses. FATAL is not a status of its own; a fatal check is a
#: FAIL whose failure blocks the estate (see doctor.check_huggingface_hub).
CHECK_STATUSES: tuple[str, ...] = ("PASS", "WARN", "FAIL", "BLOCKED", "UNKNOWN")

#: The literal top header of every estate/doctor report. Cosmetic work is
#: forbidden from outranking blockers; putting them at the top is the encoding.
BLOCKERS_HEADER = "BLOCKERS THAT OUTRANK ALL COSMETIC WORK"

#: GitHub Pages serves apex/zone A records from exactly these four addresses.
#: a11oy.net is a GitHub Pages site, so its A set must be a subset of these.
GITHUB_PAGES_A_RECORDS: frozenset[str] = frozenset(
    {
        "185.199.108.153",
        "185.199.109.153",
        "185.199.110.153",
        "185.199.111.153",
    }
)

#: A repo whose last push is older than this many days is STALE (not ACTIVE).
STALE_DAYS = 180

__all__ = [
    "BLOCKERS_HEADER",
    "CHECK_STATUSES",
    "FORBIDDEN_LINK_CODE",
    "FORBIDDEN_LINK_RE",
    "GITHUB_PAGES_A_RECORDS",
    "REPO_STATES",
    "SEVERITIES",
    "STALE_DAYS",
    "__version__",
]
