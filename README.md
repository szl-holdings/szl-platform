# SZL Platform

**Governed-AI engineering surface: every artifact ships with a receipt, every claim is re-computable, and `UNKNOWN` is never `PASS`.**

This monorepo is the Python engineering layer of the SZL Holdings estate. It exists so that
anyone — an investor, an auditor, a new engineer, or an adversary — can clone one tree,
run one command, and independently verify everything the estate asserts about itself.

```
pip install -e packages/szl-receipts
make install && make test
```

## The doctrine (three rules, no exceptions)

1. **Prove, don't assert.** Every artifact — a receipt, a payload, an audit row, a model
   weight file, a bitstream — is either accompanied by a verifiable receipt or honestly
   named `*.unsigned.json`. An empty `signatures` array is never called "signed".
2. **UNKNOWN is never PASS.** Outcomes live in `PASS | WARN | FAIL | BLOCKED | UNKNOWN`.
   Promotion logic treats `UNKNOWN` as non-passing everywhere, including this README's CI.
3. **Determinism or it didn't happen.** Builders embed no timestamps in deterministic
   bodies; time lives only in runtime receipts. `make idempotent` builds twice and diffs.

## Packages

| Package | What it is | Status |
|---|---|---|
| `packages/szl-receipts` | RFC 8785 (JCS) canonicalization, chunked SHA-256 byte digests, DSSE/in-toto envelopes, Ed25519 sign/verify, append-only receipt chains, honest unsigned naming | core |
| `packages/szl-payload` | Deterministic payload builder: sections → `dist/SZL_MASTER_PAYLOAD_V14.md` under hard compile gates (forbidden domains, banned claims, secret-logging scan, DNS-first ordering) | core |
| `packages/szl-estate` | Estate control plane: two-source GitHub enumeration that must agree, per-repo audit files, `doctor` (credentials/DNS/tunnels), `verify-claims` (re-runs the org's numeric claims, opens `CLAIM_DRIFT` findings), live `GET /api/cps/claims` | core |
| `packages/kids-sim` | KIDS v0.1 golden simulator — the executable specification for the KHIPU instruction set (GEMM, RMSNorm, DMA, attention) with differential tests against NumPy | core |
| `packages/szl-evidence-litellm` | LiteLLM evidence-plane plugin: tamper-evident DSSE receipt per inference request, fail-closed policy mode, async batched sink | core |
| `packages/szl-iso42001` | Free, offline ISO/IEC 42001 + EU AI Act Article-50 readiness checker that emits a signed receipt of its own findings | core |
| `packages/szl-adversarial` | Public attack harness for the receipt chain: forgery, replay, truncation, reorder, and canonicalization attacks — run it before an auditor does | core |
| `packages/szl-beacon` | Beacon edge-node reference: the receipt-emitting field unit for maritime/disaster/legal evidence collection | reference |

## Why this exists

Governance platforms ask you to trust a dashboard. This estate asks you to **run the
verifier**. The receipts library is a few hundred lines with no service dependency; the
attack harness is public; the audit of our own org ships in `artifacts/audits/` next to
the receipts that prove when it ran and what it saw. If any of it fails on your machine,
that failure is the honest output — we would rather print `BLOCKED` than a green lie.

## Layout

```
packages/            independently installable Python packages (the code)
docs/                doctrine, readiness setup, competitor teardowns (the why)
artifacts/           generated audits, receipts, rollback bundles (the proof)
dist/                deterministic build outputs — derived, never hand-edited
.github/workflows/   CI that runs the same commands you can run locally
```

## For investors

Start with `docs/OPERATOR_PACKET.md`, then `packages/szl-adversarial/README.md`
(the claim, attacked), then `artifacts/audits/REPOSITORY_MATRIX.csv` (the estate,
measured). Every number in those documents carries the receipt of the run that produced
it.

## For engineers

Start with `packages/szl-receipts/README.md`. Everything else in the tree composes that
one primitive. All packages: Python ≥ 3.11, typed, ruff-clean, tested offline.

License: Apache-2.0 unless a package states otherwise. See `LICENSE`.
