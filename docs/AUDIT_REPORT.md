# SZL Holdings — GitHub Org + HF Estate Audit

**Run date:** 2026-08-31 · **Method:** content-level, computed live this session · **Tooling:** `szl-estate` (two-source enumeration, per-repo audits), `szl-alignment` (compliance scoring over full clones), `szl-adversarial` (receipt-chain attack run), manual DNS/HTTP probes · **Artifacts:** `artifacts/` + `discovery/` in this repository.

> Doctrine applied to ourselves: every count below was computed in this run. Where a source failed, it is printed as PARTIAL/UNKNOWN with the error — never interpolated.

## 1. Inventory — computed, not asserted

| Measure | Value | Evidence |
|---|---|---|
| GitHub org repos | **103** | `gh repo list` (GraphQL), 2026-08-31; REST cross-check rate-limited → enumeration status honestly **PARTIAL** with both source outcomes recorded |
| Mid-audit drift | **`szl-v14` appeared during enumeration**, then `szl-platform` and `khipu-x1` were added by this session's pushes (100 → 103) | `discovery/gh_repo_list.json` vs live re-runs — the tooling caught each change |
| Active / archived | 65 active, 35 archived (+ `szl-v14` new) | inventory JSON |
| Primary language | Python 66, TypeScript 13, Lean 4, HTML 3, Cuda 2, Rust 1, Nix 1, None 4, others 7 | inventory JSON |
| Private repos | 5 (`gdw-frontier`, `pitch-collateral`, `szl-defensive-control-plane`, `szl-estate-os`, `szl-org-health`) | inventory JSON |
| HF org `SZLHOLDINGS` | 44 models, 38 datasets, 47 Spaces | HF hub search, 2026-08-31 |

## 2. Blockers that outrank all cosmetic work

1. ~~**CRITICAL — forbidden domain in a live publish path**~~ **RESOLVED 2026-08-31 20:04 UTC** ([szl-command-lab PR #16](https://github.com/szl-holdings/szl-command-lab/pull/16)): the 4 occurrences (`src/lib/publish.ts` L37/L41, two `publish-map.json` copies) now point at canonical `a-11-oy.com`. Every other org hit was verified prohibition/guard context — the estate's own machinery referencing the string to forbid it. Owner decision recorded: a11oy keeps intentional negative-control references; a semantic allowlist (not a raw substring ban) is the accepted gate design there.
2. **FAIL — `szl.dev` has no delegation.** `dig NS szl.dev` → empty (NXDOMAIN), confirmed by `szl-estate doctor` exit 1. Registrar action required.
3. ~~**HIGH — HF claim drift**~~ **RESOLVED 2026-08-31**: model-bom refreshed to 44/44 models and 30/30 datasets ([commits `8f45f2b`, `e92e8b5`](https://huggingface.co/datasets/SZLHOLDINGS/model-bom)); verify-claims now reports both **PASS** live. Remaining: `monorepo_packages: 126` and the in-repo test counts serve as UNKNOWN until recomputed inside their own checkouts — the claims API publishes exactly that.
4. ~~**HIGH — HF token expiry**~~ — owner-handled, removed 2026-08-31 16:00 ET.
5. **MEDIUM — 3 open PRs, all in `a11oy`** (oldest 2026-07-31). The "~12 stuck PRs" from the V11 era is resolved down to 3.

## 3. Alignment (64 repos scored over full clones — mean 49.5%)

| Gap | Count | Fix vehicle |
|---|---|---|
| Missing `SECURITY.md` | 36/64 | alignment template, PR per repo |
| Missing `CONTRIBUTING.md` | 53/64 | alignment template |
| Missing issue/PR templates | majority | alignment template |
| Forbidden-domain CI gate absent | all active repos | `forbidden-domain.yml` (prohibition-context-aware) |
| License files | present everywhere; GitHub recognizes none of the custom texts | standardize SPDX headers; `LicenseRef-SZL-Proprietary` for closed core |
| Doctrine README header | absent in most | `README_HEADER.md` insert (idempotent marker) |

Strongest repos by alignment: `platform` 80%, `lutar-lean` / `szl-brand` / `szl-trust` 75%. Full matrix: `artifacts/audits/REPOSITORY_MATRIX.csv` + alignment `matrix.csv`.

## 4. Live surface probes (2026-08-31)

`a11oy.net` 200 · `www.a11oy.net` 301 · `a-11-oy.com` 200 · `szlholdings-a11oy.hf.space` 200 · `gpu2.a-11-oy.com` 403 (Cloudflare Access working — correct, do not "fix") · `szl.dev` no delegation (FAIL).

## 5. Minewing RFQ link verification

All six Section-28 links return **200 public** today: `a11oy`, `szl-substrate`, `szl-kernels`, `szl-forge`, `szl-receipt-attn`, `governance-as-code`. The RFQ's provenance section no longer risks a 404.

## 6. Receipt-chain attack run (against ourselves)

`szl-adversarial` live run: **19/19 non-limitation attacks blocked** — forgery, bitflip, FAIL→PASS rewrite (stale and recomputed digests), key-reorder, whitespace, NFC/NFD, number-format, reorder, replay, fork, naming-swap, signature-strip, cross-envelope swap, PAE prefix confusion, UNKNOWN-promotion, garbage-outcome. One documented limitation: tail truncation without external anchors (WARN; blocked when `expected_head` anchor is provided). Full report: `site/data/adversarial/ATTACK_REPORT.md` with its own self-receipt.

## 7. What this audit deliberately did not do

- No repo content was modified; the mirror is read-only evidence at `discovery/mirror/` (65 shallow clones, 978 MB).
- REST-paginated cross-check is PARTIAL by rate limit; the honest status is recorded in `enumeration.json` rather than a fabricated "COMPLETE".
- Test-count claims inside `a11oy`, `platform`, `szl-ouroboros` were not recomputed (require per-repo checkouts + full runs) — they serve as UNKNOWN in the claims API until recomputed.
