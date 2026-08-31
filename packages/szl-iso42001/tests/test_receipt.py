"""Receipt emission tests — both modes.

Mode A (always runs): szl_receipts absent. Simulated by monkeypatching the
receipt module's import seam to raise ImportError, exactly as a machine
without the sibling package would behave. The receipt must still be written,
honestly named `readiness-receipt.unsigned.json`, with empty signatures.

Mode B (skips cleanly in this sandbox): szl_receipts installed. Uses
pytest.importorskip so the test silently skips where the library is absent
and runs for real where it is present (e.g. the full monorepo CI).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import szl_iso42001.receipt as receipt_mod
from szl_iso42001 import __version__
from szl_iso42001.controls import load_controls
from szl_iso42001.receipt import UNSIGNED_RECEIPT_NAME, emit_receipt, sha256_text
from szl_iso42001.report import render_report
from szl_iso42001.score import score_answers

REPORT = "# test report body\n"
ANSWERS = {"ISO42001-A2-01": "yes", "ISO42001-C4-03": "no"}


def _kwargs():
    return {
        "band": "PARTIAL",
        "counts": {"yes": 1, "partial": 0, "no": 1, "unknown": 42},
        "control_count": 44,
        "tool_version": __version__,
    }


# ---------------------------------------------------------------------------
# Mode A — unsigned path (library absent)
# ---------------------------------------------------------------------------

def test_unsigned_receipt_when_library_missing(tmp_path, monkeypatch):
    def _no_library():
        raise ImportError("No module named 'szl_receipts' (simulated)")

    monkeypatch.setattr(receipt_mod, "_import_szl_receipts", _no_library)

    info = emit_receipt(REPORT, ANSWERS, tmp_path, **_kwargs())

    assert info["signed"] is False
    path = Path(info["path"])
    assert path.name == UNSIGNED_RECEIPT_NAME
    assert path.exists()

    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["signatures"] == []  # present AND empty — honest by construction
    assert body["subjects"][0]["sha256"] == sha256_text(REPORT)
    assert body["subjects"][0]["name"] == "readiness-report.md"
    assert body["band"] == "PARTIAL"
    assert body["control_count"] == 44
    assert body["answer_counts"] == {"yes": 1, "partial": 0, "no": 1, "unknown": 42}
    assert "UNSIGNED" in body["note"].upper()
    assert info["sha256"] == sha256_text(REPORT)


def test_unsigned_receipt_hash_matches_report_roundtrip(tmp_path, monkeypatch):
    """The core product claim, tested end-to-end: hash in receipt == hash of report."""
    monkeypatch.setattr(
        receipt_mod,
        "_import_szl_receipts",
        lambda: (_ for _ in ()).throw(ImportError("simulated")),
    )
    controls = load_controls()
    answers = {c.id: "partial" for c in controls}
    result = score_answers(answers, controls)
    report_md = render_report(result)

    info = emit_receipt(
        report_md, answers, tmp_path,
        band=result.band, counts=result.counts,
        control_count=result.control_count, tool_version=__version__,
    )
    body = json.loads(Path(info["path"]).read_text(encoding="utf-8"))

    # An independent recomputation, as an auditor would do:
    import hashlib

    recomputed = hashlib.sha256(report_md.encode("utf-8")).hexdigest()
    assert body["subjects"][0]["sha256"] == recomputed


def test_unsigned_receipt_is_deterministic_modulo_timestamp(tmp_path, monkeypatch):
    monkeypatch.setattr(
        receipt_mod,
        "_import_szl_receipts",
        lambda: (_ for _ in ()).throw(ImportError("simulated")),
    )
    def emit_once() -> dict:
        info = emit_receipt(REPORT, ANSWERS, tmp_path, **_kwargs())
        return json.loads(Path(info["path"]).read_text(encoding="utf-8"))

    first = emit_once()
    second = emit_once()
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_emit_receipt_creates_out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        receipt_mod,
        "_import_szl_receipts",
        lambda: (_ for _ in ()).throw(ImportError("simulated")),
    )
    nested = tmp_path / "deep" / "nested" / "out"
    info = emit_receipt(REPORT, ANSWERS, nested, **_kwargs())
    assert Path(info["path"]).exists()


# ---------------------------------------------------------------------------
# Mode B — signed-style path (library present); skips cleanly when absent
# ---------------------------------------------------------------------------

def test_signed_receipt_when_library_present(tmp_path):
    szl_receipts = pytest.importorskip(
        "szl_receipts", reason="szl_receipts not installed in this sandbox"
    )
    # If we get here, the real library exists — drive its real API.
    assert hasattr(szl_receipts, "receipt")
    info = emit_receipt(REPORT, ANSWERS, tmp_path, **_kwargs())
    assert Path(info["path"]).exists()
    assert info["sha256"] == sha256_text(REPORT)


def test_signed_path_api_drift_falls_back_honestly(tmp_path, monkeypatch):
    """If a future szl_receipts changes its API beyond our adapter, we must
    NOT crash or emit a malformed 'signed' artifact — we fall back to the
    honestly-named unsigned receipt and annotate why."""

    class _DriftedReceiptModule:
        @staticmethod
        def build_receipt(**kwargs):  # raises TypeError on our call shape
            raise TypeError("drifted API")

    class _DriftedLibrary:
        receipt = _DriftedReceiptModule

    monkeypatch.setattr(receipt_mod, "_import_szl_receipts", lambda: _DriftedLibrary)

    info = emit_receipt(REPORT, ANSWERS, tmp_path, **_kwargs())
    assert info["signed"] is False
    body = json.loads(Path(info["path"]).read_text(encoding="utf-8"))
    assert body["signatures"] == []
    assert "TypeError" in body["note"]
