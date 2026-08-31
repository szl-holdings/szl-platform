"""Builder tests: assembly, per-section digests, hard compile gates, and the
end-to-end run over the real sections/ doctrine tree."""

from __future__ import annotations

import hashlib

import pytest
from conftest import (
    DNS_OK,
    DNS_TOKENS,
    PACKAGE_ROOT,
    REAL_SECTIONS_DIR,
    TRAIN_OK,
    TRAIN_TOKENS,
)

from szl_payload import gates
from szl_payload.builder import BuildError, compile_payload, section_comment, sha256_bytes
from szl_payload.manifest import load_manifest

REAL_TREE_AVAILABLE = (PACKAGE_ROOT / "manifest.toml").is_file() and REAL_SECTIONS_DIR.is_dir()
requires_real_tree = pytest.mark.skipif(
    not REAL_TREE_AVAILABLE, reason="real sections/ doctrine tree not present"
)


class TestCompileHappyPath:
    def test_output_written_with_section_comments(self, pkg, std_sections):
        manifest = load_manifest(pkg(std_sections))
        result = compile_payload(manifest)
        assert result.output_path.is_file()
        document = result.output_path.read_text(encoding="utf-8")
        for section in manifest.sections:
            digest = hashlib.sha256(
                (manifest.root / section.path).read_bytes()
            ).hexdigest()
            assert section_comment(section.id, digest) in document

    def test_sections_appear_in_manifest_order(self, pkg, std_sections):
        manifest = load_manifest(pkg(std_sections))
        document = compile_payload(manifest).document
        positions = [document.index(f"<!-- section:{s.id} ") for s in manifest.sections]
        assert positions == sorted(positions)

    def test_payload_digest_is_over_output_bytes(self, pkg, std_sections):
        manifest = load_manifest(pkg(std_sections))
        result = compile_payload(manifest)
        on_disk = result.output_path.read_bytes()
        assert result.payload_sha256 == hashlib.sha256(on_disk).hexdigest()

    def test_build_has_no_timestamp_or_randomness(self, pkg, std_sections):
        # Pure function of sections+manifest: two compiles agree byte-for-byte.
        manifest = load_manifest(pkg(std_sections))
        assert compile_payload(manifest).document == compile_payload(manifest).document

    def test_no_writes_on_gate_failure(self, pkg, std_sections):
        root = pkg(std_sections[:2])  # no train section, but poison the DNS body
        dns_file = root / "sections" / "phase_neg1_dns.md"
        dns_file.write_text(DNS_OK + '\nbackdoor: sha256("SZLHOLDINGS/SZL-1".encode())\n')
        manifest = load_manifest(root)
        with pytest.raises(gates.GateViolation):
            compile_payload(manifest)
        assert not manifest.output_file.exists(), "a failed compile must not write output"


