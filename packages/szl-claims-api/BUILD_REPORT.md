# szl-claims-api — build report (2026-08-31)

## Gate results

- `python3 -m pytest packages/szl-claims-api -q` — **41/41 pass** (Python 3.14.3)
- `python3 -m ruff check packages/szl-claims-api` — **clean** (root policy E,F,I,W,UP,B,S)
- Live smoke: `seed` → `serve` (uvicorn) → `/healthz`, `/api/cps/claims`,
  `/api/cps/claims/{id}/receipt` (passes `szl_receipts.verify_receipt` with zero
  findings), `/api/cps/report.md`, 404 on unknown claim id — all verified over real HTTP.
- Real `refresh_from_estate` boundary exercised once against installed szl-estate 0.1.0:
  adapted the estate's claims.json into this service's schema, strictly validated it,
  atomically replaced the file. Result was honest: static claims UNKNOWN, and three real
  DRIFTs detected by the estate runner (monorepo_packages observed 9 vs claimed 126 in
  the sandbox checkout; hf_models observed 44 vs claimed 43; hf_datasets observed 30 vs
  claimed 28). org_repos — unknown to szl-estate's registry — stayed UNKNOWN and was
  not dropped.

## Files (all under packages/szl-claims-api/)

```
pyproject.toml                         src layout, deps fastapi>=0.110 uvicorn>=0.29 szl-receipts
README.md                              the why: stale self-reported numbers are the first diligence attack
BUILD_REPORT.md                        this file
src/szl_claims_api/__init__.py         public surface + doctrine docstring
src/szl_claims_api/__main__.py         python -m szl_claims_api
src/szl_claims_api/store.py            strict loader, OK/UNAVAILABLE/INVALID, StoreStats, estate refresh boundary
src/szl_claims_api/receipts.py         content-hash-keyed GovernedAction/v1 receipt minter
src/szl_claims_api/app.py              FastAPI: /healthz, /api/cps/claims[/{id}[/receipt]], /api/cps/report.md
src/szl_claims_api/seed.py             seed registry -> claims.json writer
src/szl_claims_api/cli.py              serve / seed / print
src/szl_claims_api/claims_registry.seed.json  10 real public claims, sources attributed
tests/conftest.py
tests/fixtures/claims.sample.json      one PASS, one DRIFT, one UNKNOWN
tests/test_store.py  tests/test_receipts.py  tests/test_app.py  tests/test_cli.py
```

## Design decisions

1. **File-based contract, strictly validated.** claims.json is a top-level list of
   exactly eight keys; verdict ∈ {PASS, DRIFT, UNKNOWN}; unique ids; timezone-aware
   last_run; PASS/DRIFT require non-null observed AND last_run; UNKNOWN forbids
   observed. A file that fails validation is refused (state INVALID) — an invalid
   file is never laundered into served numbers.
2. **Honest degradation serves the seed, not silence.** Missing file → UNAVAILABLE;
   endpoints answer with all 10 seeded claims marked UNKNOWN with a note, never
   fabricated numbers. UNKNOWN receipts are still minted and still verify.
3. **Receipts are content-addressed.** Cache key = sha256 of the claim's canonical
   (RFC 8785) bytes; the same digest is the receipt's subject. Any content change —
   observed value, last_run, anything — mints a NEW receipt id; stale-receipt reuse
   is structurally impossible. `created_at` pins to the claim's `last_run`
   (UNKNOWN claims use a deterministic 1970 epoch placeholder, never "now"), so a
   verified claim's receipt is reproducible by anyone holding the claims file.
   Policy digest = sha256 of the canonical seed registry (bytes, not a filename);
   policy version = the claim's last_run ("unverified" for UNKNOWN).
4. **Verdict→outcome mapping in one place:** PASS→PASS, DRIFT→FAIL (a measurement
   contradicting the claim), UNKNOWN→UNKNOWN (never passing).
5. **No server-side computation.** `claimed`/`actual` are quoted verbatim from the
   file; the only computed values are receipt digests and response timestamps
   (generated_at / server_time), which describe the serving event, not the claim.
6. **Optional szl-estate boundary, file-to-file.** `refresh_from_estate` runs the
   estate's runner into a temp dir, adapts its `{"results": ...}` file into this
   service's schema (typed `expected` restored from the seed registry; claims the
   estate doesn't know are merged in as UNKNOWN so a refresh can never silently
   drop a public claim), strictly validates, then atomically replaces claims.json.
   Any failure — import, runner, validation — returns (False, note) and leaves the
   existing file byte-identical. BLOCKERS_HEADER is duplicated verbatim rather than
   imported, keeping the estate boundary purely file-based.
7. **report.md layout is literal:** title, then (any DRIFT) the exact line
   `BLOCKERS THAT OUTRANK ALL COSMETIC WORK` with drifting claims listed first, or
   (no DRIFT) the claims table. Store state, totals, and the server_time honesty
   note form the footer.

## Pre-existing finding (out of scope, not caused by this package)

Repo-wide `python3 -m pytest packages` collection was already broken before this
package existed: 4 import-file-mismatch errors among szl-beacon / szl-iso42001 /
szl-payload / szl-receipts (duplicate test basenames without tests/__init__.py;
szl-adversarial avoids it via __init__.py). This package follows the mandated
filenames (test_store/test_receipts/test_app/test_cli.py), which join the same
pre-existing collision pattern in whole-repo runs (4 → 7 errors). Fixing it
requires touching other packages' tests dirs or the root pytest config (e.g.
`--import-mode=importlib`), both outside this task's "touch nothing outside
packages/szl-claims-api/" boundary. The mandated gate
`pytest packages/szl-claims-api -q` passes 100%.
