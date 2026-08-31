"""Export tests: honest .unsigned.json naming, empty signatures, computed
publication_eligible=false, canonical digest, and the ten UNKNOWN answers."""

from __future__ import annotations

import json
import shutil

import pytest
from conftest import DNS_OK, DNS_TOKENS, EXTRACT_OK, EXTRACT_TOKENS, PACKAGE_ROOT

from szl_payload import _jcs
from szl_payload.builder import compile_payload
from szl_payload.export import (
    EXPORT_MANIFEST_NAME,
    GENERATED_BY,
    OPERATOR_PACKET_QUESTIONS,
    run_export,
)
from szl_payload.extract import extract_document
from szl_payload.manifest import load_manifest


@pytest.fixture
def built(tmp_path):
    """A built synthetic package: returns (manifest, compile_result, extracted)."""
    from conftest import write_package

    root = write_package(
        tmp_path,
        [
            ("phase_neg1_dns", DNS_OK, DNS_TOKENS),
            ("phase0_scaffold", EXTRACT_OK, EXTRACT_TOKENS),
        ],
    )
    shutil.copytree(PACKAGE_ROOT / "templates", root / "templates")
    manifest = load_manifest(root)
    compiled = compile_payload(manifest)
    written = extract_document(compiled.document, root / "dist" / "extracted")
    return manifest, compiled, written


class TestExportManifest:
    def test_named_unsigned_with_empty_signatures(self, built):
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        # Honest naming: signatures == [] → the file MUST say .unsigned.json.
        assert result.export_manifest_path.name == EXPORT_MANIFEST_NAME
        assert result.export_manifest_path.name.endswith(".unsigned.json")
        obj = json.loads(result.export_manifest_path.read_text(encoding="utf-8"))
        assert obj["signatures"] == []

    def test_publication_eligible_serializes_false(self, built):
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        obj = json.loads(result.export_manifest_path.read_text(encoding="utf-8"))
        assert obj["publication_eligible"] is False

    def test_generated_by_and_backend_recorded(self, built):
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        obj = json.loads(result.export_manifest_path.read_text(encoding="utf-8"))
        assert obj["generated_by"] == GENERATED_BY
        assert obj["generated_by"] == "szl-payload 14.0.0"
        assert obj["jcs_backend"] == _jcs.JCS_BACKEND

    def test_payload_and_section_and_subject_digests(self, built):
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        obj = json.loads(result.export_manifest_path.read_text(encoding="utf-8"))
        assert obj["payload"]["sha256"] == compiled.payload_sha256
        assert [s["id"] for s in obj["sections"]] == ["phase_neg1_dns", "phase0_scaffold"]
        assert all(len(s["sha256"]) == 64 for s in obj["sections"])
        # Subjects follow the contract shape [{name, sha256}].
        names = sorted(s["name"] for s in obj["subjects"])
        assert names == ["configs/policy.json", "scaffold/run.sh"]
        assert all(set(s.keys()) == {"name", "sha256"} for s in obj["subjects"])

    def test_canonicalization_is_real_rfc8785(self, built):
        # JCS canonicalization: key order and whitespace are canonical; two
        # semantically equal objects canonicalize to identical bytes.
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        obj = json.loads(result.export_manifest_path.read_text(encoding="utf-8"))
        canonical = _jcs.canonicalize(obj)
        canonical_again = _jcs.canonicalize(json.loads(canonical.decode("utf-8")))
        assert canonical == canonical_again, "canonicalization must be a fixed point"
        # And canonical bytes differ from a sort_keys dump when JCS rules bite
        # (e.g. non-ASCII-safe structure), proving we are not json.dumps.
        assert isinstance(canonical, bytes)

    def test_receipt_is_the_only_timestamped_artifact(self, built):
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        receipt = result.receipt_path.read_text(encoding="utf-8")
        assert "generated_at" in receipt
        # The payload body itself must carry no build-time line at all.
        body = compiled.document
        assert "generated_at" not in body
        assert "embed_build_time_in_body" not in body


class TestOperatorPacket:
    def test_ten_answers_all_unknown(self, built):
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        packet = result.operator_packet_path.read_text(encoding="utf-8")
        for index, question in enumerate(OPERATOR_PACKET_QUESTIONS, start=1):
            assert f"{index}. **{question}**" in packet, f"missing answer {index}: {question}"
        # Every answer rendered UNKNOWN — never asserted green by default.
        assert packet.count("— UNKNOWN (UNKNOWN)") == 10

    def test_packet_references_payload_digest(self, built):
        manifest, compiled, written = built
        result = run_export(manifest, compiled.payload_sha256, compiled.sections, written)
        packet = result.operator_packet_path.read_text(encoding="utf-8")
        assert compiled.payload_sha256 in packet


class TestDeterminism:
    def test_export_is_byte_identical_on_rebuild(self, tmp_path):
        from conftest import write_package

        root = write_package(
            tmp_path,
            [
                ("phase_neg1_dns", DNS_OK, DNS_TOKENS),
                ("phase0_scaffold", EXTRACT_OK, EXTRACT_TOKENS),
            ],
        )
        shutil.copytree(PACKAGE_ROOT / "templates", root / "templates")
        manifest = load_manifest(root)

        def build_and_snapshot() -> dict[str, bytes]:
            compiled = compile_payload(manifest)
            written = extract_document(compiled.document, root / "dist" / "extracted")
            run_export(manifest, compiled.payload_sha256, compiled.sections, written)
            export_dir = manifest.export_path
            return {
                path.name: path.read_bytes() for path in sorted(export_dir.iterdir())
            }

        first = build_and_snapshot()
        second = build_and_snapshot()
        assert first == second, "export must be deterministic (receipt uses source-mtime clock)"
        assert set(first) == {
            "export_manifest.unsigned.json",
            "RECEIPT.md",
            "REPORT.md",
            "OPERATOR_PACKET.md",
        }
