"""Manifest contract tests: explicit order, no globs, fail-closed validation."""

from __future__ import annotations

import pytest
from conftest import DNS_OK, DNS_TOKENS, GENERIC_OK, GENERIC_TOKENS, TRAIN_OK

from szl_payload import gates
from szl_payload.manifest import ManifestError, load_manifest


class TestManifestLoads:
    def test_valid_manifest_round_trips(self, pkg, std_sections):
        root = pkg(std_sections)
        manifest = load_manifest(root)
        assert manifest.section_ids == ("phase_neg1_dns", "phase0_doctor", "phase7_train_sft")
        assert manifest.output_path == "dist/SZL_MASTER_PAYLOAD_V14.md"
        assert manifest.export_dir == "dist/export"
        assert manifest.embed_build_time_in_body is False
        assert manifest.publication_eligible is False
        assert manifest.require_dns_first is True
        assert manifest.sections[0].must_contain == tuple(DNS_TOKENS)

    def test_section_order_is_exactly_manifest_order(self, pkg, std_sections):
        # Order is doctrine: the loaded tuple must mirror the file, unsorted.
        root = pkg(std_sections)
        manifest = load_manifest(root)
        ids = [section.id for section in manifest.sections]
        assert ids == ["phase_neg1_dns", "phase0_doctor", "phase7_train_sft"]


class TestManifestRejects:
    def test_missing_manifest(self, tmp_path):
        with pytest.raises(ManifestError, match="manifest not found"):
            load_manifest(tmp_path)

    def test_malformed_toml(self, tmp_path):
        (tmp_path / "manifest.toml").write_text("not = [toml", encoding="utf-8")
        with pytest.raises(ManifestError, match="cannot parse"):
            load_manifest(tmp_path)

    def test_glob_path_rejected(self, tmp_path):
        # A glob silently reorders and DNS stops being Phase -1: reject it.
        (tmp_path / "manifest.toml").write_text(
            '[output]\npath = "dist/out.md"\n'
            '[export]\ndir = "dist/export"\nembed_build_time_in_body = false\n'
            'publication_eligible = false\n'
            '[gates]\nrequire_dns_first = true\n'
            'forbidden_patterns = "lint/forbidden.txt"\n'
            'banned_claims = "lint/banned_claims.txt"\n'
            '[[sections]]\nid = "x"\npath = "sections/*.md"\nmust_contain = []\n',
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="glob"):
            load_manifest(tmp_path)

    def test_empty_sections_rejected(self, tmp_path):
        (tmp_path / "manifest.toml").write_text(
            '[output]\npath = "dist/out.md"\n'
            '[export]\ndir = "dist/export"\nembed_build_time_in_body = false\n'
            'publication_eligible = false\n'
            '[gates]\nrequire_dns_first = true\n'
            'forbidden_patterns = "lint/forbidden.txt"\n'
            'banned_claims = "lint/banned_claims.txt"\n'
            'sections = []\n',
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="non-empty explicit ordered list"):
            load_manifest(tmp_path)

    def test_duplicate_section_id_rejected(self, pkg, std_sections):
        root = pkg(std_sections + [("phase0_doctor", GENERIC_OK, GENERIC_TOKENS)])
        with pytest.raises(ManifestError, match="duplicate section id"):
            load_manifest(root)

    def test_embed_build_time_true_rejected(self, tmp_path):
        # The determinism doctrine: a timestamped body voids idempotency.
        (tmp_path / "manifest.toml").write_text(
            '[output]\npath = "dist/out.md"\n'
            '[export]\ndir = "dist/export"\nembed_build_time_in_body = true\n'
            'publication_eligible = false\n'
            '[gates]\nrequire_dns_first = true\n'
            'forbidden_patterns = "lint/forbidden.txt"\n'
            'banned_claims = "lint/banned_claims.txt"\n'
            '[[sections]]\nid = "x"\npath = "sections/x.md"\nmust_contain = []\n',
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="embed_build_time_in_body"):
            load_manifest(tmp_path)


class TestRequireDnsFirst:
    """The ordering gate itself (unit level; end-to-end craft is in test_builder)."""

    def test_train_before_dns_fails(self):
        findings = gates.check_dns_first(("phase7_train_sft", "phase_neg1_dns"))
        assert len(findings) == 1
        assert findings[0].gate == "require_dns_first"
        assert "phase7_train_sft" in findings[0].message

    def test_dns_before_train_passes(self):
        assert gates.check_dns_first(("phase_neg1_dns", "phase7_train_sft")) == []

    def test_missing_dns_section_fails(self):
        findings = gates.check_dns_first(("phase0_doctor", "phase7_train_sft"))
        assert len(findings) == 1
        assert "absent" in findings[0].message

    def test_train_rl_also_gated(self):
        findings = gates.check_dns_first(("phase8_train_rl", "phase_neg1_dns"))
        assert len(findings) == 1

    def test_gate_disabled_by_manifest_flag(self, pkg, std_sections):
        root = pkg(std_sections, require_dns_first=False)
        manifest = load_manifest(root)
        texts = {
            "phase_neg1_dns": ("sections/phase_neg1_dns.md", DNS_OK),
            "phase0_doctor": ("sections/phase0_doctor.md", GENERIC_OK),
            "phase7_train_sft": ("sections/phase7_train_sft.md", TRAIN_OK),
        }
        # With the flag off, section gates only run must_contain.
        assert gates.run_section_gates(manifest, texts) == []
        assert set(DNS_TOKENS) and manifest.require_dns_first is False
