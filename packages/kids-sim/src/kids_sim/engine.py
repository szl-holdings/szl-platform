"""KIDS v0.1 deterministic execution engine.

Runs a program (list of KIDS commands) over the memory model, emitting one
event per command into the receipt engine. Determinism is a hard
requirement: same program + same inputs => identical receipt root.

Execution model: a deterministic value stack holds operands (numpy arrays
or Int8Tensor). GEMM/RMSNORM/ATTN pop operands, push results. This keeps
the ISA surface (M,N,K,tile,dtype,scale_id) free of addressing detail —
addressing is the compiler's problem, semantics are the ISA's.

Privileged commands (DMA_STORE, KV_APPEND, KV_COMMIT) require BOTH:
  1. an RC1 authorization token — an envelope delivered via RC1_SEND and
     moved to the auth pool by RC1_RECV whose command_type matches the op;
  2. LGATE ALLOW, when a policy gate is installed.

DENY / missing authorization => the command does not execute, the event
is logged DENIED with a reason, and architectural state is unchanged
(fail closed). Any HardPartitionFault raised by the memory model is
caught, logged as BYPASS_ATTEMPT, and the command does not execute.

YARQA_COMPARTMENT semantics (frozen v0.1 choice — "canal semantics"):
the descriptor is a list of compartments, each a set of token indices
(canals). Query row i attends to key j iff j <= i (causality) AND i and j
share at least one compartment. Tokens in no compartment attend only to
themselves. This is causal attention restricted per-canal: the model can
never mix information across canals, which is the governance property
YARQA exists to provide.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from . import lgate as lg
from . import perf
from .isa import (
    AttnCausal,
    Command,
    DmaLoad,
    DmaStore,
    GemmTiled,
    KvAppend,
    LGateCheck,
    Opcode,
    Rc1Recv,
    Rc1Send,
    RmsNorm,
    YarqaCompartment,
)
from .kvcommit import KVBlockTable
from .memory import AccessContext, HardPartitionFault, Memory
from .numeric import Int8Tensor, bf16_roundtrip
from .rc1 import RC1Controller, RC1Reject
from .receipts import Receipt, ReceiptEngine

PRIVILEGED: frozenset[Opcode] = frozenset({Opcode.DMA_STORE, Opcode.KV_APPEND, Opcode.KV_COMMIT})


class Engine:
    def __init__(
        self,
        *,
        policy: lg.PolicyRule | None = None,
        rc1: RC1Controller | None = None,
        head_dim: int = 64,
    ) -> None:
        self.memory = Memory()
        self.receipts = ReceiptEngine()
        self.lgate = lg.LGate(policy) if policy is not None else None
        self.rc1 = rc1
        self.kv = KVBlockTable(head_dim)
        self.head_dim = head_dim
        self.stack: list[Any] = []
        self._outbox: list[tuple[int, dict]] = []  # envelopes queued for RC1_SEND
        self._auth_pool: list[dict] = []  # validated envelopes authorizing privileged ops
        self.events: list[dict[str, Any]] = []
        self.total_cycles = 0

    # --- operand stack ----------------------------------------------------
    def push(self, value: Any) -> None:
        self.stack.append(value)

    def pop(self) -> Any:
        if not self.stack:
            raise RuntimeError("operand stack underflow")
        return self.stack.pop()

    def submit_envelope(self, mailbox: int, env: dict) -> None:
        self._outbox.append((mailbox, env))

    # --- main loop --------------------------------------------------------
    def run(self, program: list[Command]) -> list[Receipt]:
        for cmd in program:
            self.execute(cmd)
        return self.receipts.receipts

    def execute(self, cmd: Command) -> None:
        event: dict[str, Any] = {
            "seq": len(self.events),
            "op": cmd.OPCODE.name,
            "command": cmd.to_dict(),
        }
        status = "EXECUTED"
        detail = ""
        try:
            if cmd.OPCODE in PRIVILEGED:
                auth = self._authorize(cmd)
                if auth is not None:
                    status, detail = auth
                else:
                    self._dispatch(cmd, event)
            else:
                self._dispatch(cmd, event)
        except HardPartitionFault as e:
            status, detail = "BYPASS_ATTEMPT", str(e)
        except RC1Reject as e:
            status, detail = "DENIED", str(e)
        event.update(
            {
                "status": status,
                "detail": detail,
                "hw_timestamp": self.memory.cycle_count,  # CYCLES, never wall time
                "dma_seq": self.memory.monotonic_sequence_counter,
            }
        )
        self.events.append(event)
        self.receipts.emit(event)

    # --- authorization ----------------------------------------------------
    def _authorize(self, cmd: Command) -> tuple[str, str] | None:
        """Return None if authorized, else (status, reason) for DENIED."""
        # 1. RC1 authorization token
        token_idx = next(
            (i for i, env in enumerate(self._auth_pool) if env["command_type"] == cmd.OPCODE.name),
            None,
        )
        if token_idx is None:
            return ("DENIED", f"no RC1 authorization for {cmd.OPCODE.name}")
        # 2. LGATE policy gate (exactly 1 cycle — spec target)
        if self.lgate is not None:
            verdict = self.lgate.check(cmd.to_dict(), self.receipts.counter)
            self._charge(1)
            if verdict.decision is lg.Decision.DENY:
                return ("DENIED", f"LGATE: {verdict.reason}")
        self._auth_pool.pop(token_idx)
        return None

    # --- dispatch ----------------------------------------------------------
    def _dispatch(self, cmd: Command, event: dict) -> None:
        op = cmd.OPCODE
        if op is Opcode.GEMM_TILED:
            assert isinstance(cmd, GemmTiled)
            result = self._gemm(cmd)
            self.push(result)
            est = perf.estimate_cycles(cmd, dma_bytes=cmd.M * cmd.K + cmd.K * cmd.N)
            self._charge(est.cycles)
            raw = result.q.tobytes() if isinstance(result, Int8Tensor) else None
            if raw is None and isinstance(result, dict):
                raw = result["acc_int32"].tobytes()
            if raw is None:
                raw = np.ascontiguousarray(np.asarray(result)).tobytes()
            event["result_digest"] = _array_digest(raw)
        elif op is Opcode.RMSNORM:
            assert isinstance(cmd, RmsNorm)
            g = self.pop()
            x = self.pop()
            result = rmsnorm(np.asarray(x, dtype=np.float32), np.asarray(g, dtype=np.float32),
                             eps=float(cmd.eps), dtype=cmd.dtype)
            self.push(result)
            est = perf.estimate_cycles(cmd, dma_bytes=int(np.asarray(x).size) * 4)
            self._charge(est.cycles)
            event["result_digest"] = _array_digest(np.ascontiguousarray(result).tobytes())
        elif op is Opcode.ATTN_CAUSAL:
            assert isinstance(cmd, AttnCausal)
            v, k, q = self.pop(), self.pop(), self.pop()
            result = attention_causal(np.asarray(q, np.float32), np.asarray(k, np.float32),
                                      np.asarray(v, np.float32), scale=float(cmd.scale))
            self.push(result)
            est = perf.estimate_cycles(cmd)
            self._charge(est.cycles)
            event["result_digest"] = _array_digest(np.ascontiguousarray(result).tobytes())
        elif op is Opcode.YARQA_COMPARTMENT:
            assert isinstance(cmd, YarqaCompartment)
            v, k, q = self.pop(), self.pop(), self.pop()
            result = attention_yarqa(np.asarray(q, np.float32), np.asarray(k, np.float32),
                                     np.asarray(v, np.float32), cmd.compartment_descriptor)
            self.push(result)
            est = perf.estimate_cycles(cmd, head_dim=int(np.asarray(q).shape[-1]))
            self._charge(est.cycles)
            event["result_digest"] = _array_digest(np.ascontiguousarray(result).tobytes())
        elif op is Opcode.DMA_LOAD:
            assert isinstance(cmd, DmaLoad)
            seq = self.memory.dma(cmd.src, cmd.dst, cmd.bytes, ctx=AccessContext.AP)
            event["dma_seq"] = seq
            self._charge(perf.estimate_cycles(cmd).cycles)
        elif op is Opcode.DMA_STORE:
            assert isinstance(cmd, DmaStore)
            seq = self.memory.dma(cmd.src, cmd.dst, cmd.bytes, ctx=AccessContext.AP)
            event["dma_seq"] = seq
            self._charge(perf.estimate_cycles(cmd).cycles)
        elif op is Opcode.KV_APPEND:
            assert isinstance(cmd, KvAppend)
            tokens = np.asarray(self.pop(), dtype=np.float32)
            self.kv.append_tokens(cmd.block_id, tokens)
            self._charge(perf.estimate_cycles(cmd, head_dim=self.head_dim,
                                              tokens=int(tokens.shape[0])).cycles)
        elif op is Opcode.KV_COMMIT:
            root = self.kv.commit()
            self.push(root)
            event["kv_root"] = root.hex()
            self._charge(perf.estimate_cycles(cmd, head_dim=self.head_dim,
                                              kv_blocks=len(self.kv.block_ids())).cycles)
        elif op is Opcode.LGATE_CHECK:
            assert isinstance(cmd, LGateCheck)
            event["lgate"] = self._lgate_check(cmd)
        elif op is Opcode.RC1_SEND:
            assert isinstance(cmd, Rc1Send)
            self._rc1_send(cmd.mailbox)
            self._charge(perf.estimate_cycles(cmd).cycles)
        elif op is Opcode.RC1_RECV:
            assert isinstance(cmd, Rc1Recv)
            got = self._rc1_recv(cmd.mailbox)
            event["envelope_received"] = got
            self._charge(perf.estimate_cycles(cmd).cycles)
        elif op is Opcode.RECEIPT_EMIT:
            event["receipt_root"] = self.receipts.root.hex()
            self._charge(perf.estimate_cycles(cmd).cycles)
        else:  # pragma: no cover - all opcodes handled
            raise RuntimeError(f"unhandled opcode {op}")

    # --- ops ---------------------------------------------------------------
    def _gemm(self, cmd: GemmTiled) -> Any:
        b, a = self.pop(), self.pop()
        if cmd.dtype == "int8":
            if not (isinstance(a, Int8Tensor) and isinstance(b, Int8Tensor)):
                raise TypeError("int8 GEMM requires Int8Tensor operands")
            acc = gemm_int32(a.q, b.q, tile=cmd.tile)
            return {"acc_int32": acc, "scale": a.scale * b.scale,
                    "fp32": acc.astype(np.float32) * np.float32(a.scale * b.scale)}
        af = np.asarray(a, dtype=np.float32)
        bf = np.asarray(b, dtype=np.float32)
        if cmd.dtype == "bf16":
            return gemm_bf16(af, bf, tile=cmd.tile)
        return gemm_tiled_f32(af, bf, tile=cmd.tile)

    def _lgate_check(self, cmd: LGateCheck) -> dict:
        if self.lgate is None:
            return {"decision": "ALLOW", "reason": "no policy installed", "cycles": 0}
        verdict = self.lgate.check({"op": cmd.command_digest}, self.receipts.counter)
        self._charge(verdict.cycles)  # exactly 1 — spec target
        return {"decision": verdict.decision.value, "reason": verdict.reason,
                "cycles": verdict.cycles}

    def _rc1_send(self, mailbox: int) -> None:
        if self.rc1 is None:
            raise RC1Reject("no RC1 controller attached")
        if not self._outbox:
            raise RC1Reject("RC1_SEND with empty outbox")
        mb, env = self._outbox.pop(0)
        if mb != mailbox:
            raise RC1Reject(f"outbox envelope addressed to mailbox {mb}, not {mailbox}")
        # Delivered over the narrow RC1 interface; write hits the mailbox
        # region in RC1 context — the ONLY context allowed to write it.
        self.rc1.send(mailbox, env, current_cycle=self.memory.cycle_count)

    def _rc1_recv(self, mailbox: int) -> bool:
        if self.rc1 is None:
            raise RC1Reject("no RC1 controller attached")
        env = self.rc1.recv(mailbox)
        if env is None:
            return False
        self._auth_pool.append(env)
        return True

    def _charge(self, cycles: int) -> None:
        self.memory.cycle_count += cycles
        self.total_cycles += cycles


# --- numeric kernels (the golden references live here) ---------------------

def _array_digest(b: bytes) -> str:
    import hashlib

    return hashlib.sha3_256(b"SZL-KIDS-RESULT-V1" + b).hexdigest()


def gemm_tiled_f32(a: np.ndarray, b: np.ndarray, tile: int) -> np.ndarray:
    """Tiled fp32 GEMM with float64 accumulation across k-tiles.

    fp64 accumulation makes the result independent of tile size to far
    below fp32 resolution, so the tiled datapath and the numpy reference
    agree bit-exactly after the final fp32 rounding in every practical case.
    """
    m, k = a.shape
    k2, n = b.shape
    if k != k2:
        raise ValueError(f"inner dim mismatch {k} vs {k2}")
    acc = np.zeros((m, n), dtype=np.float64)
    for i0 in range(0, m, tile):
        for j0 in range(0, n, tile):
            partial = np.zeros((min(tile, m - i0), min(tile, n - j0)), dtype=np.float64)
            for k0 in range(0, k, tile):
                partial += a[i0 : i0 + tile, k0 : k0 + tile].astype(np.float64) @ b[
                    k0 : k0 + tile, j0 : j0 + tile
                ].astype(np.float64)
            acc[i0 : i0 + partial.shape[0], j0 : j0 + partial.shape[1]] = partial
    return acc.astype(np.float32)


def gemm_int32(a_q: np.ndarray, b_q: np.ndarray, tile: int) -> np.ndarray:
    """Tiled int8 x int8 -> int32 accumulate. Exact integer arithmetic:
    tile-independent, exactly equal to the numpy int32 reference."""
    m, k = a_q.shape
    _, n = b_q.shape
    acc = np.zeros((m, n), dtype=np.int64)
    for i0 in range(0, m, tile):
        for j0 in range(0, n, tile):
            partial = np.zeros((min(tile, m - i0), min(tile, n - j0)), dtype=np.int64)
            for k0 in range(0, k, tile):
                partial += a_q[i0 : i0 + tile, k0 : k0 + tile].astype(np.int32) @ b_q[
                    k0 : k0 + tile, j0 : j0 + tile
                ].astype(np.int32)
            acc[i0 : i0 + partial.shape[0], j0 : j0 + partial.shape[1]] = partial
    if np.any(acc > np.int64(2**31 - 1)) or np.any(acc < np.int64(-(2**31))):
        raise OverflowError("int32 accumulator overflow — K too large for v0.1 budget")
    return acc.astype(np.int32)


def gemm_bf16(a: np.ndarray, b: np.ndarray, tile: int) -> np.ndarray:
    """bf16 GEMM, TPU-style: operands rounded to bf16, products and
    accumulation in fp64 (tile-order independent), output is the fp32
    accumulator value (rounding to bf16 on store is a separate explicit
    conversion, matching real bf16 MAC arrays).

    Tolerances (frozen v0.1): bit-exact against the golden reference at
    ANY tile size; <=1e-3 rtol vs the fp32 reference computed on the SAME
    bf16-rounded operands (in practice ~1e-6). Note the operand rounding
    itself contributes up to 2^-9 relative vs an unrounded fp32 GEMM —
    that is a property of the bf16 dtype (8 significand bits), not of the
    datapath, and is documented rather than hidden."""
    a_q = bf16_roundtrip(a).astype(np.float64)
    b_q = bf16_roundtrip(b).astype(np.float64)
    m, k = a_q.shape
    _, n = b_q.shape
    acc = np.zeros((m, n), dtype=np.float64)
    for i0 in range(0, m, tile):
        for j0 in range(0, n, tile):
            partial = np.zeros((min(tile, m - i0), min(tile, n - j0)), dtype=np.float64)
            for k0 in range(0, k, tile):
                partial += a_q[i0 : i0 + tile, k0 : k0 + tile] @ b_q[k0 : k0 + tile, j0 : j0 + tile]
            acc[i0 : i0 + partial.shape[0], j0 : j0 + partial.shape[1]] = partial
    return acc.astype(np.float32)


def rmsnorm(x: np.ndarray, g: np.ndarray, eps: float, dtype: str = "fp32") -> np.ndarray:
    """y = x / sqrt(mean(x^2) + eps) * g over the last axis.

    bf16 path: inputs rounded to bf16, computation in fp32, output rounded
    to bf16 (documented v0.1 choice: single rounding at output).
    """
    if dtype == "bf16":
        x = bf16_roundtrip(x)
        g = bf16_roundtrip(g)
    ms = np.mean(x.astype(np.float64) ** 2, axis=-1, keepdims=True)
    y = x / np.sqrt(ms + eps) * g
    y = y.astype(np.float32)
    return bf16_roundtrip(y) if dtype == "bf16" else y


def attention_causal(q: np.ndarray, k: np.ndarray, v: np.ndarray, scale: float) -> np.ndarray:
    """Standard causal scaled-dot-product attention, fp32."""
    s = q.shape[0]
    scores = (q @ k.T) * np.float32(scale)
    mask = np.triu(np.ones((s, s), dtype=bool), k=1)
    scores = np.where(mask, np.float32(-np.inf), scores)
    return _softmax_rows(scores) @ v


def attention_yarqa(q: np.ndarray, k: np.ndarray, v: np.ndarray,
                    compartments: list[list[int]]) -> np.ndarray:
    """YARQA canal attention (frozen v0.1 semantics — see module docstring).

    Query i attends to key j iff j <= i AND exists a compartment containing
    both i and j. Tokens in no compartment attend only to themselves."""
    s = q.shape[0]
    owner: list[set[int]] = [set() for _ in range(s)]
    for ci, comp in enumerate(compartments):
        for t in comp:
            if t >= s:
                raise ValueError(f"compartment {ci} references token {t} >= seq_len {s}")
            owner[t].add(ci)
    scores = (q @ k.T).astype(np.float64)
    scale = 1.0 / math.sqrt(q.shape[-1])
    scores *= scale
    allowed = np.zeros((s, s), dtype=bool)
    for i in range(s):
        for j in range(i + 1):  # causal
            allowed[i, j] = (i == j) or bool(owner[i] & owner[j])
    scores = np.where(allowed, scores, -np.inf)
    return (_softmax_rows(scores.astype(np.float32)) @ v).astype(np.float32)


def _softmax_rows(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x, axis=-1, keepdims=True)
    e = np.exp(x)
    return (e / np.sum(e, axis=-1, keepdims=True)).astype(np.float32)
