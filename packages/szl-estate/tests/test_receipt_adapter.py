"""Tests for the receipt adapter's documented degradation boundary.

The fallback path is real behavior — an explicitly unsigned, honestly named
file — so it is asserted rigorously, not skipped.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest
from szl_estate import receipt_adapter as ra
from szl_estate.receipt_adapter import UNSIGNED_NOTE


class TestUnsignedFallback:
    def test_unsigned_file_is_honestly_named(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ra, "receipts_available", lambda: False)
        out = ra.emit_receipt(
            tmp_path / "enumerate-2026-08-31",
            action="enumerate",
            outcome="COMPLETE",
            subjects=["szl-holdings/a11oy"],
            evidence={"repo_count": 100},
        )
        assert out.name.endswith(".unsigned.json"), "unsigned artifacts must SAY unsigned"
        body = json.loads(out.read_text())
        assert body["signatures"] == [], "an empty signatures array, never elided"
        assert body["note"] == UNSIGNED_NOTE  # exact doctrine wording, asserted
        assert body["action"] == "enumerate"
        assert body["outcome"] == "COMPLETE"
        assert body["subjects"] == ["szl-holdings/a11oy"]
        assert body["evidence"]["repo_count"] == 100
        assert body["schema"] == ra.SCHEMA

    def test_signed_emit_failure_still_degrades_honestly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ra, "receipts_available", lambda: True)

        def fail_emit(path_base, body):  # noqa: ANN001, ANN202
            raise RuntimeError("signing key unavailable")

        module = types.ModuleType("szl_receipts")
        module.emit_receipt = fail_emit
        monkeypatch.setitem(sys.modules, "szl_receipts", module)

        out = ra.emit_receipt(tmp_path / "audit", "audit", "DONE", ["x"], {})
        assert out.name.endswith(".unsigned.json")
        body = json.loads(out.read_text())
        assert body["signatures"] == []
        assert "signing key unavailable" in body["note"]
        # The generic unsigned note must not mask the real failure reason.
        assert body["note"] != UNSIGNED_NOTE


class TestSignedPath:
    def test_write_envelope_fallback_uses_honest_naming(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A szl_receipts exposing only write_envelope: unsigned body must land
        in an unsigned-named file, because the envelope carries no signatures."""

        def fake_write_envelope(path_base, envelope, *, overwrite=True):  # noqa: ANN001, ANN201, ARG001
            suffix = ".json" if envelope.get("signatures") else ".unsigned.json"
            out = Path(str(path_base) + suffix)
            out.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")
            return out

        module = types.ModuleType("szl_receipts")
        module.write_envelope = fake_write_envelope
        monkeypatch.setitem(sys.modules, "szl_receipts", module)

        out = ra.emit_receipt(
            tmp_path / "enum", "enumerate", "COMPLETE", ["szl-holdings/a11oy"], {"n": 1}
        )
        assert out.name.endswith(".unsigned.json"), "no signatures -> honest unsigned name"
        body = json.loads(out.read_text())
        assert body["signatures"] == []
        assert body["action"] == "enumerate"

    def test_szl_receipts_is_used_when_importable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[tuple[str, dict]] = []

        def fake_emit(path_base: str, body: dict) -> str:
            captured.append((path_base, body))
            written = Path(path_base + ".signed.json")
            signed = dict(body)
            signed["signatures"] = [{"keyid": "testkey", "sig": "deadbeef"}]
            written.write_text(json.dumps(signed))
            return str(written)

        module = types.ModuleType("szl_receipts")
        module.emit_receipt = fake_emit
        monkeypatch.setitem(sys.modules, "szl_receipts", module)
        monkeypatch.setattr(ra, "receipts_available", lambda: True)

        out = ra.emit_receipt(tmp_path / "r", "audit", "DONE", ["szl-holdings/x"], {"k": "v"})
        assert out.name == "r.signed.json"
        assert captured[0][1]["action"] == "audit"
        body = json.loads(out.read_text())
        assert body["signatures"] != [], "the signed path must produce real signatures"

    def test_availability_reflects_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A module already in sys.modules IS importable, whatever the disk says.
        monkeypatch.setitem(sys.modules, "szl_receipts", types.ModuleType("szl_receipts"))
        assert ra.receipts_available() is True
        # Absence is environment-dependent (szl-receipts may be installed as a
        # sibling), so absence is simulated by forcing find_spec to come up
        # empty — deterministic on every machine.
        monkeypatch.delitem(sys.modules, "szl_receipts")
        monkeypatch.setattr(ra.importlib.util, "find_spec", lambda name: None)
        assert ra.receipts_available() is False
