"""KIDS v0.1 conformance runner.

    python -m kids_sim.conformance run --vectors vectors/ --json

Runs every golden vector, prints per-vector PASS/FAIL with digests.
Exit codes: 0 all pass, 1 failure, 2 a vector file is corrupt/invalid
(e.g. fails its own schema or digest self-check). UNKNOWN is never
coerced to PASS.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import receipts as rcpt
from .engine import Engine
from .isa import command_from_dict
from .numeric import Int8Tensor

VECTOR_SCHEMA_KEYS = {"name", "kind"}
VALID_KINDS = {
    "gemm_int8",
    "gemm_bf16",
    "rmsnorm",
    "attn_causal",
    "yarqa",
    "kv_commit",
    "receipt_chain",
    "receipt_domain",
}


class VectorError(Exception):
    """The vector file itself is invalid/corrupt (exit 2)."""


@dataclass
class VectorResult:
    name: str
    status: str  # PASS | FAIL | ERROR
    detail: str
    digest: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail,
                "digest": self.digest}


def _decode_input(spec: dict[str, Any]) -> Any:
    kind = spec.get("type", "f32")
    if kind == "int8":
        return Int8Tensor(np.asarray(spec["q"], dtype=np.int8).reshape(spec["shape"]),
                          float(spec["scale"]))
    if kind == "bf16":
        from .numeric import bf16_roundtrip

        return bf16_roundtrip(np.asarray(spec["data"], dtype=np.float32))
    return np.asarray(spec["data"], dtype=np.float32)


def _close(a: np.ndarray, b: np.ndarray, rtol: float = 1e-3, atol: float = 1e-6) -> bool:
    return bool(np.allclose(a, b, rtol=rtol, atol=atol))


def run_vector(path: Path) -> VectorResult:
    try:
        v = json.loads(path.read_text())
    except Exception as e:
        raise VectorError(f"{path.name}: unreadable JSON: {e}") from e
    if not isinstance(v, dict) or not VECTOR_SCHEMA_KEYS <= set(v):
        raise VectorError(f"{path.name}: missing required keys {sorted(VECTOR_SCHEMA_KEYS)}")
    kind = v["kind"]
    if kind not in VALID_KINDS:
        raise VectorError(f"{path.name}: unknown kind {kind!r}")
    name = v["name"]
    try:
        return _DISPATCH[kind](name, v)
    except VectorError:
        raise
    except Exception as e:  # execution blew up: the vector may be corrupt
        raise VectorError(f"{name}: execution error: {e}") from e


def _run_steps(v: dict[str, Any]) -> Engine:
    head_dim = v.get("head_dim", 8)
    rc1 = None
    setup = v.get("setup", {})
    if "rc1" in setup:
        from .rc1 import RC1Controller

        r = setup["rc1"]
        rc1 = RC1Controller(r["device_id"], bytes.fromhex(r["auth_key_hex"]),
                            set(r.get("policy_digests", [])))
    eng = Engine(head_dim=head_dim, rc1=rc1)
    for step in v["steps"]:
        for spec in step.get("inputs", []):
            eng.push(_decode_input(spec))
        if "envelope" in step:  # queue an RC1 envelope for a RC1_SEND step
            cmd = step["command"]
            eng.submit_envelope(cmd.get("mailbox", 0), step["envelope"])
        eng.execute(command_from_dict(step["command"]))
    return eng


def _expect_array(name: str, got: np.ndarray, v: dict, *, exact: bool) -> VectorResult:
    exp = np.asarray(v["expected"]["data"], dtype=np.float32)
    got = np.asarray(got, dtype=np.float32)
    if got.shape != exp.shape:
        return VectorResult(name, "FAIL", f"shape {got.shape} != expected {exp.shape}")
    ok = np.array_equal(got, exp) if exact else _close(got, exp)
    import hashlib

    dig = hashlib.sha3_256(np.ascontiguousarray(got).tobytes()).hexdigest()[:16]
    return VectorResult(name, "PASS" if ok else "FAIL",
                        "exact match" if exact else "rtol<=1e-3", dig)


def _v_gemm_int8(name: str, v: dict) -> VectorResult:
    eng = _run_steps(v)
    top = eng.pop()
    if not isinstance(top, dict) or "acc_int32" not in top:
        raise VectorError(f"{name}: int8 GEMM did not produce an int32 accumulator")
    exp = np.asarray(v["expected"]["acc_int32"], dtype=np.int32)
    got = top["acc_int32"]
    ok = got.shape == exp.shape and np.array_equal(got, exp)
    return VectorResult(name, "PASS" if ok else "FAIL", "int32 accumulator exact equality")


def _v_gemm_bf16(name: str, v: dict) -> VectorResult:
    eng = _run_steps(v)
    return _expect_array(name, eng.pop(), v, exact=True)


def _v_rmsnorm(name: str, v: dict) -> VectorResult:
    eng = _run_steps(v)
    exact = v.get("expected", {}).get("exact", False)
    return _expect_array(name, eng.pop(), v, exact=exact)


def _v_attn(name: str, v: dict) -> VectorResult:
    eng = _run_steps(v)
    return _expect_array(name, eng.pop(), v, exact=False)


def _v_kv_commit(name: str, v: dict) -> VectorResult:
    eng = _run_steps(v)
    root = eng.pop()
    expected = v["expected"]["kv_root"]
    ok = isinstance(root, bytes) and root.hex() == expected
    short = root.hex()[:16] if isinstance(root, bytes) else ""
    return VectorResult(name, "PASS" if ok else "FAIL", "Merkle root match", short)


def _v_receipt_chain(name: str, v: dict) -> VectorResult:
    eng_events: list[dict] = v["events"]
    expected: list[str] = v["expected"]["receipts"]
    engine = rcpt.ReceiptEngine()
    for ev in eng_events:
        engine.emit(ev)
    got = [r.digest.hex() for r in engine.receipts]
    ok = got == expected and rcpt.verify_chain(engine.receipts)
    return VectorResult(name, "PASS" if ok else "FAIL",
                        f"{len(got)} receipts, chain verified", engine.root.hex()[:16])


def _v_receipt_domain(name: str, v: dict) -> VectorResult:
    domain = v["domain"].encode()
    if domain != rcpt.DOMAIN:
        raise VectorError(f"{name}: domain {v['domain']!r} != mandatory {rcpt.DOMAIN.decode()!r}")
    prev = bytes.fromhex(v["prev_digest"])
    got = rcpt.compute_receipt(prev, v["event"]).hex()
    ok = got == v["expected_digest"]
    return VectorResult(name, "PASS" if ok else "FAIL",
                        "sha3_256(DOMAIN||prev||event) cross-check", got[:16])


_DISPATCH = {
    "gemm_int8": _v_gemm_int8,
    "gemm_bf16": _v_gemm_bf16,
    "rmsnorm": _v_rmsnorm,
    "attn_causal": _v_attn,
    "yarqa": _v_attn,
    "kv_commit": _v_kv_commit,
    "receipt_chain": _v_receipt_chain,
    "receipt_domain": _v_receipt_domain,
}


def run_directory(vectors_dir: Path) -> tuple[list[VectorResult], list[str]]:
    """Returns (results, corrupt_vector_names)."""
    results: list[VectorResult] = []
    corrupt: list[str] = []
    for path in sorted(vectors_dir.glob("*.json")):
        try:
            results.append(run_vector(path))
        except VectorError as e:
            corrupt.append(str(e))
            results.append(VectorResult(path.stem, "ERROR", str(e)))
    return results, corrupt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kids_sim.conformance",
                                description="KIDS v0.1 golden-vector conformance runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="run conformance vectors")
    run_p.add_argument("--vectors", type=Path, required=True, help="vector directory")
    run_p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    if args.cmd == "run":
        if not args.vectors.is_dir():
            print(f"vector dir {args.vectors} not found", file=sys.stderr)
            return 2
        results, corrupt = run_directory(args.vectors)
        failed = [r for r in results if r.status == "FAIL"]
        payload = {
            "kids_version": "0.1",
            "vectors": [r.to_dict() for r in results],
            "corrupt": corrupt,
            "summary": {
                "total": len(results),
                "pass": sum(1 for r in results if r.status == "PASS"),
                "fail": len(failed),
                "error": len(corrupt),
            },
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for r in results:
                print(f"{r.status:5s}  {r.name:28s} {r.digest:16s} {r.detail}")
            s = payload["summary"]
            print(f"\n{s['pass']}/{s['total']} PASS, {s['fail']} FAIL, {s['error']} ERROR")
        if corrupt:
            return 2
        return 1 if failed else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
