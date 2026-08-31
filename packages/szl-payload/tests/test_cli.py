"""CLI tests: stage dispatch, exit codes (0/2/3), --json output, and the
verify stage's gate-failure behavior end to end."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from conftest import DNS_OK, DNS_TOKENS, EXTRACT_OK, EXTRACT_TOKENS, PACKAGE_ROOT

from szl_payload.cli import EXIT_GATE_FAILED, EXIT_OK, EXIT_OPERATIONAL_ERROR, main

TEMPLATES_DIR = PACKAGE_ROOT / "templates"


@pytest.fixture
def cli_pkg(pkg):
    """Synthetic package with templates copied in so export can render."""

    def _make(sections, *, require_dns_first: bool = True) -> Path:
        root = pkg(sections, require_dns_first=require_dns_first)
        shutil.copytree(TEMPLATES_DIR, root / "templates")
        return root

    return _make


GOOD_SECTIONS = [
    ("phase_neg1_dns", DNS_OK, DNS_TOKENS),
    ("phase0_scaffold", EXTRACT_OK, EXTRACT_TOKENS),
]


class TestStageDispatch:
    def test_default_command_is_all(self, cli_pkg, capsys):
        root = cli_pkg(GOOD_SECTIONS)
        assert main(["--root", str(root)]) == EXIT_OK
        out = capsys.readouterr().out
        assert (root / "dist" / "SZL_MASTER_PAYLOAD_V14.md").is_file()
        assert (root / "dist" / "export" / "export_manifest.unsigned.json").is_file()
        assert "PASS" in out

    def test_generate_then_compile(self, cli_pkg):
        root = cli_pkg(GOOD_SECTIONS)
        assert main(["generate", "--root", str(root)]) == EXIT_OK
        assert not (root / "dist").exists(), "generate writes nothing"
        assert main(["compile", "--root", str(root)]) == EXIT_OK
        assert (root / "dist" / "SZL_MASTER_PAYLOAD_V14.md").is_file()

    def test_json_flag_emits_parseable_json(self, cli_pkg, capsys):
        root = cli_pkg(GOOD_SECTIONS)
        assert main(["compile", "--root", str(root), "--json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["stage"] == "compile"
        assert len(payload["payload_sha256"]) == 64


class TestExitCodes:
    def test_gate_failure_exits_2(self, cli_pkg, capsys):
        poisoned = DNS_OK + "\nprint(TOKEN)\n"
        root = cli_pkg([("phase_neg1_dns", poisoned, DNS_TOKENS)])
        assert main(["compile", "--root", str(root)]) == EXIT_GATE_FAILED
        err = capsys.readouterr().err
        assert "GATE FAILURE" in err
        assert "forbidden" in err

    def test_operational_error_exits_3(self, tmp_path, capsys):
        assert main(["compile", "--root", str(tmp_path)]) == EXIT_OPERATIONAL_ERROR
        assert "manifest not found" in capsys.readouterr().err

    def test_gate_failure_json_still_exits_2(self, cli_pkg, capsys):
        poisoned = DNS_OK + "\nprint(TOKEN)\n"
        root = cli_pkg([("phase_neg1_dns", poisoned, DNS_TOKENS)])
        assert main(["compile", "--root", str(root), "--json"]) == EXIT_GATE_FAILED
        payload = json.loads(capsys.readouterr().out)
        assert payload["error"] == "gate_violation"
        assert payload["finding_count"] >= 1


class TestVerify:
    def _build(self, cli_pkg, root_sections=GOOD_SECTIONS):
        root = cli_pkg(root_sections)
        assert main(["all", "--root", str(root)]) == EXIT_OK
        return root

    def test_verify_clean_build_passes(self, cli_pkg):
        root = self._build(cli_pkg)
        assert main(["verify", "--root", str(root)]) == EXIT_OK

    def test_verify_detects_section_edit_after_build(self, cli_pkg):
        root = self._build(cli_pkg)
        dns = root / "sections" / "phase_neg1_dns.md"
        dns.write_text(dns.read_text(encoding="utf-8") + "\nanother 1033 mention\n")
        assert main(["verify", "--root", str(root)]) == EXIT_GATE_FAILED

    def test_verify_detects_forbidden_domain_in_dist(self, cli_pkg):
        root = self._build(cli_pkg)
        (root / "dist" / "leak.md").write_text("oops: a11oy.com\n", encoding="utf-8")
        assert main(["verify", "--root", str(root)]) == EXIT_GATE_FAILED

    def test_verify_detects_bare_manifest_sibling(self, cli_pkg):
        root = self._build(cli_pkg)
        honest = root / "dist" / "export" / "export_manifest.unsigned.json"
        (root / "dist" / "export" / "export_manifest.json").write_bytes(honest.read_bytes())
        assert main(["verify", "--root", str(root)]) == EXIT_GATE_FAILED

    def test_verify_detects_tampered_signatures(self, cli_pkg):
        root = self._build(cli_pkg)
        manifest_path = root / "dist" / "export" / "export_manifest.unsigned.json"
        obj = json.loads(manifest_path.read_text(encoding="utf-8"))
        obj["signatures"] = [{"keyid": "x", "sig": "y"}]
        manifest_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        assert main(["verify", "--root", str(root)]) == EXIT_GATE_FAILED

    def test_verify_detects_tampered_publication_eligible(self, cli_pkg):
        root = self._build(cli_pkg)
        manifest_path = root / "dist" / "export" / "export_manifest.unsigned.json"
        obj = json.loads(manifest_path.read_text(encoding="utf-8"))
        obj["publication_eligible"] = True
        manifest_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        assert main(["verify", "--root", str(root)]) == EXIT_GATE_FAILED

    def test_verify_without_build_is_operational(self, cli_pkg):
        root = cli_pkg(GOOD_SECTIONS)
        assert main(["verify", "--root", str(root)]) == EXIT_OPERATIONAL_ERROR
