# SZL Platform

<!-- szl:header v1 -->
<!-- Native identity: szl-brand@4309f6fce89179331b0b3ed8c99494e76c5be256; Orbit v2 icon. -->
<p>
  <a href="https://github.com/szl-holdings">
    <img src="https://raw.githubusercontent.com/szl-holdings/szl-brand/4309f6fce89179331b0b3ed8c99494e76c5be256/kit/logos/orbit-v2/suite/szl-icon-32.svg" alt="SZL Holdings — Orbit v2" width="32" height="32" />
  </a>
</p>

**Control before action. Evidence after.**

[Product](https://a-11-oy.com) · [Proof](https://a11oy.net) · [GitHub organization](https://github.com/szl-holdings)
<!-- /szl:header -->

**Governed-AI engineering surface: every artifact ships with a receipt, every claim in the receipt ledger is re-computable, and `UNKNOWN` is never `PASS`.**

This monorepo is the Python engineering layer of the SZL Holdings estate. It exists so that
anyone — an investor, an auditor, a new engineer, or an adversary — can clone one tree,
run one command, and independently verify everything the estate asserts about itself.

## Install and verify

```bash
python3 -m venv .venv && . .venv/bin/activate   # make uses `python3 -m pip`
make install                 # editable-installs szl-receipts first, then every package
make lint                    # ruff over packages/ and alignment/
make test                    # one pytest run per package (packages own their conftest)
make verify idempotent       # payload verify, then build twice and diff byte-for-byte
```

These are the same commands CI runs (`.github/workflows/ci.yml`, Python 3.11, 3.12 and 3.13).
CI also installs the optional LiteLLM extra
(`pip install -e 'packages/szl-evidence-litellm[litellm]'`) so the LiteLLM integration tests
run instead of skipping. Any single package installs on its own with
`pip install -e '<dir>[test]'` (any `packages/*` directory, or `alignment`); packages that
depend on `szl-receipts` need `pip install -e packages/szl-receipts` first, because it is not
published to an index.

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
| `packages/szl-estate` | Estate control plane: two-source GitHub enumeration that must agree, per-repo audit files, `doctor` (credentials/DNS/tunnels), `verify-claims` (re-runs the org's numeric claims, opens `CLAIM_DRIFT` findings) | core |
| `packages/szl-claims-api` | FastAPI service behind `GET /api/cps/claims`: serves each public numeric claim with `{claimed, actual, last_run, drift, receipt_id}` from the `verify-claims` output | service |
| `packages/kids-sim` | KIDS v0.1 golden simulator — the executable specification for the KHIPU instruction set (GEMM, RMSNorm, DMA, attention) with differential tests against NumPy | core |
| `packages/szl-evidence-litellm` | LiteLLM evidence-plane plugin: tamper-evident DSSE receipt per inference request, fail-closed policy mode, async batched sink | core |
| `packages/szl-iso42001` | Free, offline ISO/IEC 42001 + EU AI Act Article-50 readiness checker (44 controls) that emits a receipt of its own findings | core |
| `packages/szl-adversarial` | Public attack harness for the receipt chain: forgery, replay, truncation, reorder, and canonicalization attacks — run it before an auditor does | core |
| `packages/szl-beacon` | Beacon edge-node reference: the receipt-emitting field unit for maritime/disaster/legal evidence collection | reference |
| `alignment/` (`szl-alignment`) | Org alignment engine: inspects repos and plans/applies the estate standard (doctrine header, `SECURITY.md`, the forbidden-domain gate, base Python CI) from `alignment/templates/` | tooling |

## Why this exists

Governance platforms ask you to trust a dashboard. This estate asks you to **run the
verifier**. The receipts library is roughly 2,300 lines of Python
(`wc -l packages/szl-receipts/src/szl_receipts/*.py`) whose only runtime dependency is
`cryptography` — there is no service to trust. The attack harness is public. If any of it
fails on your machine, that failure is the honest output — we would rather print `BLOCKED`
than a green lie.

## Layout

```
packages/            independently installable Python packages (the code)
alignment/           szl-alignment engine + the estate-wide templates it installs
docs/                doctrine, readiness setup, competitor teardowns, the GAR Internet-Draft
artifacts/           committed audit / claims / enumeration snapshots (dated evidence)
site/                proof explorer, published to GitHub Pages by pages-sync.yml
run/                 per-service working dirs (claims API store)
scripts/             operator scripts (tunnel heal, mesh restart, node bootstrap, ACME DNS-01, claims adapter)
.github/workflows/   CI that runs the same commands you can run locally
```

Build outputs are derived and never committed: the payload builder writes
`packages/szl-payload/dist/` (git-ignored); `make clean` removes it and caches only.

## For investors

Start with `docs/OPERATOR_PACKET.md`, then `packages/szl-adversarial/README.md`
(the claim, attacked: `python -m szl_adversarial run` writes its report and a self-receipt,
`attack-report.unsigned.json` unless an operator key signs it). The org audit under
`artifacts/audits/` (`REPOSITORY_MATRIX.csv`, `ESTATE_SUMMARY.md`) is a **dated snapshot**:
an offline-mode run from 2026-08-31 covering 103 repositories, with the second
enumeration source replayed from a fixture, and no receipt attached. Re-run it live with
`make audit` (needs `GH_TOKEN`) before quoting any number from it.

## For engineers

Start with `packages/szl-receipts/README.md`. Everything else in the tree composes that
one primitive. All packages: Python ≥ 3.11, type-annotated, ruff-clean (`make lint`), and
tested offline.

For the current solo-maintainer merge controls and how to verify them, see
[`docs/CHANGE_CONTROL.md`](docs/CHANGE_CONTROL.md).

## Proof boundary

What `make test` / `make verify idempotent` and CI establish, on Python 3.11–3.13:

- the receipt core's canonicalization, signing, verification and chain checks behave as
  their tests specify;
- the adversarial harness's 19 non-limitation attacks are blocked by the current
  `szl-receipts` code, and its one documented limitation (dropping the newest entries of a
  chain without an external anchor) is reported as a limitation, not hidden;
- the payload build is deterministic (built twice, byte-identical);
- the forbidden-domain workflow template fails closed (its tests execute the template's
  own script, including the scanner-error and scanner-missing cases).

What they do **not** establish:

- that any deployed service (the claims API, a LiteLLM proxy, a Beacon node, the proof
  explorer at https://dev.a-11-oy.com/) is running or configured as described;
- that the committed snapshots under `artifacts/` and `site/data/` describe the
  organization today — they are dated (see above);
- that anything is signed: no receipt committed in this tree carries a signature (no
  committed JSON/JSONL file has a non-empty `signatures` array); signing needs an operator
  key at run time (e.g. `--sign-with`);
- certification of any kind: `szl-iso42001` is a readiness self-assessment, not an audit;
- that a governed model's answers are correct — a receipt proves integrity and signer
  identity, not model quality.

## Links

- Source: https://github.com/szl-holdings/szl-platform
- Proof explorer (GitHub Pages from `site/`): https://dev.a-11-oy.com/
- Hugging Face organization (the HF counts `szl-estate verify-claims` re-computes):
  https://huggingface.co/SZLHOLDINGS

License: Apache-2.0 (`LICENSE`) unless a package states otherwise. Six package manifests
(`szl-receipts`, `szl-payload`, `szl-adversarial`, `szl-beacon`, `szl-claims-api`,
`szl-evidence-litellm`) currently declare `Proprietary`.
