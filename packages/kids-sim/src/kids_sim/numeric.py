"""KIDS v0.1 numeric formats.

Two data types are frozen in KIDS v0.1:

* INT8  — symmetric per-tensor quantization, INT32 accumulation.
* BF16  — brain float 16. There is no numpy-native bf16 dtype, so this
  module implements bf16 as a bit-truncation of fp32 with
  round-to-nearest-even (RNE) on the dropped 16 bits. This matches the
  hardware definition (e.g. ARM/Intel bf16 conversion semantics) and is
  fully deterministic.

All conversions are pure bit manipulation on uint32 views of fp32, so
results are bit-exact across platforms.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "fp32_to_bf16",
    "bf16_to_fp32",
    "bf16_roundtrip",
    "quantize_int8",
    "dequantize_int8",
    "Int8Tensor",
]

_BF16_DROP_BITS = 16
_BF16_BIAS_ROUND = 0x7FFF  # (1 << 15) - 1


def fp32_to_bf16(x: np.ndarray) -> np.ndarray:
    """Round fp32 array to bf16 precision, returned as uint16 bit patterns.

    Round-to-nearest-even on the low 16 bits:
        u = bits(x)
        rounding_bias = 0x7FFF + ((u >> 16) & 1)
        u = (u + rounding_bias) >> 16

    NaN inputs stay NaN (the bias add can never turn a NaN into an Inf
    because NaN has exponent all-ones and a nonzero mantissa; adding the
    bias keeps mantissa nonzero except in the payload-overflow case, which
    we guard explicitly).
    """
    arr = np.ascontiguousarray(x, dtype=np.float32)
    u = arr.view(np.uint32).copy()
    isnan = np.isnan(arr)
    rounding_bias = np.uint32(_BF16_BIAS_ROUND) + ((u >> np.uint32(16)) & np.uint32(1))
    u = (u + rounding_bias) >> np.uint32(16)
    out = u.astype(np.uint16)
    if np.any(isnan):
        # Force a quiet NaN payload so a NaN never degenerates to Inf.
        out[isnan] = np.uint16(0x7FC0)
    return out


def bf16_to_fp32(b: np.ndarray) -> np.ndarray:
    """Expand uint16 bf16 bit patterns to fp32 values."""
    u = np.ascontiguousarray(b, dtype=np.uint16).astype(np.uint32) << np.uint32(16)
    return u.view(np.float32)


def bf16_roundtrip(x: np.ndarray) -> np.ndarray:
    """fp32 -> bf16 -> fp32. The canonical 'compute in bf16' storage model."""
    return bf16_to_fp32(fp32_to_bf16(x))


def _bf16_add(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Add two bf16-stored (as fp32 values) arrays, rounding result to bf16."""
    s = np.ascontiguousarray(a, dtype=np.float32) + np.ascontiguousarray(b, dtype=np.float32)
    return bf16_roundtrip(s)


class Int8Tensor:
    """Symmetric per-tensor quantized int8 tensor.

    q = clamp(round(x / scale), -127, 127), stored as int8.
    dequant = q.astype(float32) * scale.
    Accumulation for GEMM is always int32 (see engine.py).
    """

    __slots__ = ("q", "scale", "shape")

    def __init__(self, q: np.ndarray, scale: float):
        q = np.ascontiguousarray(q, dtype=np.int8)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("int8 scale must be finite and > 0")
        self.q = q
        self.scale = float(scale)
        self.shape = q.shape

    def dequantize(self) -> np.ndarray:
        return self.q.astype(np.float32) * np.float32(self.scale)

    def to_dict(self) -> dict:
        return {"q": self.q.tolist(), "scale": self.scale, "shape": list(self.shape)}

    @classmethod
    def from_dict(cls, d: dict) -> Int8Tensor:
        return cls(np.asarray(d["q"], dtype=np.int8).reshape(d["shape"]), float(d["scale"]))


def quantize_int8(x: np.ndarray) -> Int8Tensor:
    """Symmetric per-tensor quantization with saturating int8 cast.

    scale = max(|x|) / 127. If the tensor is all zeros, scale defaults to
    1.0 (dequant of zeros is zeros regardless).
    """
    arr = np.ascontiguousarray(x, dtype=np.float32)
    amax = float(np.max(np.abs(arr))) if arr.size else 0.0
    scale = amax / 127.0 if amax > 0.0 else 1.0
    q = np.rint(arr / np.float32(scale))
    q = np.clip(q, -127.0, 127.0).astype(np.int8)
    return Int8Tensor(q, scale)


def dequantize_int8(t: Int8Tensor) -> np.ndarray:
    return t.dequantize()
