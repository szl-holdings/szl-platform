# Frontier Readiness — Operating Setup

**SZL Holdings · 2026-08-31 · This is a setup document, not a roadmap. Everything in §1–§3 exists and runs today. Everything in §6 is a dated obligation with an owner: you.**

---

## 1. Verified live, today (measured, not recalled)

| Surface | State | Evidence |
|---|---|---|
| `a11oy.net` (proof origin) | **200, serving** | 4× GitHub Pages A records `185.199.108–111.153`, DNS-only |
| `www.a11oy.net` | 301 → canonical | CNAME `szl-holdings.github.io` |
| `a-11-oy.com` (command center) | **200, serving** | Cloudflare-proxied |
| `szlholdings-a11oy.hf.space` | **200** | HF Space live |
| `gpu2.a-11-oy.com` | **403 — correct** | Cloudflare Access is working; do not remove it to turn a probe green |
| `szl.dev` | **FAIL — no delegation** | `dig NS szl.dev` → empty; NXDOMAIN confirmed today; registrar problem, not a records problem |
| GitHub org | **101 repos** enumerated | Two-source rule: `gh` GraphQL OK; REST cross-check rate-limited → honestly PARTIAL. The 101st repo (`szl-v14`) appeared mid-audit and was caught by the tooling |
| Hugging Face org `SZLHOLDINGS` | 44 models / 38 datasets / 47 Spaces | Live search 2026-08-31; authenticated as `betterwithage` (PRO), org role admin, **team plan — custom Space domains are possible** |
| Open PRs org-wide | **3** (all in `a11oy`) | `gh search prs`, 2026-08-31 |
| Forbidden domain `a11oy.com` | **19 true violations in 3 repos** (incl. live `szl-command-lab/src/lib/publish.ts` `host:`/`href:` entries + two `publish-map.json` copies) | Content-level scan of all 65 non-archived repo clones; prohibition/guard contexts classified separately |
| Licenses | All repos carry a license file; GitHub recognizes none of the custom ones | Mixed Apache-2.0 / `LicenseRef-SZL-Proprietary`; standardize SPDX |
| Org README claims | **3 live CLAIM_DRIFTs** | `hf_models` 43→44, `hf_datasets` 28→30 (measured today), `monorepo_packages` needs recompute inside `platform` checkout |

## 2. Built today, tested, running (this monorepo)

| Package | What it is | Proof |
|---|---|---|
| `szl-receipts` | RFC 8785 JCS, chunked byte digests, DSSE/in-toto, Ed25519, hash-chained receipts, honest unsigned naming | 163 tests green |
| `szl-payload` | Deterministic V14 builder with hard compile gates; `dist/SZL_MASTER_PAYLOAD_V14.md` (1,030 lines) builds byte-identical twice | 90 tests; `make all verify idempotent` pass |
| `szl-estate` | Two-source enumeration (must agree or PARTIAL), per-repo audit files, doctor, verify-claims | 71 tests; real audit in `artifacts/` |
| `szl-claims-api` | Live `GET /api/cps/claims` — every public claim with claimed/actual/drift/receipt | 41 tests; serves real drifts found today |
| `kids-sim` | KIDS v0.1 golden simulator: GEMM/RMSNorm/DMA/attention, LGATE, RC1 hard partition, SHA3-256 domain-separated receipts, KV Merkle commitment | 90 tests; 8/8 conformance vectors |
| `szl-beacon` | Beacon Reality Protocol reference: 11-state machine, Reality Debt, witness diversity, RC1 sim (RC1-01..04), offline-first sync, 50-node reference fleet | 128 tests; demo chain verifies |
| `szl-evidence-litellm` | LiteLLM evidence plugin: tamper-evident hash-chained receipt per request, fail-open/fail-closed, per-attempt capture, OTel mapping | tests green incl. LiteLLM integration |
| `szl-adversarial` | Public attack harness: 19 attacks against our own receipt chain | **19/19 blocked**, 1 documented limitation (unanchored tail truncation) |
| `szl-iso42001` | Free offline ISO 42001 + EU AI Act Art. 50 readiness checker that receipts its own findings | 62 tests |
| `alignment/` | Org-alignment engine: per-repo compliance scoring, template pack, idempotent PR preparation | 67 tests; org mean score 49.5% measured |
| `docs/standards/` | `draft-lutar-governed-action-receipt-00` — IETF individual draft of the receipt format | reproducible worked example inside |
| `site/` | The proof explorer — every figure computed from files in this repo | passes the estate's own forbidden-domain gate |
| `khipu-x1-workspace/` (repo: `khipu-x1`) | The uploaded master build payload, executed: 101-repo audit with source locks, chip-readiness matrix, KIDS v0.1 spec, RC1 emulator, `.khipu` builder/verifier | run summary: PASS, 0 remote mutations |

## 3. The competitive position, verified by independent research today

