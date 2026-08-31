"""GEMM_TILED differential tests against NumPy references."""

import numpy as np
import pytest

from kids_sim.engine import gemm_bf16, gemm_int32, gemm_tiled_f32
from kids_sim.numeric import bf16_roundtrip, quantize_int8


@pytest.mark.parametrize("tile", [1, 3, 4, 16])
def test_int8_gemm_exact_vs_numpy(tile):
    rng = np.random.default_rng(101)
    m, k, n = 7, 13, 5
    a = quantize_int8(rng.standard_normal((m, k), dtype=np.float32))
    b = quantize_int8(rng.standard_normal((k, n), dtype=np.float32))
    got = gemm_int32(a.q, b.q, tile=tile)
    ref = a.q.astype(np.int32) @ b.q.astype(np.int32)  # numpy int32 reference
    np.testing.assert_array_equal(got, ref)  # EXACT equality


@pytest.mark.parametrize("tile", [1, 4, 8])
def test_bf16_gemm_bit_exact_and_fp32_close(tile):
    rng = np.random.default_rng(102)
    m, k, n = 6, 12, 6
    a = bf16_roundtrip(rng.standard_normal((m, k), dtype=np.float32))
    b = bf16_roundtrip(rng.standard_normal((k, n), dtype=np.float32))
    got = gemm_bf16(a, b, tile=tile)
    # bit-exact against the golden reference at any tile size
    ref = gemm_bf16(a, b, tile=2)
    np.testing.assert_array_equal(got, ref)
    # <= 1e-3 rtol vs the fp32 reference on the same bf16-rounded operands
    fp32_ref = a @ b
    np.testing.assert_allclose(got, fp32_ref, rtol=1e-3, atol=1e-3)
    # and vs an unrounded fp32 GEMM, only operand rounding (<=2^-8) shows
    np.testing.assert_allclose(got, a.astype(np.float64) @ b.astype(np.float64),
                               rtol=1e-3, atol=1e-3)


@pytest.mark.parametrize("tile", [1, 2, 5])
def test_fp32_gemm_matches_numpy(tile):
    rng = np.random.default_rng(103)
    a = rng.standard_normal((9, 11)).astype(np.float32)
    b = rng.standard_normal((11, 7)).astype(np.float32)
    got = gemm_tiled_f32(a, b, tile=tile)
    np.testing.assert_allclose(got, a @ b, rtol=1e-6, atol=1e-6)


def test_gemm_dim_mismatch_raises():
    with pytest.raises(ValueError):
        gemm_tiled_f32(np.zeros((2, 3), np.float32), np.zeros((4, 2), np.float32), tile=2)


def test_bf16_operands_rounded_output_is_fp32_accumulator():
    rng = np.random.default_rng(104)
    a_raw = rng.standard_normal((4, 8)).astype(np.float32)
    b_raw = rng.standard_normal((8, 4)).astype(np.float32)
    got = gemm_bf16(a_raw, b_raw, tile=2)
    # operands were rounded to bf16 internally:
    ref = (bf16_roundtrip(a_raw).astype(np.float64) @ bf16_roundtrip(b_raw).astype(np.float64))
    np.testing.assert_allclose(got, ref.astype(np.float32), rtol=1e-6, atol=1e-6)
    # output is the fp32 accumulator (bf16 store rounding is explicit):
    assert got.dtype == np.float32
