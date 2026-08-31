"""Pin bf16 RNE behavior at .5 boundaries and bf16/int8 conversion semantics."""

import numpy as np
import pytest

from kids_sim.numeric import (
    bf16_roundtrip,
    bf16_to_fp32,
    dequantize_int8,
    fp32_to_bf16,
    quantize_int8,
)


def bits(x: float) -> np.uint32:
    return np.array([x], dtype=np.float32).view(np.uint32)[0]


def from_bits(u: int) -> float:
    return np.array([u], dtype=np.uint32).view(np.float32)[0]


class TestBf16RNE:
    """Round-to-nearest-EVEN on the dropped 16 bits, pinned at .5."""

    def test_half_rounds_to_even_down(self):
        # 0x3F808000: dropped bits exactly 0x8000 (.5), kept LSB 0 (even) -> stays
        assert fp32_to_bf16(np.array([from_bits(0x3F808000)], dtype=np.float32))[0] == 0x3F80

    def test_half_rounds_to_even_up(self):
        # 0x3F818000: dropped .5, kept LSB 1 (odd) -> rounds up
        assert fp32_to_bf16(np.array([from_bits(0x3F818000)], dtype=np.float32))[0] == 0x3F82

    def test_below_half_rounds_down(self):
        assert fp32_to_bf16(np.array([from_bits(0x3F807FFF)], dtype=np.float32))[0] == 0x3F80

    def test_above_half_rounds_up(self):
        assert fp32_to_bf16(np.array([from_bits(0x3F808001)], dtype=np.float32))[0] == 0x3F81

    def test_exact_values_unchanged(self):
        for b in (0x3F80, 0xBF80, 0x0000, 0x3FC0):  # 1.0, -1.0, 0.0, 1.5
            v = bf16_to_fp32(np.array([b], dtype=np.uint16))
            assert fp32_to_bf16(v)[0] == b

    def test_nan_preserved(self):
        out = fp32_to_bf16(np.array([np.nan], dtype=np.float32))
        assert np.isnan(bf16_to_fp32(out)[0])

    def test_inf_preserved(self):
        out = fp32_to_bf16(np.array([np.inf], dtype=np.float32))
        assert np.isinf(bf16_to_fp32(out)[0])

    def test_negative_rounding_magnitude(self):
        # -1.0 with .5 in dropped bits behaves symmetrically
        assert fp32_to_bf16(np.array([from_bits(0xBF808000)], dtype=np.float32))[0] == 0xBF80
        assert fp32_to_bf16(np.array([from_bits(0xBF818000)], dtype=np.float32))[0] == 0xBF82


class TestBf16RoundTrip:
    def test_roundtrip_idempotent(self):
        rng = np.random.default_rng(7)
        x = rng.standard_normal(1000).astype(np.float32)
        once = bf16_roundtrip(x)
        twice = bf16_roundtrip(once)
        np.testing.assert_array_equal(once, twice)

    def test_roundtrip_within_bf16_resolution(self):
        rng = np.random.default_rng(8)
        x = rng.standard_normal(1000).astype(np.float32)
        y = bf16_roundtrip(x)
        rel = np.abs(y - x) / np.maximum(np.abs(x), 1e-30)
        assert np.all(rel <= 2**-8 + 1e-9)

    def test_bits_are_bf16_representable(self):
        rng = np.random.default_rng(9)
        x = rng.standard_normal(256).astype(np.float32)
        y = bf16_roundtrip(x)
        low = y.view(np.uint32) & np.uint32(0xFFFF)
        assert np.all(low == 0)


class TestInt8:
    def test_symmetric_scale(self):
        x = np.linspace(-4, 4, 33, dtype=np.float32)
        t = quantize_int8(x)
        assert t.scale == pytest.approx(4.0 / 127.0)
        assert t.q.max() == 127 and t.q.min() == -127

    def test_saturating_quantize(self):
        x = np.array([1e9, -1e9], dtype=np.float32)
        t = quantize_int8(x)
        assert t.q.tolist() == [127, -127]

    def test_dequantize_roundtrip_close(self):
        rng = np.random.default_rng(11)
        x = rng.standard_normal((16, 16)).astype(np.float32)
        y = dequantize_int8(quantize_int8(x))
        np.testing.assert_allclose(y, x, rtol=2 / 127, atol=2 / 127)

    def test_zero_tensor(self):
        t = quantize_int8(np.zeros((4,), dtype=np.float32))
        assert np.all(t.q == 0)
        np.testing.assert_array_equal(t.dequantize(), np.zeros(4, dtype=np.float32))

    def test_scale_must_be_positive(self):
        from kids_sim.numeric import Int8Tensor

        with pytest.raises(ValueError):
            Int8Tensor(np.zeros((2,), dtype=np.int8), 0.0)
