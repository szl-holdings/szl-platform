"""Receipt chain tests: linkage, monotonic counters, tamper/reorder/
truncation/replay detection, and the domain-separation vector."""

import hashlib
import json

import pytest

from kids_sim.receipts import (
    DOMAIN,
    GENESIS,
    ChainVerificationError,
    ReceiptEngine,
    compute_receipt,
    verify_chain,
)

EVENTS = [
    {"seq": i, "op": op, "status": "EXECUTED", "detail": "", "hw_timestamp": i * 48, "dma_seq": 0}
    for i, op in enumerate(["GEMM_TILED", "RMSNORM", "ATTN_CAUSAL", "RECEIPT_EMIT"])
]


def build():
    e = ReceiptEngine()
    for ev in EVENTS:
        e.emit(dict(ev))
    return e


def test_domain_constant_mandatory():
    assert DOMAIN == b"SZL-KIDS-RECEIPT-V1"


def test_receipt_formula_independent_recompute():
    event = dict(EVENTS[0])
    event["counter"] = 0
    # independent recomputation, not via compute_receipt
    canon = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    expect = hashlib.sha3_256(b"SZL-KIDS-RECEIPT-V1" + GENESIS + canon).hexdigest()
    assert compute_receipt(GENESIS, event).hex() == expect
    # domain separation is real: bare sha3-256 of the event differs
    assert compute_receipt(GENESIS, event).hex() != hashlib.sha3_256(canon).hexdigest()
    # and a SHA-256 of the same bytes differs (cross-domain disjointness)
    assert compute_receipt(GENESIS, event).hex() != hashlib.sha256(DOMAIN + GENESIS + canon).hexdigest()


def test_monotonic_counters_gapless():
    e = build()
    assert [r.counter for r in e.receipts] == [0, 1, 2, 3]


def test_valid_chain_verifies():
    e = build()
    assert verify_chain(e.receipts, [dict(ev) for ev in EVENTS])
    assert verify_chain([r.to_dict() for r in e.receipts])  # dict form


def test_tamper_detected():
    rs = [r.to_dict() for r in build().receipts]
    rs[2]["event"]["op"] = "KV_COMMIT"  # tamper
    with pytest.raises(ChainVerificationError, match="digest mismatch|counter|linkage"):
        verify_chain(rs)


def test_reorder_detected():
    rs = [r.to_dict() for r in build().receipts]
    rs[1], rs[2] = rs[2], rs[1]
    with pytest.raises(ChainVerificationError):
        verify_chain(rs)


def test_truncation_detected():
    e = build()
    rs = [r.to_dict() for r in e.receipts]
    with pytest.raises(ChainVerificationError, match="truncation"):
        verify_chain(rs[:-1], [dict(ev) for ev in EVENTS])


def test_replay_detected():
    rs = [r.to_dict() for r in build().receipts]
    rs.append(rs[1])  # replay an old receipt at the tail
    with pytest.raises(ChainVerificationError):
        verify_chain(rs)


def test_chain_linkage_break_detected():
    rs = [r.to_dict() for r in build().receipts]
    rs[1]["prev_digest"] = "00" * 32
    with pytest.raises(ChainVerificationError, match="linkage|digest"):
        verify_chain(rs)
