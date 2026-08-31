# Phase 2 — Audit (estate inventory with completeness tracking)

The audit is the estate's ground truth. It is read-only, it runs in Pass 1,
and its output feeds the `inventory_complete` term of the computed
`publication_eligible` chain (Phase 9). A partial inventory reported as
complete is a hard failure.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## Two-source enumeration must agree

Inventory is taken from two independent sources and **two-source enumeration must agree**
before the audit is complete:

1. **GitHub** org `szl-holdings` (hyphenated — the unhyphenated form 404s).
   Search-validated count: exactly **100 repositories**, complete, not
   truncated. Prior views disagreed (38 in one view, 58 in another, 19 on the
   org README) — disagreeing counts are the signature of an incomplete
   enumeration, never a number to average.
2. **Hugging Face** org `SZLHOLDINGS` (case-sensitive — the lowercase form
   404s). Search found **129 Hub repos** (models, datasets, Spaces) with the
   response truncated after 71 items. One-call audits are structurally
   incomplete: paginate with `--limit 0`. Buckets are invisible to `author=`
   listings — only `list_user_repos(namespace=...)` surfaces them plus storage
   bytes — and collections are queried with `owner=`, never the author-filter
   form the lint gate forbids.

Any disagreement between the two sources, or between two runs of one source,
keeps `inventory_complete` false and blocks every downstream publish claim.

## Per-repo audit files

Every repository gets its own per-repo audit file under `audit/<repo>.md`
recording: default branch, visibility, last push, open PR count and mergeable
state, CI status, doctrine surface flags (V11 regression surfaces such as
`a11oy`, `a11oy-net`, `szl-receipt`, `governed-receipt-spec`), and the
evidence commands used. No per-repo audit file, no row in the matrix.

## REPOSITORY_MATRIX.csv

The rollup artifact is `REPOSITORY_MATRIX.csv` — one row per repo across both
sources:

```
repo,source,visibility,last_activity,open_prs,mergeable,ci_status,v11_surface,audit_file
```

Completeness rule: matrix row count must equal the validated count from each
source (100 GitHub + the fully paginated Hub count). The matrix is digested
and the digest is carried into the Phase 9 attestation subjects.

## Standing reconciliations

- Repos described but not found in any listing (`szl-substrate`,
  `szl-receipt-attn` are cited in the Minewing RFQ §28) are recorded as
  UNVERIFIED, and the RFQ provenance claim stays open until each URL is
  verified or replaced with "available under NDA".
- Repos that exist but are absent from the README's 19-repo view
  (`szl-lake`, `szl-provctl-live`, `szl-energy-attest`, `yarqa`, `immune`,
  `killinchu`, `rosie`, `developers`) are matrix rows like any other.
- Demand signals are recorded, not hypothesized: `killinchu-osint-corpus` at
  81.3K downloads is the only real demand signal across the estate and feeds
  Phase 4 with its restrictive license intact.

UNKNOWN is never PASS: a repo that cannot be enumerated is UNKNOWN, and the
audit says so.
