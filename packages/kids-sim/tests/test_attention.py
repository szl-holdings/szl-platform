"""ATTN_CAUSAL and YARQA_COMPARTMENT tests vs NumPy references."""

import numpy as np

from kids_sim.engine import attention_causal, attention_yarqa


def ref_causal(q, k, v, scale):
    s = q.shape[0]
    scores = (q @ k.T) * scale
    mask = np.triu(np.ones((s, s), bool), 1)
    scores = np.where(mask, -np.inf, scores)
    e = np.exp(scores - scores.max(axis=-1, keepdims=True))
    p = e / e.sum(axis=-1, keepdims=True)
    return p @ v


def test_causal_matches_reference():
    rng = np.random.default_rng(301)
    s, d = 7, 8
    q, k, v = (rng.standard_normal((s, d)).astype(np.float32) for _ in range(3))
    got = attention_causal(q, k, v, scale=d**-0.5)
    np.testing.assert_allclose(got, ref_causal(q, k, v, d**-0.5), rtol=1e-5, atol=1e-6)


def test_causal_mask_blocks_future():
    # If keys/values of FUTURE tokens change, earlier outputs must not move.
    rng = np.random.default_rng(302)
    s, d = 5, 4
    q, k, v = (rng.standard_normal((s, d)).astype(np.float32) for _ in range(3))
    out1 = attention_causal(q, k, v, 1.0)
    k2, v2 = k.copy(), v.copy()
    k2[-1], v2[-1] = 99.0, -99.0  # corrupt the LAST token only
    out2 = attention_causal(q, k2, v2, 1.0)
    np.testing.assert_allclose(out1[:-1], out2[:-1], rtol=1e-6, atol=1e-6)


def test_yarqa_canal_isolation():
    # Tokens in different canals must not influence each other: changing a
    # key/value inside canal B leaves canal A outputs unchanged.
    rng = np.random.default_rng(303)
    s, d = 6, 4
    q, k, v = (rng.standard_normal((s, d)).astype(np.float32) for _ in range(3))
    comps = [[0, 1, 2], [3, 4, 5]]
    out1 = attention_yarqa(q, k, v, comps)
    k2, v2 = k.copy(), v.copy()
    k2[5], v2[5] = 42.0, -42.0  # perturb inside canal B
    out2 = attention_yarqa(q, k2, v2, comps)
    np.testing.assert_allclose(out1[:3], out2[:3], rtol=1e-6, atol=1e-6)  # canal A untouched
    assert not np.allclose(out1[3:], out2[3:])  # canal B moved


def test_yarqa_is_causal_within_canal():
    rng = np.random.default_rng(304)
    s, d = 4, 4
    q, k, v = (rng.standard_normal((s, d)).astype(np.float32) for _ in range(3))
    comps = [[0, 1, 2, 3]]
    out1 = attention_yarqa(q, k, v, comps)
    k2, v2 = k.copy(), v.copy()
    k2[3] = 7.0  # later token in same canal
    v2[3] = -7.0
    out2 = attention_yarqa(q, k2, v2, comps)
    np.testing.assert_allclose(out1[:3], out2[:3], rtol=1e-6, atol=1e-6)


def test_yarqa_uncompartmented_token_attends_only_to_itself():
    rng = np.random.default_rng(305)
    s, d = 3, 4
    q, k, v = (rng.standard_normal((s, d)).astype(np.float32) for _ in range(3))
    out = attention_yarqa(q, k, v, [[0, 1]])  # token 2 in no canal
    np.testing.assert_allclose(out[2], v[2], rtol=1e-6, atol=1e-6)


def test_yarqa_rejects_out_of_range_index():
    q = np.zeros((2, 4), np.float32)
    with np.testing.assert_raises(ValueError):
        attention_yarqa(q, q, q, [[0, 5]])
