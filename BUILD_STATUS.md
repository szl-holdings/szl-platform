# SZL-PLATFORM — Build Status (payload closeout)

**Closed out:** 2026-09-02 · Doctrine v11 · additive record; supersedes nothing.

## What the 2026-08-31 V14 spin-up produced

- Monorepo scaffold: 8 installable packages (`szl-receipts`, `szl-payload`, `szl-estate`, `kids-sim`, `szl-evidence-litellm`, `szl-iso42001`, `szl-adversarial`, `szl-beacon`) with one-command local verification (`make install && make test`).
- Deterministic payload builder under hard compile gates; estate audit control plane with two-source GitHub enumeration; KIDS v0.1 golden simulator with NumPy differential tests.
- `site/` proof explorer: zero-CDN single-page surface, in-browser SHA-256 verification, adversarial run committed (`receipt chain resisted 19/19 non-limitation attacks`). Full log: `SITE_BUILD_RESULT.md`.
- GitHub Pages dev surface live at dev.a-11-oy.com (legacy build — org SHA-pin policy forbids official pages actions).

## Post-payload repairs (all merged)

| PR | Repair |
|---|---|
| #1 | SHA-pin v14 workflow templates, dev-extra install, scoped ruff |
| #2 | Base gate owns `tests/` only, skips honestly when absent |
| #3 | Estate-count assertions rebound to refreshed seed |
| #4 | `hf_datasets` source assertion wrapped under 100-col gate |
| #5 | Ruff step name quoted in base-python-ci template |
| #6 | Explicit defer marker for the base gate |
| #7 | pages-sync fetches `gh-pages` before worktree add |
| #8 | Bounded flusher cancel-wait in `EvidenceSink.aclose` (py3.11 hang) + regression test |

## Disposition

- All gates (install, lint, deterministic tests, verification, idempotency) run in CI on every push and pull request; the #8 regression test is verified on Python 3.11 and 3.12.
- Claims posture unchanged: `UNKNOWN` is never `PASS`; 9 claims on the site wall read 0 PASS / 3 DRIFT / 6 UNKNOWN at build time — honest output, not a defect.

## Metadata gap — closed

The GitHub repository description was never set by the payload. Set 2026-09-02 to:
`SZL Platform — governed-AI engineering monorepo: receipt-first packages, estate audit control plane, KIDS simulator, adversarial harness. Prove, don't assert. Doctrine v11 / V14.`

## Remaining work

Nothing software-gated remains from the payload itself. Estate-level owner actions (credential rotation, tunnel ownership) are tracked in their own repos and issues, not here.
