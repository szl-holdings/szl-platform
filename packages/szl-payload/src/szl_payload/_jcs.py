"""RFC 8785 JCS canonicalization backend selection.

Doctrine (Phase 1, Defect 2): canonicalization uses a real RFC 8785 JCS
implementation — never ``json.dumps(sort_keys=True)``, whose number and
unicode serialization differ from ES6 semantics and would produce false
drift (and missed drift) downstream.

Backend order:

1. The pinned ``rfc8785`` distribution (``rfc8785==1.0.2`` per
   ``pyproject.toml``). This is the contracted dependency.
2. The estate's own stdlib-only implementation, ``szl_receipts.jcs`` from
   the sibling ``packages/szl-receipts`` package. Used when the pinned
   distribution cannot be installed in the build environment (offline
   mirrors may not carry it). ``szl_receipts.jcs`` implements the full ES6
   number rules, UTF-16 key ordering, and minimal string escaping.

Whichever backend is active, ``canonicalize`` returns canonical UTF-8 bytes:
same logical value in, same bytes out, forever.
"""

from __future__ import annotations

from typing import Any

JCS_BACKEND: str

try:  # Primary: the pinned rfc8785 distribution.
    import rfc8785 as _rfc8785

    JCS_BACKEND = "rfc8785"

    def canonicalize(obj: Any) -> bytes:
        """Canonical RFC 8785 UTF-8 bytes via the pinned rfc8785 package."""
        out = _rfc8785.canonicalize(obj)
        # The distribution has returned both str and bytes across releases;
        # normalize to bytes so digests are stable regardless.
        return out.encode("utf-8") if isinstance(out, str) else bytes(out)

except ImportError:  # Fallback: the estate implementation in szl-receipts.
    from szl_receipts.jcs import jcs_canon_bytes as _jcs_canon_bytes

    JCS_BACKEND = "szl_receipts.jcs"

    def canonicalize(obj: Any) -> bytes:
        """Canonical RFC 8785 UTF-8 bytes via szl_receipts.jcs."""
        return _jcs_canon_bytes(obj)
