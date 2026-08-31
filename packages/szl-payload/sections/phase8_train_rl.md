# Phase 8 — Train RL (GSPO)

Reinforcement learning runs after SFT, under the same Pass 2 authorization
and GPU gate, against the same sealed corpus and sealed evaluation suite.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## GSPO configuration

- Algorithm: **GSPO** with `importance_sampling_level="sequence"`.
  Sequence-level importance sampling is the point of the algorithm;
  token-level importance sampling reintroduces exactly the variance GSPO
  exists to remove. Any config drift away from sequence level is a defect,
  not a tuning choice.
- Pins from Phase 7 apply unchanged (`unsloth` / `trl` / `transformers` /
  `SZL_SEMCONV_COMMIT`).

## Reward shaping

- **Over-refusal penalty**: a policy that refuses governed-but-legitimate
  requests is penalized. Running RL with no over-refusal penalty is on the
  V13 hard-failure list — it teaches the model that refusing everything is
  the safe optimum, and that policy fails the sealed refusal benchmarks.
- **Refusal-then-leak nets -3.0**: refusing a governed request and then
  leaking the governed content in the same episode scores worse than either
  failure alone. The composite failure is the one that matters operationally,
  so the reward makes it the most expensive outcome on the board.

## Evaluation

Sealed eval runs after RL against the frozen baseline from Phase 7 — the
delta is still the only claim, now with refusal-benchmark deltas reported
alongside capability deltas. A capability gain purchased with a refusal
regression is reported as both, never netted into one number.

UNKNOWN is never PASS: an episode that cannot be scored is UNKNOWN and is
excluded from averages with its count reported, not silently dropped.
