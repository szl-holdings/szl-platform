"""Extract tests: happy path, mode application, sha256 reporting, and the
extract-path escape security boundary (this document gets fed to agents)."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from conftest import EXTRACT_OK, EXTRACT_TOKENS

from szl_payload.builder import compile_payload, sha256_bytes
from szl_payload.extract import (
    ExtractError,
    extract_document,
    extract_payload,
    find_tags,
)
from szl_payload.manifest import load_manifest


def _doc_with_tag(relpath: str, mode: str, body: str = "payload-bytes") -> str:
    return (
        "# Doc\n\n"
        f"<!-- extract: {relpath} mode={mode} -->\n"
        "```python\n"
        f"{body}\n"
        "```\n"
    )


class TestHappyPath:
    def test_writes_files_with_mode_and_sha256(self, tmp_path):
        document = (
            _doc_with_tag("scaffold/run.sh", "755", body="echo one")
            + "\n"
            + _doc_with_tag("cfg/policy.json", "644", body='{"a": 1}')
        )
        dest = tmp_path / "dist" / "extracted"
        written = extract_document(document, dest)

        run_sh = dest / "scaffold" / "run.sh"
        policy = dest / "cfg" / "policy.json"
        assert run_sh.read_text(encoding="utf-8") == "echo one\n"
        assert policy.read_text(encoding="utf-8") == '{"a": 1}\n'
        assert stat.S_IMODE(run_sh.stat().st_mode) == 0o755
        assert stat.S_IMODE(policy.stat().st_mode) == 0o644
        by_path = {item.relpath: item for item in written}
        assert by_path["scaffold/run.sh"].sha256 == sha256_bytes(b"echo one\n")
        assert by_path["cfg/policy.json"].sha256 == sha256_bytes(b'{"a": 1}\n')
        assert by_path["scaffold/run.sh"].mode == 0o755

    def test_find_tags_parses_without_language_fence_issues(self):
        tags = find_tags(EXTRACT_OK)
        assert [t.relpath for t in tags] == ["scaffold/run.sh", "configs/policy.json"]
        assert tags[0].mode_text == "755"
        assert tags[0].body == "echo scaffold-ok"

    def test_four_digit_mode_normalized(self, tmp_path):
        document = _doc_with_tag("tool.sh", "0755", body="echo hi")
        written = extract_document(document, tmp_path)
        assert written[0].mode == 0o755
        assert stat.S_IMODE((tmp_path / "tool.sh").stat().st_mode) == 0o755


class TestEscapeRejected:
    """SECURITY: reject before writing anything — no partial scaffolds."""

    def test_dotdot_escape_rejected(self, tmp_path):
        document = _doc_with_tag("../evil.sh", "755")
        with pytest.raises(ExtractError, match=r"\.\."):
            extract_document(document, tmp_path)
        assert not (tmp_path.parent / "evil.sh").exists()

    def test_nested_dotdot_escape_rejected(self, tmp_path):
        document = _doc_with_tag("a/../../evil.sh", "755")
        with pytest.raises(ExtractError, match=r"\.\."):
            extract_document(document, tmp_path)

    def test_absolute_path_rejected(self, tmp_path):
        document = _doc_with_tag("/tmp/evil-abs.sh", "755")
        with pytest.raises(ExtractError, match="absolute"):
            extract_document(document, tmp_path)
        assert not Path("/tmp/evil-abs.sh").is_file()

    def test_mode_above_0777_rejected(self, tmp_path):
        document = _doc_with_tag("sticky.sh", "1777", body="echo hi")
        with pytest.raises(ExtractError, match="exceeds 0o777"):
            extract_document(document, tmp_path)

    def test_duplicate_target_rejected(self, tmp_path):
        document = _doc_with_tag("dup.sh", "644") + "\n" + _doc_with_tag("dup.sh", "644")
        with pytest.raises(ExtractError, match="duplicate"):
            extract_document(document, tmp_path)

    def test_poison_late_tag_writes_nothing(self, tmp_path):
        # A clean tag followed by a poisoned one must leave no partial output.
        good_then_evil = _doc_with_tag("good.sh", "644") + "\n" + _doc_with_tag("../evil.sh", "644")
        with pytest.raises(ExtractError):
            extract_document(good_then_evil, tmp_path / "dest")
        assert not (tmp_path / "dest").exists(), "all tags validate before any write"


class TestFromBuiltPayload:
    def test_extract_payload_end_to_end(self, pkg):
        root = pkg([("phase0_scaffold", EXTRACT_OK, EXTRACT_TOKENS)], require_dns_first=False)
        manifest = load_manifest(root)
        compile_payload(manifest)
        written = extract_payload(manifest.output_file, manifest.root / "dist")
        assert [item.relpath for item in written] == ["scaffold/run.sh", "configs/policy.json"]
        run_sh = manifest.root / "dist" / "extracted" / "scaffold" / "run.sh"
        assert run_sh.is_file()
        assert stat.S_IMODE(run_sh.stat().st_mode) == 0o755

    def test_extract_requires_built_payload(self, pkg):
        root = pkg([("phase0_scaffold", EXTRACT_OK, EXTRACT_TOKENS)], require_dns_first=False)
        manifest = load_manifest(root)
        with pytest.raises(ExtractError, match="run compile first"):
            extract_payload(manifest.output_file, manifest.root / "dist")