class TestCompileGates:
    def test_missing_must_contain_token_fails_section(self, pkg):
        root = pkg([("phase_neg1_dns", "# DNS\nno tokens here\n", DNS_TOKENS)])
        manifest = load_manifest(root)
        with pytest.raises(gates.GateViolation) as excinfo:
            compile_payload(manifest)
        gates_found = {f.gate for f in excinfo.value.findings}
        assert "must_contain" in gates_found
        missing = "\n".join(f.message for f in excinfo.value.findings)
        assert "/user/tokens/verify" in missing and "1033" in missing

    def test_train_before_dns_fails_compile(self, pkg):
        # The spec scenario: a crafted manifest with train before DNS.
        root = pkg(
            [
                ("phase7_train_sft", TRAIN_OK, TRAIN_TOKENS),
                ("phase_neg1_dns", DNS_OK, DNS_TOKENS),
            ]
        )
        manifest = load_manifest(root)
        with pytest.raises(gates.GateViolation) as excinfo:
            compile_payload(manifest)
        gate_names = {f.gate for f in excinfo.value.findings}
        assert "require_dns_first" in gate_names
        assert not manifest.output_file.exists()

    def test_require_dns_first_disabled_allows_order(self, pkg):
        root = pkg(
            [
                ("phase7_train_sft", TRAIN_OK, TRAIN_TOKENS),
                ("phase_neg1_dns", DNS_OK, DNS_TOKENS),
            ],
            require_dns_first=False,
        )
        manifest = load_manifest(root)
        result = compile_payload(manifest)
        assert result.sections[0].id == "phase7_train_sft"

    def test_forbidden_pattern_in_output_fails_with_line_number(self, pkg, std_sections):
        root = pkg(std_sections)
        doctor = root / "sections" / "phase0_doctor.md"
        body = doctor.read_text(encoding="utf-8") + "\nsee also a11oy.com archive\n"
        doctor.write_text(body, encoding="utf-8")
        manifest = load_manifest(root)
        with pytest.raises(gates.GateViolation) as excinfo:
            compile_payload(manifest)
        forbidden = [f for f in excinfo.value.findings if f.gate == "forbidden"]
        assert forbidden
        # The finding names the built output and the exact line the match sits on.
        assert forbidden[0].location.startswith("dist/SZL_MASTER_PAYLOAD_V14.md:")
        line_no = int(forbidden[0].location.rsplit(":", 1)[1])
        assert line_no > 1, "the offending line must be reported, not a blanket failure"

    def test_missing_section_file_is_operational_error(self, tmp_path):
        (tmp_path / "lint").mkdir()
        (tmp_path / "sections").mkdir()
        from conftest import lint_text

        (tmp_path / "lint" / "forbidden.txt").write_text(lint_text("forbidden.txt"))
        (tmp_path / "lint" / "banned_claims.txt").write_text(lint_text("banned_claims.txt"))
        (tmp_path / "manifest.toml").write_text(
            '[output]\npath = "dist/out.md"\n'
            '[export]\ndir = "dist/export"\nembed_build_time_in_body = false\n'
            'publication_eligible = false\n'
            '[gates]\nrequire_dns_first = false\n'
            'forbidden_patterns = "lint/forbidden.txt"\n'
            'banned_claims = "lint/banned_claims.txt"\n'
            '[[sections]]\nid = "ghost"\npath = "sections/ghost.md"\nmust_contain = []\n',
            encoding="utf-8",
        )
        manifest = load_manifest(tmp_path)
        with pytest.raises(BuildError, match="file not found"):
            compile_payload(manifest)


class TestDigestCommentFormat:
    def test_comment_format_exact(self):
        digest = sha256_bytes(b"abc")
        assert section_comment("phase_neg1_dns", digest) == (
            f"<!-- section:phase_neg1_dns sha256:{digest} -->"
        )


@requires_real_tree
class TestRealDoctrineTree:
    """End-to-end: the shipped sections/ must compile clean per the contract."""

    def test_real_sections_compile_clean_and_contain_contract_tokens(self):
        manifest = load_manifest(PACKAGE_ROOT)
        result = compile_payload(manifest, write=False)
        document = result.document
        assert len(result.sections) == 13
        assert result.sections[0].id == "phase_neg1_dns"
        assert "1033" in document
        assert "BLOCKERS THAT OUTRANK ALL COSMETIC WORK" in document
        assert "/user/tokens/verify" in document
        assert 'importance_sampling_level="sequence"' in document

    def test_real_tree_passes_all_output_gates(self):
        manifest = load_manifest(PACKAGE_ROOT)
        result = compile_payload(manifest, write=False)
        findings = gates.run_output_gates(manifest, result.document, manifest.output_path)
        assert findings == [], f"real tree must be gate-clean: {[f.render() for f in findings]}"

    def test_real_tree_safe_defaults_in_every_section(self):
        manifest = load_manifest(PACKAGE_ROOT)
        block = "AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false"
        for section in manifest.sections:
            text = (PACKAGE_ROOT / section.path).read_text(encoding="utf-8")
            assert block in text, f"{section.id} is missing the safe-defaults block"
