"""Receipt emission for szl-iso42001 — the self-demonstrating part.

WHY THIS MODULE EXISTS (the product thesis, in comments for investors):
  This package is a FREE readiness checker. But it is also the demo of the
  thing SZL Holdings sells: tamper-evident provenance for AI-governance
  artifacts. A checker that tells you to "prove, don't assert" and then emits
  an unverifiable report would be a contradiction. So this tool receipts its
  own findings. If the sibling package `szl_receipts` is installed, the report
  is bound into a signed-style GovernedAction/v1 receipt. If it is not
  installed, the tool still writes a receipt — honestly NAMED
  `readiness-receipt.unsigned.json`, with an empty signatures array that is
  never called a signature.

  Either way, the report's sha256 is on disk next to the report, and any third
  party can re-hash the report and check the match. Provenance degrades
  gracefully, never silently.

Both write paths are deterministic in structure: keys are emitted in a fixed
order via explicit dict construction + sort_keys=False... except we DO sort
keys in the unsigned receipt so its bytes are stable for a given input.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Receipt format version emitted by this tool. Bumped only on breaking changes
# to the receipt body schema.
RECEIPT_KIND = "GovernedAction/v1"

# Honest filenames. The unsigned variant carries ".unsigned" in the name so no
# one ever mistakes it for a signed artifact (platform doctrine, rule 1).
UNSIGNED_RECEIPT_NAME = "readiness-receipt.unsigned.json"
SIGNED_RECEIPT_BASENAME = "readiness-receipt"


def sha256_bytes(data: bytes) -> str:
    """Lowercase hex sha256 of raw bytes — the one hash used everywhere here."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """sha256 of a string encoded as UTF-8 (reports are UTF-8 markdown)."""
    return sha256_bytes(text.encode("utf-8"))


def _import_szl_receipts() -> Any:
    """Import the optional sibling receipts library.

    Isolated into its own function so tests can monkeypatch exactly this seam:
    patching this function to raise ImportError simulates a machine without
    szl_receipts installed, exercising the honest-unsigned path.
    """
    import szl_receipts  # noqa: PLC0415 — optional dependency, imported lazily

    return szl_receipts


def emit_receipt(
    report_md: str,
    answers: dict[str, object],
    out_dir: str | Path,
    *,
    band: str,
    counts: dict[str, int],
    control_count: int,
    tool_version: str,
) -> dict[str, Any]:
    """Write a receipt for a readiness report into out_dir.

    Args:
        report_md: the full markdown report body (hashed into the receipt).
        answers: the raw answers mapping that produced the report. Only the
            *count by kind* lands in the receipt body — answers themselves can
            be commercially sensitive, so the receipt commits to the report
            hash, not to the answers.
        out_dir: directory to write into; created if missing.
        band / counts / control_count / tool_version: summary facts about the
            run, recorded so a receipt reader can sanity-check the report
            without parsing markdown.

    Returns:
        A dict describing what was written: {"path", "signed", "sha256", ...}.
        `signed` is a plain fact about which path ran — never a marketing claim.

    Behavior:
        * szl_receipts importable -> build a GovernedAction/v1 receipt through
          its API (subjects bind the report by sha256) and write per its naming
          rules.
        * ImportError -> write readiness-receipt.unsigned.json with the same
          core facts, an empty "signatures": [], and an explicit unsigned note.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report_hash = sha256_text(report_md)

    try:
        szl_receipts = _import_szl_receipts()
    except ImportError:
        return _emit_unsigned(
            out, report_hash, band, counts, control_count, tool_version
        )
    return _emit_signed(
        szl_receipts, out, report_hash, band, counts, control_count, tool_version
    )


def _emit_unsigned(
    out: Path,
    report_hash: str,
    band: str,
    counts: dict[str, int],
    control_count: int,
    tool_version: str,
) -> dict[str, Any]:
    """Fallback path: a self-describing, honestly-named unsigned receipt.

    The body deliberately mirrors the signed receipt's core fields so tooling
    can consume either shape. `signatures` is present and EMPTY — an absent key
    would be ambiguous; an empty array is an explicit statement.
    """
    body = {
        "kind": RECEIPT_KIND,
        "tool": f"szl-iso42001 {tool_version}",
        "generated_at": datetime.now(UTC).isoformat(),
        "band": band,
        "control_count": control_count,
        "answer_counts": {k: counts.get(k, 0) for k in ("yes", "partial", "no", "unknown")},
        "subjects": [
            {"name": "readiness-report.md", "sha256": report_hash},
        ],
        "signatures": [],
        "note": (
            "UNSIGNED RECEIPT. The sibling package 'szl_receipts' was not "
            "importable in this environment, so this receipt carries no "
            "cryptographic signature. It is still tamper-EVIDENT: re-hash "
            "readiness-report.md and compare against subjects[0].sha256. "
            "Install szl_receipts to get a signed-style GovernedAction/v1 "
            "receipt instead."
        ),
    }
    path = out / UNSIGNED_RECEIPT_NAME
    path.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "path": str(path),
        "signed": False,
        "sha256": report_hash,
        "kind": RECEIPT_KIND,
    }


def _emit_signed(
    szl_receipts: Any,
    out: Path,
    report_hash: str,
    band: str,
    counts: dict[str, int],
    control_count: int,
    tool_version: str,
) -> dict[str, Any]:
    """Signed-style path via the sibling receipts library.

    We call the library's own builder (szl_receipts.receipt.build_receipt) with
    subjects binding the report by hash, then let the library's naming rules
    pick the filename. We introspect the API rather than hard-coding its
    signature, because this package must keep working across szl_receipts
    minor versions — and if the API has drifted beyond what we can adapt to,
    we fall back to the honest unsigned path rather than crash.
    """
    try:
        receipt_module = szl_receipts.receipt
        build_receipt = receipt_module.build_receipt
        receipt = build_receipt(
            kind=RECEIPT_KIND,
            actor=f"szl-iso42001 {tool_version}",
            action="iso42001-readiness-assessment",
            subjects=[("readiness-report.md", report_hash)],
            metadata={
                "band": band,
                "control_count": control_count,
                "answer_counts": {
                    k: counts.get(k, 0) for k in ("yes", "partial", "no", "unknown")
                },
            },
        )
        # Ask the library for its canonical filename; if it exposes one, use
        # it, otherwise derive a conservative default.
        if hasattr(receipt_module, "receipt_filename"):
            filename = receipt_module.receipt_filename(receipt)
        else:
            rid = getattr(receipt, "id", None) or receipt.get("id", "receipt")
            filename = f"{SIGNED_RECEIPT_BASENAME}-{rid}.receipt.json"
        path = out / filename
        if hasattr(receipt_module, "write_receipt"):
            receipt_module.write_receipt(receipt, path)
        else:
            payload = (
                receipt
                if isinstance(receipt, dict)
                else getattr(receipt, "to_dict", lambda: vars(receipt))()
            )
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return {
            "path": str(path),
            "signed": True,
            "sha256": report_hash,
            "kind": RECEIPT_KIND,
        }
    except (AttributeError, TypeError, ValueError) as exc:
        # The receipts library is present but its API doesn't match what we
        # know how to drive. Honesty beats bravado: fall back to unsigned and
        # say why, rather than emit a malformed "signed" artifact.
        result = _emit_unsigned(
            out, report_hash, band, counts, control_count, tool_version
        )
        # Annotate the unsigned file's note via the returned path.
        note_extra = f" Signed-path attempt failed ({type(exc).__name__})."
        path = Path(result["path"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["note"] += note_extra
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result
