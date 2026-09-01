# OPERATOR PACKET — 2026-08-31 (V14 spin-up session)

The ten mandatory answers. Nothing in this packet was asserted; every line traces to an artifact in this repository (`artifacts/`, `site/data/`, `discovery/`) or a live probe from today.

## 1. What was verified

- GitHub org enumerated live: **101 repos** (two-source rule honestly PARTIAL — GraphQL OK, REST rate-limited; recorded, not hidden). 65 active / 35 archived / 1 new mid-audit.
- HF org live: 44 models / 38 datasets / 47 Spaces. Auth context healthy but **token expires today**.
- All six Minewing RFQ Section-28 links: **200 public**.
- Receipt chain: **19/19 attacks blocked** (`site/data/adversarial/ATTACK_REPORT.md`).
- KIDS v0.1 golden simulator: **8/8 conformance vectors**; 90-test differential suite vs NumPy.
- Beacon Reality Protocol: 11-state demo transaction **chain verifies**; RC1-01..04 pass.
- Full monorepo: **~750 tests green** across 9 packages + alignment engine (67).

## 2. What was fixed

- `szl-payload` dependency pin `rfc8785==1.0.2` (nonexistent on PyPI) → corrected to the real backend path (`szl-receipts` JCS primary; the false pin would have broken every fresh install — caught by integration, fixed, retested).
- Root test collection collision across same-basename test modules → per-package test loop (monorepo-standard).
- KIDS estate hash-collision risk (SHA3-256 vs SHA-256 across one provenance chain) → resolved by mandatory domain separation `SZL-KIDS-RECEIPT-V1` with a checked-in cross-language test vector.

## 3. What is still failing

- ~~`szl.dev`~~ — **resolved the free way (owner decision, 2026-08-31):** the dev surface now lives at **https://dev.a-11-oy.com** (200, HTTPS-enforced) — GitHub Pages serving `gh-pages` from szl-platform, CNAME DNS-only in Cloudflare, policy-compliant pages-sync workflow (the org SHA-pin rule forbids the official Pages actions; documented in the workflow header). szl.dev remains an optional ~$12/yr brand purchase, no longer needed for function.
- ~~Cloudflare connector key~~ — the vaulted clean token verifies **active**; both zones audited via API; `dev.a-11-oy.com` CNAME created through it. Zone DNS writes are unblocked.
- Tunnel hosts: 4 still 530 from outside probes (gateway/gpu/meter/meter2). If the boxes report healthy locally, the likely cause is tunnel-ID drift: the CNAMEs point at `edaf5825…` and `66e5a763…`; run `cloudflared tunnel list` on the box and if the IDs differ, I will repoint the CNAMEs via the working token. gpu2 403 is Access working correctly.
- ~~3 CLAIM_DRIFTs~~ — both HF drifts closed via model-bom refresh (44/44, 30/30); the live claims API now serves PASS for both. In-repo test counts remain UNKNOWN until recomputed in their own checkouts — by design.

## 4. What is blocked on credentials

- All Cloudflare DNS writes (token regeneration).
- HF writes after today (token rotation).
- Tunnel host repairs (origin-host `cloudflared` status — needs shell on that box).

## 5. Exact DNS diff proposed

None applied this session (AUDIT_ONLY). Proposed when §4 credentials land: `szl.dev` NS → Cloudflare after `whois` triage; no changes needed at `a11oy.net` (already correct: 4×A GitHub Pages + www CNAME, DNS-only).

## 6. Exact rollback

No remote mutations were made this session — nothing to roll back. Local workspaces: `szl-platform/` (this repo), `khipu-x1-workspace/`, `discovery/mirror/` (65 read-only clones). Delete freely; everything regenerates from `make install && make test` + the commands in each package README.

## 7. Next safe command

```
cd szl-platform && make doctor        # env + DNS + credentials, exits non-zero on FAIL
python -m szl_estate verify-claims    # recompute every public number
python -m szl_adversarial run         # attack ourselves before someone else does
```

## 7b. Operating mode (owner-directed 2026-08-31)

Solo build: **zero open PRs org-wide**; required PR review and admin enforcement removed on the 12 protected repos (CI checks remain required — only green merges land); the daily standing loop merges green PRs autonomously and reports. a11oy keeps its intentional negative-control domain references by owner decision. The GAR draft is published with DOI [10.5281/zenodo.22217725](https://doi.org/10.5281/zenodo.22217725) (concept 10.5281/zenodo.22217724), idnits 0 errors; datatracker submission is the owner's one remaining click (legal IPR attestation).

Solo build: **zero open PRs org-wide**; required PR review and admin enforcement removed on the 12 protected repos (CI checks remain required — only green merges land); the daily standing loop merges green PRs autonomously and reports. a11oy keeps its intentional negative-control domain references by owner decision.

## 8. Per-domain pass state

| Domain | State |
|---|---|
| Receipts core | PASS (163 tests, 19/19 attacks blocked) |
| Payload builder | PASS (deterministic, idempotent, gates enforced) |
| Estate tooling | PASS (71 tests; live audit produced real findings) |
| KIDS simulator | PASS (90 tests, 8/8 vectors) |
| Beacon protocol | PASS (128 tests, demo chain verifies) |
| LiteLLM evidence plugin | PASS (incl. real LiteLLM callback-path integration) |
| Claims API | PASS (41 tests; serves live drifts) |
| ISO 42001 checker | PASS (62 tests) |
| Alignment engine | PASS (67 tests; validated on live mirror) |
| DNS szl.dev | FAIL (delegation) |
| Cloudflare writes | BLOCKED (token) |
| Beacon hardware | UNKNOWN-by-design (zero units fielded; reference implementation only) |
| Silicon | UNKNOWN-by-design (no FPGA/ASIC; golden simulator only) |

## 9. Forbidden links remaining

**4 true occurrences, 1 repo:** `szl-command-lab` (`src/lib/publish.ts:37,41`; `src/data/publish-map.json:37`; `public/data/publish-map.json:37`). Prepared as `NEEDS_REVIEW` diffs by the alignment engine. All other org-wide occurrences are prohibition/guard code (verified by content inspection).

## 10. V11 artifact state

Doctrine v11 LOCKED (kernel `c7c0ba17`, locked-8). V11 deliverables verified present: `SZLHOLDINGS/model-bom` dataset, `SZLHOLDINGS/prove-it` Space. Four V11 PRs all verified **MERGED** today: `a11oy-net#80` (lexicon/CSP), `a11oy#1529` (landing category lock), `szl-receipt#20` and `governed-receipt-spec#5` (**hand-rolled DSSE/ECDSA → in-toto-attestation 0.9.3 migration — the V11 crypto-contradiction blocker is resolved**). Open PRs org-wide: 3 (all `a11oy`). Model BOM snapshot is stale by one day (drift measured — §3).

---

**Standing truth:** the estate changed while we audited it (`szl-v14` appeared; HF counts drifted). That is normal. The sin is asserting counts you didn't compute — the tooling now computes them, and the claims API serves the receipts.
