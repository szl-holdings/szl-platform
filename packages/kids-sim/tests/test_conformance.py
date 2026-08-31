"""Conformance runner tests: all committed vectors pass; corrupted copy
in tmp_path returns exit 2; tampered expected value returns exit 1."""

import json
import shutil
from pathlib import Path

from kids_sim import conformance

VECTORS = Path(__file__).resolve().parent.parent / "vectors"


def test_all_committed_vectors_pass():
    results, corrupt = conformance.run_directory(VECTORS)
    assert corrupt == []
    statuses = {r.name: r.status for r in results}
    assert all(s == "PASS" for s in statuses.values()), statuses
    assert len(results) >= 8


def test_cli_main_all_pass():
    assert conformance.main(["run", "--vectors", str(VECTORS), "--json"]) == 0


def test_corrupt_vector_copy_exit_2(tmp_path):
    shutil.copytree(VECTORS, tmp_path / "vectors")
    victim = tmp_path / "vectors" / "gemm_int8_01.json"
    victim.write_text("{ not json !!")  # corrupted COPY; committed vector untouched
    rc = conformance.main(["run", "--vectors", str(tmp_path / "vectors"), "--json"])
    assert rc == 2


def test_tampered_expected_value_exit_1(tmp_path):
    shutil.copytree(VECTORS, tmp_path / "vectors")
    victim = tmp_path / "vectors" / "receipt_chain_01.json"
    doc = json.loads(victim.read_text())
    doc["expected"]["receipts"][1] = "00" * 32  # break the expected chain
    victim.write_text(json.dumps(doc))
    rc = conformance.main(["run", "--vectors", str(tmp_path / "vectors")])
    assert rc == 1


def test_unknown_kind_is_error_exit_2(tmp_path):
    (tmp_path / "bogus.json").write_text(json.dumps({"name": "bogus", "kind": "nope"}))
    assert conformance.main(["run", "--vectors", str(tmp_path)]) == 2


def test_domain_vector_matches_independent_computation():
    doc = json.loads((VECTORS / "receipt_domain_vector.json").read_text())
    canon = json.dumps(doc["event"], sort_keys=True, separators=(",", ":")).encode()
    import hashlib

    expect = hashlib.sha3_256(doc["domain"].encode() + bytes.fromhex(doc["prev_digest"]) + canon)
    assert expect.hexdigest() == doc["expected_digest"]
