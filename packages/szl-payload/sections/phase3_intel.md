# Phase 3 — Intel (weekly trending delta)

Intel is a **weekly trending delta**, not a static snapshot: the report is
what *changed* since the last run — claims that drifted, repos that moved,
demand signals that shifted — with evidence and a receipt per assertion.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## verify-claims

The org README's numeric claims are all stamped "verified 2026-05-12" —
months stale. The `verify-claims` command re-runs each claim, diffs the
measured value against the README, and opens one **CLAIM_DRIFT** finding per
mismatch. The claim set:

| Claim | Stamped value |
| --- | --- |
| ouroboros tests | 218/218 |
| platform tests across 76 packages | 1,220/1,220 |
| MCP end-to-end | 27/27 |
| database tables | 848 |
| API endpoint declarations | 5,524 |
| monorepo packages | 126 |
| Λ overhead | ≤ 0.59 ms median |

Roughly twenty hard numeric claims in total, plus the correction-ledger entry
(Putnam 0/12) tracked in the PR queue (Phase 10).

## Live claims endpoint

The target shape is a live `GET /api/cps/claims` endpoint returning, per
assertion:

```json
{"claimed": "value in the README", "actual": "measured value", "last_run": "run id", "drift": true, "receipt": "receipt id"}
```

A claim that cannot be re-measured reports `actual: UNKNOWN` — never the
stale value wearing a fresh date.

## Trend inputs

Weekly inputs: the Phase 2 matrix delta (repos added/removed/renamed, CI
state changes), Hub demand-signal movement on the audited assets, PR queue
movement from Phase 10, and drift findings from Phase 6. Every line in the
weekly report cites its evidence command; a trend without evidence is
editorial, and editorial does not ship.

UNKNOWN is never PASS: an unmeasured claim is reported UNKNOWN, which keeps
the corresponding README line annotated until re-verified.
