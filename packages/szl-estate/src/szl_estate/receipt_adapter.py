"""Optional integration with the sibling `szl-receipts` signing package.

THIS MODULE IS A DOCUMENTED DEGRADATION BOUNDARY — NOT A MOCK, NOT A STUB.

Two honest modes, chosen at runtime:

  1. ``szl_receipts`` is importable  ->  receipts are emitted through it and
     carry real signatures. The exact call goes through a narrow adapter
     (:func:`_emit_signed`) so the estate package never hard-depends on the
     receipts package being installed.
  2. ``szl_receipts`` is NOT importable  ->  we write
     ``<path_base>.unsigned.json`` ourselves, with ``"signatures": []``
     spelled out explicitly and a note stating, in the filename and in the
     body, that the artifact is unsigned. An unsigned artifact named
     "unsigned" is honest; an unsigned artifact named "receipt" would be a lie.

The fallback is real, reviewable behavior — the file exists, is parseable,
and says exactly what it is — so it is tested like everything else.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

#: Written verbatim into every unsigned receipt. Tests assert this string.
UNSIGNED_NOTE = "szl-receipts not installed; unsigned by honest naming"

#: Schema marker so downstream tooling can tell adapter receipts apart.
SCHEMA = "szl-estate.receipt/v1"


def receipts_available() -> bool:
    """True iff the sibling szl-receipts package is importable.

    find_spec consults sys.modules first; a fake module injected by a test may
    carry no __spec__, which makes find_spec raise ValueError — treat that as
    "present", because an importable module in sys.modules IS importable.
    """
    if "szl_receipts" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("szl_receipts") is not None
    except (ImportError, ValueError):
        return False


def _emit_signed(path_base: Path, body: dict[str, Any]) -> Path:
    """Route through szl-receipts. Imported lazily so this module loads even
    when the sibling package is absent.

    Contract, kept deliberately small and checked against the real package:
    prefer a module-level ``emit_receipt(path_base, payload) -> path`` hook
    when the receipts package offers one; otherwise build a DSSE-style
    envelope around the body and hand it to ``szl_receipts.write_envelope``,
    which itself chooses the honest filename (``.json`` iff at least one
    signature exists, else ``.unsigned.json``). The adapter never fabricates
    signatures: ``body['signatures']`` starts empty and flows truthfully into
    whichever writer the receipts package provides. Anything else raises,
    and the caller falls back to the unsigned path with the failure recorded.
    """
    import szl_receipts  # type: ignore[import-not-found]

    emit = getattr(szl_receipts, "emit_receipt", None)
    if callable(emit):
        return Path(emit(str(path_base), body))
    write_envelope = getattr(szl_receipts, "write_envelope", None)
    if callable(write_envelope):
        envelope = {**body, "signatures": body.get("signatures", [])}
        return Path(write_envelope(path_base, envelope))
    raise RuntimeError("szl_receipts exposes neither emit_receipt nor write_envelope")


def emit_receipt(
    path_base: str | Path,
    action: str,
    outcome: str,
    subjects: list[str],
    evidence: dict[str, Any],
) -> Path:
    """Emit a receipt for one control-plane action; degrade honestly.

    Returns the path actually written. When szl-receipts is unavailable (or
    its emit call fails), the path ends in ``.unsigned.json`` and the body
    carries ``"signatures": []`` plus an explicit note. Callers must treat the
    returned filename as part of the evidence: presence of ``unsigned`` means
    no signature was ever produced.
    """
    path_base = Path(path_base)
    path_base.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "action": action,
        "outcome": outcome,
        "subjects": list(subjects),
        "evidence": dict(evidence),
        # Explicit emptiness from the start: the signer may fill this list,
        # but the adapter never invents an entry.
        "signatures": [],
    }
    if receipts_available():
        try:
            return _emit_signed(path_base, body)
        except Exception as exc:  # noqa: BLE001 — degrade, record, continue
            body["note"] = (
                f"szl-receipts importable but emit failed: {exc}; unsigned by honest naming"
            )
        # Fall through to the unsigned write below.
    else:
        body["note"] = UNSIGNED_NOTE
    out = path_base.with_name(path_base.name + ".unsigned.json")
    out.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
