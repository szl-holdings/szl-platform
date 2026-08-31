"""KV-cache Merkle commitment: inclusion proofs and tamper detection."""

import numpy as np
import pytest

from kids_sim.kvcommit import DOMAIN_KV, KVBlockTable, leaf_digest, merkle_root
from kids_sim.memory import PAGE_TOKENS


def make_table():
    rng = np.random.default_rng(401)
    t = KVBlockTable(head_dim=8)
    toks = {}
    for bid, n in ((0, 16), (1, 10), (2, 4), (5, 1)):
        toks[bid] = rng.standard_normal((n, 8)).astype(np.float32)
        t.append_tokens(bid, toks[bid])
    return t, toks


def test_leaf_digest_domain_separated():
    b = b"\x00" * 64
    import hashlib

    assert leaf_digest(b) == hashlib.sha3_256(DOMAIN_KV + b).digest()
    assert leaf_digest(b) != hashlib.sha3_256(b).digest()  # domain separation is real


def test_commit_deterministic():
    t1, _ = make_table()
    t2, _ = make_table()
    assert t1.commit() == t2.commit()


def test_inclusion_proof_verifies():
    t, _ = make_table()
    root = t.commit()
    for bid in t.block_ids():
        proof = t.generate_proof(bid)
        assert KVBlockTable.verify_proof(t.block_bytes(bid), proof, root)


def test_tamper_one_token_fails_proof_and_changes_root():
    t, toks = make_table()
    root_before = t.commit()
    proof = t.generate_proof(1)
    good_bytes = t.block_bytes(1)
    # tamper with ONE token embedding in block 1
    t.append_tokens(1, np.zeros((0, 8), np.float32))  # no-op, sanity
    page = bytearray(t.block_bytes(1))
    page[0] ^= 0xFF  # flip one bit of token 0
    assert not KVBlockTable.verify_proof(bytes(page), proof, root_before)
    # and recomputing the tree with the tampered block changes the root
    t2, _ = make_table()
    t2._blocks[1][0, 0] += 1.0
    assert t2.commit() != root_before
    assert t.append_tokens is not None and good_bytes != bytes(page)


def test_root_changes_when_block_added():
    t, _ = make_table()
    r1 = t.commit()
    t.append_tokens(9, np.ones((2, 8), np.float32))
    assert t.commit() != r1


def test_page_capacity_enforced():
    t = KVBlockTable(head_dim=4)
    t.append_tokens(0, np.ones((PAGE_TOKENS, 4), np.float32))
    with pytest.raises(ValueError):
        t.append_tokens(0, np.ones((1, 4), np.float32))


def test_merkle_root_empty():
    assert isinstance(merkle_root([]), bytes) and len(merkle_root([])) == 32


def test_odd_leaf_promotion():
    leaves = [leaf_digest(bytes([i])) for i in range(3)]
    r3 = merkle_root(leaves)
    assert r3 != merkle_root(leaves[:2])  # third leaf matters
