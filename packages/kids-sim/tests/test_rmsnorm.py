"""RMSNORM differential tests vs NumPy reference."""

import numpy as np

from kids_sim.engine import rmsnorm
from kids_sim.numeric import bf16_roundtrip


def reference(x, g, eps):
    ms = np.mean(x.astype(np.float64) ** 2, axis=-1, keepdims=True)
    return (x / np.sqrt(ms + eps) * g).astype(np.float32)


def test_rmsnorm_fp32_vs_reference():
    rng = np.random.default_rng(201)
    x = rng.standard_normal((6, 16)).astype(np.float32)
    g = rng.standard_normal((16,)).astype(np.float32)
    y = rmsnorm(x, g, eps=1e-5, dtype="fp32")
    np.testing.assert_allclose(y, reference(x, g, 1e-5), rtol=1e-6, atol=1e-7)


def test_rmsnorm_bf16_output_is_bf16():
    rng = np.random.default_rng(202)
    x = rng.standard_normal((4, 8)).astype(np.float32)
    g = np.ones((8,), dtype=np.float32)
    y = rmsnorm(x, g, eps=1e-5, dtype="bf16")
    low = y.view(np.uint32) & np.uint32(0xFFFF)
    assert np.all(low == 0)


def test_rmsnorm_bf16_close_to_fp32():
    rng = np.random.default_rng(203)
    x = rng.standard_normal((4, 8)).astype(np.float32)
    g = rng.standard_normal((8,)).astype(np.float32)
    y16 = rmsnorm(x, g, eps=1e-5, dtype="bf16")
    y32 = rmsnorm(x, g, eps=1e-5, dtype="fp32")
    np.testing.assert_allclose(y16, y32, rtol=1e-2, atol=1e-2)


def test_rmsnorm_unit_gain_for_constant_rows():
    x = np.full((2, 4), 3.0, dtype=np.float32)
    g = np.ones((4,), dtype=np.float32)
    y = rmsnorm(x, g, eps=0.0, dtype="fp32")
    np.testing.assert_allclose(y, np.sign(x) * np.ones_like(x), rtol=1e-6)
    # bf16 of 1.0 is exact
    y16 = rmsnorm(x, g, eps=0.0, dtype="bf16")
    np.testing.assert_array_equal(y16, bf16_roundtrip(np.ones_like(x)))
