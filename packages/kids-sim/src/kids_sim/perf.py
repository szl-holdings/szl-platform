"""KIDS v0.1 cycle-approximate performance model.

HONESTY DOCTRINE: every cycle number produced here is an ESTIMATE from a
documented analytic formula. The golden simulator has no wall-clock
semantics: the measured wall-clock path reports UNAVAILABLE rather than
fabricating a benchmark. When the FPGA/RTL exists, real measurements
replace these estimates; until then, labels stay explicit.

Formulas (v0.1, all ESTIMATE):
  GEMM_TILED:  ceil(M/tile)*ceil(N/tile)*K MAC-cycles
               + ceil(bytes_loaded / DMA_BW_BYTES_PER_CYCLE)
  RMSNORM:     2 passes over the tensor: 2 * numel
  ATTN_CAUSAL: causal => ~half the S*S block: ceil(S*S/2)*head_dim MAC-cycles
               + softmax ~ 3*S*S
  YARQA:       sum over compartments of ceil(len^2/2)*head_dim + 3*len^2
  DMA:         ceil(bytes / DMA_BW_BYTES_PER_CYCLE)
  KV_APPEND:   tokens*head_dim stores; KV_COMMIT: one hash per 64-byte block
               chunk of every page + ceil(log2(nblocks)) tree levels
  LGATE_CHECK: exactly 1 cycle (single-cycle is a SPEC TARGET to be proven
               in RTL — see lgate.py)
  RECEIPT_EMIT: SHA3-256 over one event: HASH_CYCLES_PER_EVENT
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .isa import Command, Opcode
from .memory import PAGE_TOKENS

# v0.1 model constants (documented, not measured):
DMA_BW_BYTES_PER_CYCLE = 64  # ESTIMATE
HASH_BYTES_PER_CYCLE = 64  # ESTIMATE: one SHA3-256 rate absorb per cycle-ish
HASH_CYCLES_PER_EVENT = 24  # ESTIMATE: Keccak-f[1600] = 24 rounds
UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class CycleEstimate:
    op: str
    cycles: int
    label: str = "ESTIMATE"  # every number is an estimate; never unlabeled
    formula: str = ""

    def to_dict(self) -> dict:
        return {"op": self.op, "cycles": self.cycles, "label": self.label, "formula": self.formula}


def estimate_cycles(cmd: Command, *, dma_bytes: int = 0, head_dim: int = 0,
                    kv_blocks: int = 0, tokens: int = 0) -> CycleEstimate:
    op = cmd.OPCODE
    name = op.name
    if op is Opcode.GEMM_TILED:
        m, n, k, tile = cmd.M, cmd.N, cmd.K, cmd.tile  # type: ignore[attr-defined]
        mac = math.ceil(m / tile) * math.ceil(n / tile) * k
        dma = math.ceil(dma_bytes / DMA_BW_BYTES_PER_CYCLE)
        return CycleEstimate(name, mac + dma,
                             formula=(f"ceil({m}/{tile})*ceil({n}/{tile})*{k} "
                                      f"+ ceil({dma_bytes}/{DMA_BW_BYTES_PER_CYCLE})"))
    if op is Opcode.RMSNORM:
        n = max(dma_bytes // 4, 1)
        return CycleEstimate(name, 2 * n, formula=f"2*numel (two passes), numel={n}")
    if op is Opcode.ATTN_CAUSAL:
        s, d = cmd.seq_len, cmd.head_dim  # type: ignore[attr-defined]
        mac = (s * s // 2) * d
        soft = 3 * s * s
        return CycleEstimate(name, mac + soft, formula=f"({s}*{s}/2)*{d} + 3*{s}*{s}")
    if op is Opcode.YARQA_COMPARTMENT:
        total = 0
        for comp in cmd.compartment_descriptor:  # type: ignore[attr-defined]
            c = len(comp)
            total += (c * c // 2) * max(head_dim, 1) + 3 * c * c
        return CycleEstimate(name, total, formula="sum_c ceil(|c|^2/2)*d + 3*|c|^2")
    if op in (Opcode.DMA_LOAD, Opcode.DMA_STORE):
        b = cmd.bytes  # type: ignore[attr-defined]
        return CycleEstimate(name, math.ceil(b / DMA_BW_BYTES_PER_CYCLE),
                             formula=f"ceil({b}/{DMA_BW_BYTES_PER_CYCLE})")
    if op is Opcode.KV_APPEND:
        elems = tokens * max(head_dim, 1)
        return CycleEstimate(name, elems, formula=f"{tokens}*{head_dim} stores")
    if op is Opcode.KV_COMMIT:
        page_bytes = PAGE_TOKENS * max(head_dim, 1) * 4
        leaf_cycles = math.ceil(page_bytes / HASH_BYTES_PER_CYCLE) + HASH_CYCLES_PER_EVENT
        levels = max(1, math.ceil(math.log2(max(kv_blocks, 1))) + 1)
        total = kv_blocks * leaf_cycles + levels * HASH_CYCLES_PER_EVENT
        return CycleEstimate(name, total,
                             formula=(f"{kv_blocks}*(ceil({page_bytes}/{HASH_BYTES_PER_CYCLE})"
                                      f"+{HASH_CYCLES_PER_EVENT}) + {levels}*{HASH_CYCLES_PER_EVENT}"))
    if op is Opcode.LGATE_CHECK:
        return CycleEstimate(name, 1, formula="1 cycle (single-cycle SPEC TARGET, to be proven in RTL)")
    if op is Opcode.RECEIPT_EMIT:
        return CycleEstimate(name, HASH_CYCLES_PER_EVENT, formula=f"{HASH_CYCLES_PER_EVENT} (one SHA3-256)")
    if op in (Opcode.RC1_SEND, Opcode.RC1_RECV):
        return CycleEstimate(name, HASH_CYCLES_PER_EVENT, formula="envelope validate ~ one HMAC-SHA3-256")
    return CycleEstimate(name, 0, formula="no model")


def measured_wall_clock() -> str:
    """The golden simulator does NOT measure wall clock. Report honestly."""
    return UNAVAILABLE
