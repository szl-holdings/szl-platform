"""KIDS v0.1 end-to-end demo: tiny 2-layer transformer block.

    python -m kids_sim.demo [--json]

Pipeline per layer: GEMM (QKV projection) -> RMSNORM -> ATTN_CAUSAL ->
KV_APPEND -> then KV_COMMIT + RECEIPT_EMIT at the end, printing the
receipt chain root. Deterministic: fixed seed, fixed shapes.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from .engine import Engine
from .isa import AttnCausal, GemmTiled, KvAppend, KvCommit, Rc1Recv, Rc1Send, ReceiptEmit, RmsNorm
from .lgate import PolicyRule
from .rc1 import RC1Controller, compute_auth_tag

SEQ, D_MODEL, HEAD_DIM = 8, 16, 8
DEVICE_ID = "KHIPU-X1-DEMO"
AUTH_KEY = bytes.fromhex("de" * 32)
POLICY = PolicyRule(allowed_opcodes=frozenset({"KV_APPEND", "KV_COMMIT", "DMA_STORE"}))
_nonce = 0


def authorize(eng: Engine, command_type: str) -> None:
    """Deliver a valid RC1 envelope authorizing one privileged command."""
    global _nonce
    _nonce += 1
    env = {
        "schema_version": "1",
        "target_id": DEVICE_ID,
        "command_type": command_type,
        "bounds": {},
        "nonce": _nonce,
        "expiry_cycle": 10**12,
        "policy_digest": POLICY.digest().hex(),
    }
    env["auth_tag"] = compute_auth_tag(env, AUTH_KEY)
    eng.submit_envelope(0, env)
    eng.execute(Rc1Send(mailbox=0))
    eng.execute(Rc1Recv(mailbox=0))


def build() -> tuple[Engine, dict]:
    rng = np.random.default_rng(0x1D5)
    rc1 = RC1Controller(DEVICE_ID, AUTH_KEY, {POLICY.digest().hex()})
    eng = Engine(head_dim=HEAD_DIM, rc1=rc1)
    x = rng.standard_normal((SEQ, D_MODEL), dtype=np.float32)
    w1 = rng.standard_normal((D_MODEL, D_MODEL), dtype=np.float32) * 0.1
    w2 = rng.standard_normal((D_MODEL, D_MODEL), dtype=np.float32) * 0.1
    g = np.ones((D_MODEL,), dtype=np.float32)
    return eng, {"x": x, "w1": w1, "w2": w2, "g": g}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kids_sim.demo",
                                description="tiny 2-layer governed transformer block on the KIDS golden sim")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    eng, t = build()
    h = t["x"]
    for layer, w in enumerate((t["w1"], t["w2"])):
        eng.push(h)
        eng.push(w)
        eng.execute(GemmTiled(M=SEQ, N=D_MODEL, K=D_MODEL, tile=4, dtype="fp32", scale_id=0))
        proj = eng.pop()
        eng.push(proj)
        eng.push(t["g"])
        eng.execute(RmsNorm(eps=1e-5, dtype="fp32"))
        normed = eng.pop()
        q = normed[:, :HEAD_DIM]
        k = normed[:, :HEAD_DIM]
        v = normed[:, :HEAD_DIM]
        eng.push(q)
        eng.push(k)
        eng.push(v)
        eng.execute(AttnCausal(head_dim=HEAD_DIM, seq_len=SEQ, scale=1.0 / np.sqrt(HEAD_DIM)))
        eng.pop()  # attention output (fed forward implicitly; demo keeps h = normed)
        eng.push(k.astype(np.float32))
        authorize(eng, "KV_APPEND")
        eng.execute(KvAppend(block_id=layer, tokens=SEQ))
        h = normed

    authorize(eng, "KV_COMMIT")
    eng.execute(KvCommit())
    kv_root = eng.pop()
    eng.execute(ReceiptEmit())

    out = {
        "layers": 2,
        "kv_root": kv_root.hex(),
        "receipt_root": eng.receipts.root.hex(),
        "receipts": len(eng.receipts.receipts),
        "cycles_estimate": {"value": eng.total_cycles, "label": "ESTIMATE"},
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("KIDS v0.1 demo: 2-layer transformer block (GEMM+RMSNORM+ATTN+KV_COMMIT+RECEIPT_EMIT)")
        for r in eng.receipts.receipts:
            print(f"  [{r.counter}] {r.event['op']:14s} {r.event['status']:9s} {r.digest.hex()[:16]}")
        print(f"KV root:      {out['kv_root']}")
        print(f"Receipt root: {out['receipt_root']}")
        print(f"Cycles: {eng.total_cycles} (ESTIMATE); wall clock UNAVAILABLE in sim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
