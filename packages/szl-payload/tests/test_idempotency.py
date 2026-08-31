"""Idempotency proofs: two complete builds must produce byte-identical dist/.

This is only possible because the payload body embeds no timestamps — build
time lives in the export receipt, and the receipt clock is the newest
source-input mtime (SOURCE_DATE_EPOCH convention), so unchanged inputs
rebuild byte-identically.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import DNS_OK, DNS_TOKENS, EXTRACT_OK, EXTRACT_TOKENS, PACKAGE_ROOT

from szl_payload.cli import main

TEMPLATES_DIR = PACKAGE_ROOT / "templates"
REAL_TREE_AVAILABLE = (PACKAGE_ROOT / "manifest.toml").is_file() and (
    PACKAGE_ROOT / "sections"
).is_dir()
requires_real_tree = pytest.mark.skipif(
    not REAL_TREE_AVAILABLE, reason="real sections/ doctrine tree not present"
)


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    """relative path → bytes for every file under *root*, recursively."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class TestSyntheticIdempotency:
    def test_two_full_builds_are_byte_identical(self, tmp_path):
        from conftest import write_package

        root = write_package(
            tmp_path,
            [
                ("phase_neg1_dns", DNS_OK, DNS_TOKENS),
                ("phase0_scaffold", EXTRACT_OK, EXTRACT_TOKENS),
            ],
        )
        shutil.copytree(TEMPLATES_DIR, root / "templates")

        snapshots = []
        for _ in range(2):
            assert main(["all", "--root", str(root)]) == 0
            assert main(["verify", "--root", str(root)]) == 0
            snapshots.append(_snapshot_tree(root / "dist"))
        assert snapshots[0] == snapshots[1]
        assert "SZL_MASTER_PAYLOAD_V14.md" in snapshots[0]
        assert "export/export_manifest.unsigned.json" in snapshots[0]


@requires_real_tree
class TestMakeIdempotentRealTree:
    """The contracted proof: `make idempotent` on the real doctrine tree."""

    def test_make_idempotent_passes(self):
        env = dict(os.environ)
        src = PACKAGE_ROOT / "src"
        receipts = PACKAGE_ROOT.parent / "szl-receipts" / "src"
        pythonpath = os.pathsep.join(
            part
            for part in (str(src), str(receipts), env.get("PYTHONPATH", ""))
            if part
        )
        env["PYTHONPATH"] = pythonpath
        result = subprocess.run(
            ["make", "idempotent"],
            cwd=PACKAGE_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, (
            f"make idempotent failed:\nSTDOUT\n{result.stdout}\nSTDERR\n{result.stderr}"
        )
        assert "byte-identical" in result.stdout
        # The proof leaves the real dist/ in place, fully verified.
        assert (PACKAGE_ROOT / "dist" / "SZL_MASTER_PAYLOAD_V14.md").is_file()
