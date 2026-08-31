#!/usr/bin/env python3
"""Generate the checked-in KIDS v0.1 golden conformance vectors.

Deterministic: fixed seeds, fixed shapes. Regenerate with:

    python packages/kids-sim/vectors/generate_vectors.py

NOTE ON PROVENANCE: expected values are produced BY the golden simulator
itself — these vectors pin the executable specification against
regressions. The independent correctness proof is the differential test
suite (tests/) against NumPy references, per the KIDS build doctrine.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from kids_sim import receipts as rcpt
from kids_sim.engine import (
    attention_causal,
    attention_yarqa,
    gemm_bf16,
    gemm_int32,
    rmsnorm,
)
from kids_sim.kvcommit import KVBlockTable
from kids_sim.numeric import bf16_roundtrip, quantize_int8

HERE = Path(__file__).resolve().parent
SEED = 0xBEE5


def write(name: str, doc: dict) -> None:
    doc = {"name": name, "kids_version": "0.1", "seed": SEED, **doc}
    (HERE / f"{name}.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {name}.json")


def gen_gemm_int8(rng: np.random.Generator) -> None:
    m, k, n, tile = 6, 12, 8, 4
    a = quantize_int8(rng.standard_normal((m, k), dtype=np.float32))
    b = quantize_int8(rng.standard_normal((k, n), dtype=np.float32))
    acc = gemm_int32(a.q, b.q, tile=tile)
    write("gemm_int8_01", {
        "kind": "gemm_int8",
        "steps": [{
            "command": {"op": "GEMM_TILED", "M": m, "N": n, "K": k, "tile": tile,
                        "dtype": "int8", "scale_id": 0},
            "inputs": [
                {"type": "int8", "q": a.q.tolist(), "scale": a.scale, "shape": list(a.shape)},
                {"type": "int8", "q": b.q.tolist(), "scale": b.scale, "shape": list(b.shape)},
            ],
        }],
        "expected": {"acc_int32": acc.tolist()},
    })


def gen_gemm_bf16(rng: np.random.Generator) -> None:
    m, k, n, tile = 5, 10, 7, 4
    a = bf16_roundtrip(rng.standard_normal((m, k), dtype=np.float32))
    b = bf16_roundtrip(rng.standard_normal((k, n), dtype=np.float32))
    c = gemm_bf16(a, b, tile=tile)
    write("gemm_bf16_01", {
        "kind": "gemm_bf16",
        "steps": [{
            "command": {"op": "GEMM_TILED", "M": m, "N": n, "K": k, "tile": tile,
                        "dtype": "bf16", "scale_id": 0},
            "inputs": [
                {"type": "bf16", "data": a.tolist()},
                {"type": "bf16", "data": b.tolist()},
            ],
        }],
        "expected": {"data": c.tolist(), "exact": True},
    })


def gen_rmsnorm(rng: np.random.Generator) -> None:
    rows, d = 4, 8
    x = rng.standard_normal((rows, d), dtype=np.float32)
    g = rng.standard_normal((d,), dtype=np.float32)
    eps = 1e-5
    y = rmsnorm(x, g, eps=eps, dtype="fp32")
    write("rmsnorm_01", {
        "kind": "rmsnorm",
        "steps": [{
            "command": {"op": "RMSNORM", "eps": eps, "dtype": "fp32"},
            "inputs": [
                {"type": "f32", "data": x.tolist()},
                {"type": "f32", "data": g.tolist()},
            ],
        }],
        "expected": {"data": y.tolist(), "exact": False},
    })


def gen_attn(rng: np.random.Generator) -> None:
    s, d = 6, 8
    q = rng.standard_normal((s, d), dtype=np.float32)
    k = rng.standard_normal((s, d), dtype=np.float32)
    v = rng.standard_normal((s, d), dtype=np.float32)
    scale = 1.0 / float(np.sqrt(d))
    out = attention_causal(q, k, v, scale=scale)
    write("attn_causal_01", {
        "kind": "attn_causal",
        "steps": [{
            "command": {"op": "ATTN_CAUSAL", "head_dim": d, "seq_len": s, "scale": scale},
            "inputs": [
                {"type": "f32", "data": q.tolist()},
                {"type": "f32", "data": k.tolist()},
                {"type": "f32", "data": v.tolist()},
            ],
        }],
        "expected": {"data": out.tolist(), "exact": False},
    })


def gen_yarqa(rng: np.random.Generator) -> None:
    s, d = 6, 8
    q = rng.standard_normal((s, d), dtype=np.float32)
    k = rng.standard_normal((s, d), dtype=np.float32)
    v = rng.standard_normal((s, d), dtype=np.float32)
    compartments = [[0, 1, 2], [3, 4], [5]]
    out = attention_yarqa(q, k, v, compartments)
    write("yarqa_01", {
        "kind": "yarqa",
        "steps": [{
            "command": {"op": "YARQA_COMPARTMENT", "compartment_descriptor": compartments},
            "inputs": [
                {"type": "f32", "data": q.tolist()},
                {"type": "f32", "data": k.tolist()},
                {"type": "f32", "data": v.tolist()},
            ],
        }],
        "expected": {"data": out.tolist(), "exact": False},
    })


def gen_kv_commit(rng: np.random.Generator) -> None:
    from kids_sim.lgate import PolicyRule
    from kids_sim.rc1 import compute_auth_tag

    head_dim = 8
    table = KVBlockTable(head_dim)
    device_id = "KHIPU-X1-SIM"
    auth_key = bytes.fromhex("00" * 31 + "01")
    policy_digest = PolicyRule(allowed_opcodes=frozenset({"KV_APPEND", "KV_COMMIT"})).digest().hex()
    blocks = {0: 16, 1: 9, 2: 3}  # tokens per block
    steps = []
    nonce = 0

    def auth_steps(command_type: str) -> list[dict]:
        nonlocal nonce
        nonce += 1
        env = {
            "schema_version": "1",
            "target_id": device_id,
            "command_type": command_type,
            "bounds": {},
            "nonce": nonce,
            "expiry_cycle": 10**12,
            "policy_digest": policy_digest,
        }
        env["auth_tag"] = compute_auth_tag(env, auth_key)
        return [
            {"command": {"op": "RC1_SEND", "mailbox": 0}, "inputs": [], "envelope": env},
            {"command": {"op": "RC1_RECV", "mailbox": 0}, "inputs": []},
        ]

    for bid, ntok in blocks.items():
        toks = rng.standard_normal((ntok, head_dim), dtype=np.float32)
        table.append_tokens(bid, toks)
        steps += auth_steps("KV_APPEND")
        steps.append({
            "command": {"op": "KV_APPEND", "block_id": bid, "tokens": ntok},
            "inputs": [{"type": "f32", "data": toks.tolist()}],
        })
    steps += auth_steps("KV_COMMIT")
    steps.append({"command": {"op": "KV_COMMIT"}, "inputs": []})
    write("kv_commit_01", {
        "kind": "kv_commit",
        "head_dim": head_dim,
        "setup": {"rc1": {"device_id": device_id, "auth_key_hex": auth_key.hex(),
                          "policy_digests": [policy_digest]}},
        "steps": steps,
        "expected": {"kv_root": table.commit().hex()},
    })


def gen_receipt_chain() -> None:
    engine = rcpt.ReceiptEngine()
    events = [
        {"seq": 0, "op": "GEMM_TILED", "status": "EXECUTED", "detail": "",
         "hw_timestamp": 0, "dma_seq": 0},
        {"seq": 1, "op": "RMSNORM", "status": "EXECUTED", "detail": "",
         "hw_timestamp": 48, "dma_seq": 0},
        {"seq": 2, "op": "RECEIPT_EMIT", "status": "EXECUTED", "detail": "",
         "hw_timestamp": 96, "dma_seq": 0},
    ]
    for ev in events:
        engine.emit(ev)
    write("receipt_chain_01", {
        "kind": "receipt_chain",
        "events": events,
        "expected": {"receipts": [r.digest.hex() for r in engine.receipts]},
    })


def gen_receipt_domain() -> None:
    # One fixed event, expected digest computed by the engine AND
    # cross-checked by hand below (see "cross_check" field).
    event = {"seq": 0, "op": "RECEIPT_EMIT", "status": "EXECUTED", "detail": "domain-separation check",
             "hw_timestamp": 0, "dma_seq": 0, "counter": 0}
    prev = rcpt.GENESIS
    digest = rcpt.compute_receipt(prev, event).hex()
    doc = {
        "name": "receipt_domain_vector",
        "kids_version": "0.1",
        "seed": SEED,
        "kind": "receipt_domain",
        "domain": rcpt.DOMAIN.decode(),
        "prev_digest": prev.hex(),
        "event": event,
        "expected_digest": digest,
        "cross_check": (
            "python3 -c \"import hashlib,json; "
            "print(hashlib.sha3_256(b'SZL-KIDS-RECEIPT-V1' + bytes(32) + "
            "json.dumps(EVENT, sort_keys=True, separators=(',',':')).encode()).hexdigest())\" "
            "with EVENT the 'event' object above; must equal expected_digest. "
            "This vector pins the domain separation resolving the estate "
            "SHA-256-vs-SHA3-256 cross-domain concern (fork_findings section 3)."
        ),
    }
    (HERE / "receipt_domain_vector.json").write_text(json.dumps(doc, indent=2) + "\n")
    print("wrote receipt_domain_vector.json")


def main() -> None:
    rng = np.random.default_rng(SEED)
    gen_gemm_int8(rng)
    gen_gemm_bf16(rng)
    gen_rmsnorm(rng)
    gen_attn(rng)
    gen_yarqa(rng)
    gen_kv_commit(rng)
    gen_receipt_chain()
    gen_receipt_domain()


if __name__ == "__main__":
    main()
