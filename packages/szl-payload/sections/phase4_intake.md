# Phase 4 — Intake (source registry + license tiers A-D)

Every external artifact enters the estate through the source registry with an
origin URL, a license reading, retrieval evidence, and a byte digest. Intake
is where lawful ingestion is enforced: nothing reaches the corpus (Phase 5)
without an admission state, and the admission state is derived from the
license tier, never from how useful the data looks.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## License tiers A-D

| Tier | License class | Admission state |
| --- | --- | --- |
| A | Permissive OSI (Apache-2.0, MIT, BSD) | TRAINING_ALLOWED |
| B | Attribution / share-alike (CC-BY-4.0) | TRAINING_ALLOWED, attribution ledger entry required |
| C | Restrictive or ambiguous (`license:other`, NC variants, custom terms) | DISCOVER_ONLY |
| D | Unlicensed or unreadable terms | BLOCKED |

## Admission states

- **DISCOVER_ONLY** — the artifact may be indexed, searched, and referenced;
  it never enters a training corpus. Recorded with the registry entry and the
  exact terms text that forced the tier.
- **TRAINING_ALLOWED** — corpus-eligible. The registry entry carries the
  license, the obligations ledger (attribution, share-alike), and the admitting
  policy version.
- **BLOCKED** — not ingested at all beyond the registry stub recording why.

The flow is one-way until terms change: DISCOVER_ONLY → TRAINING_ALLOWED
requires a new license reading with evidence; nothing flows BLOCKED →
anywhere without new terms.

## Worked example (standing rule)

`killinchu-osint-corpus` is the estate's only real demand signal (81.3K
downloads) and carries `license:other`. It is tier C: REFERENCE_ONLY /
EVALUATE_ONLY — **not trainable until the terms are resolved**, no matter how
strong the demand signal is. Admitting a `license:other` dataset to training
is on the V13 hard-failure list; the intake receipt for every training-row
decision must name the tier and the policy version that allowed it.

Every intake decision emits a receipt: origin, digest, license tier, admission
state, admitting policy version. UNKNOWN license reading means tier D —
UNKNOWN is never PASS.