- **Governance platforms** (Credo AI, OneTrust, Trustible, Saidot, Holistic AI, IBM, ServiceNow, ModelOp, ValidMind, Asenion): none ships cryptographic per-decision receipts.
- **Gateways** (LiteLLM, Kong, Envoy AI GW, Portkey, OpenRouter, Helicone, Langfuse, Braintrust, OpenLLMetry, Phoenix): none ships tamper-evident request logs.
- **Silicon** (Tenstorrent, Groq, Cerebras, Etched, d-Matrix, Positron, FuriosaAI, NVIDIA CC, TDX, SEV-SNP, Caliptra, OpenTitan): attestation is boot/session-scope everywhere; no per-inference receipts, no datapath policy gate.
- **C-UAS/maritime** (Anduril, Dedrone, Fortem, Epirus, Shield AI, AeroVironment, Saildrone, Windward, HawkEye 360, Darkhive): nobody publishes tamper-evident engagement logging; Dedrone's forensic exports are the closest and are not tamper-evident.

Full evidence with citations: `docs/COMPETITIVE_TEARDOWN.md`.

## 4. Human-only actions — dated, in order

~~Daybreak Blue key~~ and ~~HF token rotation~~ — owner-handled, removed from this list 2026-08-31 16:00 ET.

1. **Regenerate the Cloudflare API token** (My Profile → API Tokens → "Edit zone DNS" template, `Zone:DNS:Edit` + `Zone:Zone:Read`, scoped to your zones only), then `curl https://api.cloudflare.com/client/v4/user/tokens/verify` must return `"status":"active"`. This unblocks every DNS write.
2. **`whois szl.dev`** — confirm registrar + renewal state; the domain has no delegation. Then point NS at Cloudflare and re-run `python -m szl_estate doctor`.
3. **On the origin host: `systemctl status cloudflared` + `journalctl -u cloudflared --since "24 hours ago"`** — tunnel 1033 is an origin-host problem, not DNS.

## 4b. Completed this session (was pending, now done)

- **HF estate aligned**: `SZLHOLDINGS/model-bom` refresh commits `8f45f2b` + `e92e8b5` — 44/44 models, dataset register 28→30 rows covering all 30 public datasets; both CLAIM_DRIFTs closed and now serving **PASS** from the live claims API.
- **Org alignment**: 22 PRs opened, 21 merged (a11oy excluded by owner decision — negative-control references stay intentional; the gate needs a semantic allowlist there). Forbidden-domain violations in `szl-command-lab` fixed on main (PR #16).
- **Domains verified live**: `a-11-oy.com` 200 (command center), `a11oy.net` 200 (proof registry), www→apex redirects, HTTP→HTTPS 301s, HSTS present. `szl-holdings.github.io` now 301→`holdings.a-11-oy.com` 200 after the alignment merge.
- **Live claims API**: `GET /api/cps/claims` serving PASS/UNKNOWN verdicts with per-claim receipts; wired into the proof explorer preview.

## 5. Standing operating loop (this is the cadence, not a roadmap)

- **Daily:** `make doctor audit verify` in this repo. Any FAIL/DRIFT is the day's first work item.
- **Weekly:** `python -m szl_adversarial run` — publish the report, pass or fail. `python -m szl_estate verify-claims` — the org README may never go stale again; the claims API serves the result.
- **Per release:** forbidden-domain gate (`alignment/templates/workflows/forbidden-domain.yml`) runs on every PR org-wide.
- **Per artifact:** no artifact without a receipt; unsigned artifacts are honestly named `*.unsigned.json`.

## 6. Dated external obligations

| When | What | Where |
|---|---|---|
| **2026-09-01** | Daybreak Blue FIDO key registration closes (non-recoverable) | account security settings |
| **2026-09-23** | DoD FY26 SBIR Release 5 closes — closest topic: OSD "Collaborative Distributed Swarm Radar" (OSW26BZ05-DV019) | DSIP portal |
| **Through 2028** | JIATF-401 Commercial Solutions Opening (fixed-price, forensics mandate in the establishing memo — the natural home for evidence receipts) | DIU/JIATF-401 CSO |
| **2026-10-20/21** | CyLab Partners Conference, CMU, Rangos Ballroom (invite/partner-only) — bring the working adversarial-evidence demo | Pittsburgh |
| Now | Submit `docs/standards/draft-lutar-governed-action-receipt-00` via datatracker.ietf.org individual submission (see SUBMISSION_NOTES.md) | IETF |
| Now | LiteLLM evidence plugin → upstream PR or standalone package announcement; the gap (no tamper-evident logs) is verified | GitHub |
| Now | Minewing RFQ: all six Section-28 GitHub links verified live today (200). Package can ship | see `docs/OPERATOR_PACKET.md` |

## 7. Honest limits — what is NOT true today

- No FPGA, ASIC, or silicon exists. KIDS v0.1 is a frozen spec with a golden simulator; cycle numbers are ESTIMATES.
- Zero Beacon units are fielded. The 50-node fleet is a validated reference configuration.
- Receipt-chain tail truncation is undetectable without external anchors (documented in the attack report and the IETF draft).
- The receipt format has never been attacked by anyone outside this estate. The harness is public; the challenge is open.
- The Cloudflare connector key is still malformed as of this writing; DNS writes wait on §4.3.
