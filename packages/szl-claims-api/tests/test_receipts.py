"""Receipts: GovernedAction/v1 correctness, outcome mapping, content-keyed caching."""

from __future__ import annotations

import json
import re
from pathlib import Path

from szl_claims_api.receipts import (
    CLAIM_VERIFY_ACTION,
    POLICY_ID,
    ReceiptMinter,
    claim_content_hash,
    policy_digest,
)
from szl_claims_api.seed import load_seed_registry
from szl_receipts import (
    GOVERNED_ACTION_V1,
    jcs_canon_bytes,
    sha256_bytes,
    verify_receipt,
)

_SHA256_HEX_RE = re.compile(r"\A[0-9a-f]{64}\Z")


def _claims(sample_claims_path: Path) -> dict[str, dict]:
    raw = json.loads(sample_claims_path.read_text(encoding="utf-8"))
    return {c["claim_id"]: c for c in raw}


def test_pass_claim_receipt_verifies_clean(sample_claims_path: Path) -> None:
    claim = _claims(sample_claims_path)["monorepo_packages"]
    receipt = ReceiptMinter().receipt_for(claim)
    assert verify_receipt(receipt) == []
    assert receipt["receipt_type"] == GOVERNED_ACTION_V1
    assert receipt["action"] == CLAIM_VERIFY_ACTION
    assert receipt["decision"]["outcome"] == "PASS"
    # Subject digest covers the claim's canonical bytes — bytes, not names.
    assert receipt["subjects"] == [
        {"name": "monorepo_packages", "sha256": claim_content_hash(claim)}
    ]
    assert receipt["evidence"] == [{"uri": claim["source"]}]
    assert receipt["policy"]["id"] == POLICY_ID
    assert _SHA256_HEX_RE.match(receipt["policy"]["digest_sha256"])
    assert _SHA256_HEX_RE.match(receipt["receipt_id"])
    # A verified claim's receipt is pinned to its run: reproducible by anyone
    # holding the claims file.
    assert receipt["created_at"] == claim["last_run"]


def test_drift_maps_to_fail(sample_claims_path: Path) -> None:
    claim = _claims(sample_claims_path)["hf_models"]
    receipt = ReceiptMinter().receipt_for(claim)
    assert verify_receipt(receipt) == []
    assert receipt["decision"]["outcome"] == "FAIL"
    assert "DRIFT" in receipt["decision"]["rationale"]


def test_unknown_maps_to_unknown(sample_claims_path: Path) -> None:
    claim = _claims(sample_claims_path)["lambda_overhead_ms_median"]
    receipt = ReceiptMinter().receipt_for(claim)
    assert verify_receipt(receipt) == []
    assert receipt["decision"]["outcome"] == "UNKNOWN"


def test_same_claim_content_yields_same_receipt_id(sample_claims_path: Path) -> None:
    claim = _claims(sample_claims_path)["monorepo_packages"]
    minter = ReceiptMinter()
    first = minter.receipt_for(claim)
    second = minter.receipt_for(dict(claim))
    assert first["receipt_id"] == second["receipt_id"]
    assert len(minter) == 1  # cached, not re-minted


def test_mutated_observed_yields_new_receipt(sample_claims_path: Path) -> None:
    claim = _claims(sample_claims_path)["monorepo_packages"]
    minter = ReceiptMinter()
    before = minter.receipt_for(claim)
    mutated = dict(claim, observed=127, verdict="DRIFT")
    after = minter.receipt_for(mutated)
    # A claim whose observed value changed gets a NEW receipt — never reuse.
    assert after["receipt_id"] != before["receipt_id"]
    assert len(minter) == 2
    assert verify_receipt(after) == []


def test_new_run_yields_new_receipt(sample_claims_path: Path) -> None:
    """Reverification at a later run must mint a fresh identity even when the
    measured value is unchanged — last_run is part of the policy version."""
    claim = _claims(sample_claims_path)["monorepo_packages"]
    minter = ReceiptMinter()
    before = minter.receipt_for(claim)
    rerun = dict(claim, last_run="2026-09-01T07:30:00Z")
    after = minter.receipt_for(rerun)
    assert after["receipt_id"] != before["receipt_id"]
    assert after["created_at"] == "2026-09-01T07:30:00Z"
    assert verify_receipt(after) == []


def test_policy_digest_is_stable_and_content_addressed() -> None:
    digest = policy_digest()
    assert _SHA256_HEX_RE.match(digest)
    assert policy_digest() == digest
    # It is a real digest of real bytes: the canonical seed registry.
    assert digest == sha256_bytes(jcs_canon_bytes(load_seed_registry())).hex()
