"""kids_sim — KIDS v0.1 golden simulator.

Executable specification for the KHIPU-X1 governance-first LLM
accelerator ISA. The golden simulator comes BEFORE any RTL; differential
tests against NumPy references are the only correctness proof.
"""

from . import engine, isa, kvcommit, lgate, memory, numeric, perf, rc1, receipts
from .engine import Engine
from .isa import Opcode, command_from_dict, program_from_dicts
from .memory import AccessContext, HardPartitionFault, Memory
from .numeric import Int8Tensor, bf16_roundtrip, fp32_to_bf16, quantize_int8
from .receipts import ReceiptEngine, verify_chain

__version__ = "0.1.0"
KIDS_VERSION = isa.KIDS_VERSION

__all__ = [
    "Engine",
    "Memory",
    "AccessContext",
    "HardPartitionFault",
    "Opcode",
    "ReceiptEngine",
    "Int8Tensor",
    "bf16_roundtrip",
    "fp32_to_bf16",
    "quantize_int8",
    "command_from_dict",
    "program_from_dicts",
    "verify_chain",
    "engine",
    "isa",
    "kvcommit",
    "lgate",
    "memory",
    "numeric",
    "perf",
    "rc1",
    "receipts",
]
