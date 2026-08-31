"""KIDS v0.1 frozen instruction set.

The command set below is the frozen KIDS v0.1 ISA surface. Every command
is a typed dataclass with to_dict/from_dict that validates required
fields and types against the same contract expressed in
schema/kids.schema.json (draft 2020-12). Validation is hand-rolled
(jsonschema-lite) so the simulator carries no schema dependency.

OPCODES carry stable numeric codes — changing a code is an ISA break.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar

KIDS_VERSION = "0.1"
DOMAIN_SEPARATION = "SZL-KIDS-RECEIPT-V1"
SCHEMA_ID = "https://schemas.szlholdings.com/kids/v0.1"


class Opcode(enum.IntEnum):
    """Stable KIDS v0.1 opcode numbers. Never renumber."""

    GEMM_TILED = 0x01
    RMSNORM = 0x02
    DMA_LOAD = 0x03
    DMA_STORE = 0x04
    ATTN_CAUSAL = 0x05
    YARQA_COMPARTMENT = 0x06
    KV_APPEND = 0x07
    KV_COMMIT = 0x08
    LGATE_CHECK = 0x09
    RC1_SEND = 0x0A
    RC1_RECV = 0x0B
    RECEIPT_EMIT = 0x0C


# Opcodes that require RC1-mailbox authorization before they may execute.
PRIVILEGED_OPCODES: frozenset[Opcode] = frozenset(
    {Opcode.DMA_STORE, Opcode.KV_APPEND, Opcode.KV_COMMIT, Opcode.RC1_RECV}
)

_DTYPES = ("int8", "bf16", "fp32")


class SchemaError(ValueError):
    """Raised when a command dict fails schema validation."""


@dataclass(frozen=True)
class Command:
    """Base class for KIDS commands."""

    OPCODE: ClassVar[Opcode]
    _REQUIRED: ClassVar[dict[str, type | tuple[type, ...]]] = {}

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"op": self.OPCODE.name}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, enum.Enum):
                v = v.value
            elif isinstance(v, (list, tuple)):
                v = [x if not isinstance(x, enum.Enum) else x.value for x in v]
            d[f.name] = v
        return d

    @classmethod
    def validate(cls, d: dict[str, Any]) -> None:
        if not isinstance(d, dict):
            raise SchemaError("command must be an object")
        if d.get("op") != cls.OPCODE.name:
            raise SchemaError(f"expected op {cls.OPCODE.name!r}, got {d.get('op')!r}")
        for name, typ in cls._REQUIRED.items():
            if name not in d:
                raise SchemaError(f"{cls.OPCODE.name}: missing required field {name!r}")
            if not isinstance(d[name], typ) or (typ is int and isinstance(d[name], bool)):
                raise SchemaError(
                    f"{cls.OPCODE.name}: field {name!r} must be {typ}, got {type(d[name]).__name__}"
                )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Command:
        cls.validate(d)
        kwargs = {f.name: d[f.name] for f in fields(cls) if f.name in d}
        return cls(**kwargs)


@dataclass(frozen=True)
class GemmTiled(Command):
    """C[M,N] = A[M,K] @ B[K,N], tiled. int8 accumulates in int32."""

    OPCODE: ClassVar[Opcode] = Opcode.GEMM_TILED
    _REQUIRED: ClassVar[dict] = {
        "M": int,
        "N": int,
        "K": int,
        "tile": int,
        "dtype": str,
        "scale_id": int,
    }
    M: int
    N: int
    K: int
    tile: int
    dtype: str
    scale_id: int

    @classmethod
    def validate(cls, d: dict[str, Any]) -> None:
        super().validate(d)
        if d["dtype"] not in _DTYPES:
            raise SchemaError(f"GEMM_TILED: dtype must be one of {_DTYPES}")
        for dim in ("M", "N", "K", "tile"):
            if d[dim] <= 0:
                raise SchemaError(f"GEMM_TILED: {dim} must be > 0")


@dataclass(frozen=True)
class RmsNorm(Command):
    """y = x / sqrt(mean(x^2) + eps) * g over the last axis."""

    OPCODE: ClassVar[Opcode] = Opcode.RMSNORM
    _REQUIRED: ClassVar[dict] = {"eps": (int, float), "dtype": str}
    eps: float
    dtype: str

    @classmethod
    def validate(cls, d: dict[str, Any]) -> None:
        super().validate(d)
        if d["dtype"] not in ("bf16", "fp32"):
            raise SchemaError("RMSNORM: dtype must be bf16 or fp32")
        if not float(d["eps"]) > 0:
            raise SchemaError("RMSNORM: eps must be > 0")


@dataclass(frozen=True)
class DmaLoad(Command):
    OPCODE: ClassVar[Opcode] = Opcode.DMA_LOAD
    _REQUIRED: ClassVar[dict] = {
        "descriptor_id": int,
        "src": int,
        "dst": int,
        "bytes": int,
        "seq": int,
    }
    descriptor_id: int
    src: int
    dst: int
    bytes: int
    seq: int


@dataclass(frozen=True)
class DmaStore(Command):
    OPCODE: ClassVar[Opcode] = Opcode.DMA_STORE
    _REQUIRED: ClassVar[dict] = DmaLoad._REQUIRED
    descriptor_id: int
    src: int
    dst: int
    bytes: int
    seq: int


@dataclass(frozen=True)
class AttnCausal(Command):
    """Causal scaled-dot-product attention, scale = 1/sqrt(head_dim) unless given."""

    OPCODE: ClassVar[Opcode] = Opcode.ATTN_CAUSAL
    _REQUIRED: ClassVar[dict] = {"head_dim": int, "seq_len": int, "scale": (int, float)}
    head_dim: int
    seq_len: int
    scale: float


@dataclass(frozen=True)
class YarqaCompartment(Command):
    """Attention restricted to compartment token subsets.

    compartment_descriptor: list of compartments; each compartment is a
    list of token indices. A query at row i attends only to keys in the
    compartment(s) that contain i (canal semantics — see engine.py).
    """

    OPCODE: ClassVar[Opcode] = Opcode.YARQA_COMPARTMENT
    _REQUIRED: ClassVar[dict] = {"compartment_descriptor": list}
    compartment_descriptor: list = field(default_factory=list)

    @classmethod
    def validate(cls, d: dict[str, Any]) -> None:
        super().validate(d)
        for comp in d["compartment_descriptor"]:
            if not isinstance(comp, list) or not all(isinstance(i, int) and i >= 0 for i in comp):
                raise SchemaError("YARQA_COMPARTMENT: each compartment must be a list of non-negative ints")


@dataclass(frozen=True)
class KvAppend(Command):
    """Append tokens to KV block (16 tokens x head_dim per block page)."""

    OPCODE: ClassVar[Opcode] = Opcode.KV_APPEND
    _REQUIRED: ClassVar[dict] = {"block_id": int, "tokens": int}
    block_id: int
    tokens: int


@dataclass(frozen=True)
class KvCommit(Command):
    OPCODE: ClassVar[Opcode] = Opcode.KV_COMMIT
    _REQUIRED: ClassVar[dict] = {}


@dataclass(frozen=True)
class LGateCheck(Command):
    OPCODE: ClassVar[Opcode] = Opcode.LGATE_CHECK
    _REQUIRED: ClassVar[dict] = {"policy_digest": str, "command_digest": str}
    policy_digest: str
    command_digest: str


@dataclass(frozen=True)
class Rc1Send(Command):
    OPCODE: ClassVar[Opcode] = Opcode.RC1_SEND
    _REQUIRED: ClassVar[dict] = {"mailbox": int}
    mailbox: int


@dataclass(frozen=True)
class Rc1Recv(Command):
    OPCODE: ClassVar[Opcode] = Opcode.RC1_RECV
    _REQUIRED: ClassVar[dict] = {"mailbox": int}
    mailbox: int


@dataclass(frozen=True)
class ReceiptEmit(Command):
    OPCODE: ClassVar[Opcode] = Opcode.RECEIPT_EMIT
    _REQUIRED: ClassVar[dict] = {}


COMMAND_CLASSES: dict[str, type[Command]] = {
    c.OPCODE.name: c
    for c in (
        GemmTiled,
        RmsNorm,
        DmaLoad,
        DmaStore,
        AttnCausal,
        YarqaCompartment,
        KvAppend,
        KvCommit,
        LGateCheck,
        Rc1Send,
        Rc1Recv,
        ReceiptEmit,
    )
}


def command_from_dict(d: dict[str, Any]) -> Command:
    """Parse + validate a command dict against the KIDS v0.1 contract."""
    if not isinstance(d, dict) or "op" not in d:
        raise SchemaError("command must be an object with an 'op' field")
    op = d["op"]
    cls = COMMAND_CLASSES.get(op)
    if cls is None:
        raise SchemaError(f"unknown op {op!r}")
    return cls.from_dict(d)


def program_from_dicts(ds: list[dict[str, Any]]) -> list[Command]:
    if not isinstance(ds, list):
        raise SchemaError("a KIDS program is an array of commands")
    return [command_from_dict(d) for d in ds]


def program_to_dicts(prog: list[Command]) -> list[dict[str, Any]]:
    return [c.to_dict() for c in prog]
