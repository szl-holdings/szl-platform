"""Reproduce the worked example of draft-lutar-governed-action-receipt-00.

Run from a directory containing the szl-receipts repository checkout:

    pip install -e ./szl-receipts          # version 14.0.0
    mkdir -p policies dist
    printf 'SZL Build Policy v14\nAll governed builds must be reproducible and receipted.\n' > policies/szl.build.v14.md
    printf 'SZL MASTER PAYLOAD V14\n' > dist/SZL_MASTER_PAYLOAD_V14.md
    python reproduce-appendix-b.py

Expected: the receipt prints with receipt_id
27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8,
canonical length 650 bytes, canonical sha256
f300e474b5bf4f7cd909155b292d47143aea5a3fbd3b27d6aabaedc7a53e5059,
genesis entry_digest
0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9,
second entry_digest
ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c,
and the DSSE envelope verifies under the printed example public key.
All output is deterministic: created_at is fixed and the Ed25519
example key is derived from a fixed seed.  The example key is a
public, non-secret test vector; never use it operationally.
"""
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from szl_receipts import (
    Outcome, append, build_receipt, compute_receipt_id, jcs_canon_bytes,
    sha256_file, sha256_hex, sign_bytes, verify_chain, verify_envelope,
    verify_receipt,
)

receipt = build_receipt(
    actor="ci-runner-7",
    action="build-master-payload",
    policy={
        "id": "szl.build.v14",
        "version": "14.0.0",
        "digest_sha256": sha256_file("policies/szl.build.v14.md"),
    },
    outcome=Outcome.PASS,
    rationale="deterministic rebuild verified byte-identical",
    subjects=[{
        "name": "dist/SZL_MASTER_PAYLOAD_V14.md",
        "sha256": sha256_file("dist/SZL_MASTER_PAYLOAD_V14.md"),
    }],
    evidence=[{"uri": "https://ci.szl.example/runs/2026-08-31-001"}],
    created_at="2026-08-31T18:00:00Z",  # fixed, so the example is reproducible
)
assert verify_receipt(receipt) == []
assert receipt["receipt_id"] == compute_receipt_id(receipt)
print(json.dumps(receipt, indent=2, sort_keys=True))

canon = jcs_canon_bytes(dict(receipt))  # the bytes a DSSE envelope carries
print("canonical bytes:", len(canon))
print("sha256(canonical):", sha256_hex(canon))
print("receipt_id:", receipt["receipt_id"])

seed = bytes.fromhex(sha256_hex(b"draft-lutar-governed-action-receipt example key"))
key = Ed25519PrivateKey.from_private_bytes(seed)  # non-secret test vector
print(key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode(), end="")

envelope = sign_bytes(canon, "application/gar+json", key)
assert verify_envelope(envelope, key.public_key())
print(json.dumps(envelope, indent=2, sort_keys=True))

chain = []
first = append(chain, receipt)
second = build_receipt(
    actor="ci-runner-7",
    action="promote-master-payload",
    policy={
        "id": "szl.build.v14",
        "version": "14.0.0",
        "digest_sha256": sha256_file("policies/szl.build.v14.md"),
    },
    outcome=Outcome.PASS,
    rationale="promotion gate passed on PASS receipt",
    subjects=[{
        "name": "dist/SZL_MASTER_PAYLOAD_V14.md",
        "sha256": sha256_file("dist/SZL_MASTER_PAYLOAD_V14.md"),
    }],
    evidence=[{"uri": "https://ci.szl.example/runs/2026-08-31-001"}],
    created_at="2026-08-31T18:05:00Z",
)
second_entry = append(chain, second)
report = verify_chain(
    chain, expected_entries=2, expected_head=second_entry["entry_digest"]
)
assert report.ok
print("genesis entry_digest:", first["entry_digest"])
print("entry 2 digest:", second_entry["entry_digest"])
print("chain head:", report.head)
