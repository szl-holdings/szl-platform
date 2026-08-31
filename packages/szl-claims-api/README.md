# szl-claims-api — the live Covenant Proof Standard service

For a company whose thesis is *"prove what your model decided"*, stale
self-reported numbers are the first diligence attack. A diligence team opens
the org README, sees "218/218 tests", and asks the only question that matters:
**says who, and when did you last check?** If the answer is a human's memory,
the company's own proof standard indicted itself.

`szl-claims-api` closes that hole. It serves every public numeric claim SZL
Holdings makes — test counts, table counts, model counts, latency budgets —
each with `{claimed, actual, last_run, drift, receipt_id}`. The organization's
own marketing, held to its own proof standard, at:

```
GET /api/cps/claims
```

## The honesty contract

This service **reports** recomputations; it never **invents** them:

- Every number served is quoted verbatim from a claims file on disk
  (`SZL_CLAIMS_FILE`, default `artifacts/claims/claims.json`). The file is
  written by an independent runner — `szl-estate verify-claims` — that
  recomputes what can be recomputed. This service computes no claim numbers
  itself, ever.
- `UNKNOWN` is a first-class, honest state. A claim that has not been
  recomputed reports `verdict: "UNKNOWN"`, `actual: null` — never a
  remembered number dressed up as a current one.
- If the claims file is **missing**, the store state is `UNAVAILABLE` and
  every seeded claim reports `UNKNOWN` with a note. If the file is present
  but fails strict validation, the state is `INVALID` and the same honest
  fallback applies. Fabricated numbers are structurally impossible.
- Each claim carries a `GovernedAction/v1` receipt (`szl-receipts`) built at
  read time: `action: "claim.verify"`, outcome mapped `PASS→PASS`,
  `DRIFT→FAIL`, `UNKNOWN→UNKNOWN`, the claim's canonical bytes as the
  digested subject, and the claim's source as evidence. Receipts are cached
  by claim content hash: a claim whose `observed` value changed gets a **new**
  receipt — never a reused one. `created_at` is pinned to the claim's
  `last_run`, so a verified claim's receipt is reproducible by anyone holding
  the claims file.

## Install

```bash
pip install -e packages/szl-receipts
pip install -e packages/szl-claims-api
```

## Use

```bash
# Seed an honest initial claims file (everything UNKNOWN until szl-estate
# recomputes):
python -m szl_claims_api seed --out artifacts/claims

# Serve:
python -m szl_claims_api serve --host 127.0.0.1 --port 8000
# optionally attempt a one-shot szl-estate recomputation at startup
# (optional boundary; degrades cleanly when szl_estate is not importable):
python -m szl_claims_api serve --refresh

# Print the same view the API serves:
python -m szl_claims_api print --json
```

## Endpoints

| Route | Meaning |
|---|---|
| `GET /healthz` | Liveness, store state, server time. |
| `GET /api/cps/claims` | `{generated_at, store_state, note, stats, claims:[{claim_id, claimed, actual, last_run, verdict, drift, receipt_id, receipt_url}]}` |
| `GET /api/cps/claims/{claim_id}` | One claim, with description/source/evidence. 404 on unknown id. |
| `GET /api/cps/claims/{claim_id}/receipt` | The full `GovernedAction/v1` receipt JSON; passes `szl_receipts.verify_receipt` with zero findings. |
| `GET /api/cps/report.md` | `text/markdown` report. When any verdict is `DRIFT`, the line directly under the title is exactly `BLOCKERS THAT OUTRANK ALL COSMETIC WORK` and the drifting claims are listed first; otherwise the claims table follows the title. Ends with an honest `server_time` note. |

CORS is open and read-only (`GET` only) — these numbers are meant to be
fetched by anyone's diligence tooling.

## The claims file contract

The boundary between this service and `szl-estate` is a **file**, not an
import. `claims.json` is a top-level JSON list; each record is exactly:

```json
{
  "claim_id": "monorepo_packages",
  "description": "Installable packages in the platform monorepo",
  "source": "org README verified 2026-05-12",
  "expected": 126,
  "observed": 126,
  "verdict": "PASS",
  "evidence": "counted files matching '*/pyproject.toml' under packages/ in this run",
  "last_run": "2026-08-31T07:30:00Z"
}
```

Validation is strict: no missing or extra keys, `verdict ∈ {PASS, DRIFT,
UNKNOWN}`, unique `claim_id`s, `last_run` a timezone-aware ISO-8601 string or
`null`, and — the honesty invariants — a `PASS`/`DRIFT` verdict requires a
non-null `observed` **and** a `last_run`, while `UNKNOWN` requires
`observed: null` (you cannot know a number you did not compute).

## Development

```bash
pip install -e packages/szl-claims-api[dev]
python3 -m pytest packages/szl-claims-api -q
python3 -m ruff check packages/szl-claims-api
```
