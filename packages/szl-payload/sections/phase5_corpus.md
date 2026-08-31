# Phase 5 — Corpus + Seal

The corpus is a versioned, sealed artifact. Training (Phases 7–8) consumes
sealed corpus versions only; there is no path from the registry to a trainer
that bypasses this phase.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## The 13-stage pipeline

1. **register** — registry entries from Phase 4 intake, tiers attached.
2. **license-tier** — re-check the tier at pipeline entry; BLOCKED and
   DISCOVER_ONLY rows exit here.
3. **fetch** — retrieve bytes; record retrieval evidence.
4. **digest** — chunked `sha256_file` over every fetched artifact.
5. **normalize** — encoding, format, and schema normalization.
6. **dedupe** — exact and near-duplicate detection; duplicates are clustered,
   and the cluster key is the source-repo lineage.
7. **decontaminate** — remove anything overlapping the sealed evaluation
   suites.
8. **filter** — language, format, and structural quality filters.
9. **quality-score** — per-document quality scoring with the rubric version
   recorded.
10. **reasoning-tag** — mark documents carrying reasoning traces.
11. **lineage-map** — assign every document its source-repo lineage key.
12. **split** — train/validation/test split **by source-repo lineage, never
    random**: every document sharing a lineage key lands in the same split,
    so near-duplicates cannot leak across the boundary. A random split across
    lineage duplicates is a hard failure.
13. **seal** — digest every file, canonicalize the corpus manifest with
    RFC 8785, freeze the corpus digest, and record the sealed version.

## Seal discipline

- **seal BEFORE training**: computing the test split after training has
  begun is a hard failure — the split must exist, frozen, before any
  optimizer step reads a byte.
- **Reasoning floor ≥ 75%.** The reasoning-tagged fraction of the training
  mix must measure at least 75% at seal time; a mix below the reasoning floor
  does not seal.
- Any post-seal change produces a new corpus version with a new seal digest;
  training receipts name the exact seal digest they consumed.
- The sealed manifest lists every file with its digest and lineage key, and
  the manifest itself is canonicalized before its digest is taken — the same
  Phase 1 rule, applied to the corpus.

UNKNOWN is never PASS: an unmeasurable reasoning ratio blocks the seal — the
corpus stays unsealed and training stays gated.
