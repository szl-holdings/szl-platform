# Phase 7 — Train SFT

Training is a Pass 2 activity: `TRAINING=false` by default, and this phase
runs only under an authorized pass with the GPU gate (position 10 in the
Codex execution manifest) explicitly opened.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## Baseline-first eval

Before any fine-tuning step, run the **unmodified base** model on the
**sealed suite** from Phase 5 and record the scores. That baseline-first eval
is the measurement the entire training program stands on: **the delta is the only claim**.
An absolute post-training score without the frozen baseline
delta is marketing, not evidence, and it does not ship. The existing
`SZL-Khipu-1.5B` baseline is run before any new model so the estate always
has a current, sealed reference point.

## Pins

Every training run pins and records: `unsloth`, `trl`, `transformers`, and
`SZL_SEMCONV_COMMIT`. An unpinned run is an unrepeatable run, and an
unrepeatable run cannot be attested in Phase 9.

## Inputs and receipts

- Input corpus: a sealed corpus version from Phase 5, named by seal digest.
  Any corpus change re-seals (new version) and re-baselines.
- Every run emits a receipt: base model digest, sealed corpus digest, pin
  set, hyperparameters, sealed-suite baseline scores, post-run scores, and
  the computed delta.
- Low-cost pilots (PEFT/LoRA-class runs on small bases) are the default
  shape; a full run requires its own authorization packet.

UNKNOWN is never PASS: a metric that cannot be measured on the sealed suite
is reported UNKNOWN and blocks any improvement claim for that metric.
