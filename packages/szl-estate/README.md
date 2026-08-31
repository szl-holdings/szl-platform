# szl-estate

**The estate control plane for the SZL Holdings GitHub org + Hugging Face org.**
It answers four questions, out loud, with evidence:

1. **What do we own?** — `enumerate` asks GitHub twice (the `gh` CLI and the raw
   REST API) and refuses to say "COMPLETE" unless the two sources agree.
2. **What shape is it in?** — `audit` writes one evidence file per repo plus a
   `REPOSITORY_MATRIX.csv` and an `ESTATE_SUMMARY.md` whose top section is the
   literal header `BLOCKERS THAT OUTRANK ALL COSMETIC WORK`.
3. **Can this machine even run the estate?** — `doctor` checks Python, git,
   `gh` auth, `GH_TOKEN`, the Cloudflare token, DNS delegation, the cloudflared
   tunnel, and the `huggingface_hub` version gate. Exits 1 if anything is FAIL.
4. **Are our public numbers still true?** — `verify-claims` recomputes the org's
   published numeric claims and opens a `CLAIM_DRIFT` finding on any mismatch.

## The doctrine (encoded, not aspirational)

- **UNKNOWN is never PASS.** Any probe that errors — rate limit, 404, missing
  tool, offline mode — degrades to `UNKNOWN` with the error attached. Nothing in
  this package converts a failure into a zero, a green checkmark, or silence.
- **Never assert a number you didn't compute.** When enumeration is PARTIAL the
  tool prints both observed counts and the diff, and `repo_count` is `null`.
  `verify-claims` prints an `Observed` column containing only numbers the
  current run computed itself.
- **The forbidden domain is a CRITICAL finding.** The pattern
  `(?<![\w-])a11oy\.com` in any scanned file is a `FORBIDDEN_LINK` finding at
  severity CRITICAL. `a-11-oy.com` (the real product origin) and `xa11oy.com`
  (a different domain) must never match. See the comment on
  `FORBIDDEN_LINK_RE` in `src/szl_estate/__init__.py` for why the lookbehind is
  wider than the doctrine's base `(?<!-)`.

## Install and run

```bash
pip install -e packages/szl-estate

python -m szl_estate enumerate --org szl-holdings --out artifacts/estate
python -m szl_estate audit --org szl-holdings --out artifacts/estate
python -m szl_estate doctor --json
python -m szl_estate verify-claims --out artifacts/claims

# Fully offline replay against a captured `gh repo list` fixture:
python -m szl_estate enumerate --org szl-holdings --out /tmp/estate --offline
python -m szl_estate audit --org szl-holdings --out /tmp/estate --offline
```

Every subcommand supports `--help` and `--json`. `doctor` exits 1 when any
check is FAIL; other subcommands exit 0 and encode findings in their outputs
(audit and verify-claims are measurement tools — a CRITICAL finding is a
*result*, not a tool malfunction).

## Layout

```
src/szl_estate/
  __init__.py        doctrine constants: FORBIDDEN_LINK_RE, severities, GitHub Pages IPs
  enumerate.py       two-source org enumeration (gh CLI + REST) that must agree
  audit.py           per-repo audit renderer + CSV/Markdown rollups
  doctor.py          environment / credential / DNS / tunnel checks
  verify_claims.py   recomputes the org's public numeric claims; CLAIM_DRIFT on mismatch
  receipt_adapter.py optional szl-receipts integration with honest unsigned fallback
  cli.py             argparse front door (python -m szl_estate ...)
  templates/REPO_AUDIT.j2
  claims.yaml        seeded public numeric claims with their check types
tests/               offline-only suite (fixtures + monkeypatching, no network)
```

## For investors and auditors

Everything this package prints is either computed in the run you are looking at
or explicitly labeled `UNKNOWN` / `static_expected (not recomputed)`.
`tests/fixtures/gh_repo_list.json` is a real capture of
`gh repo list szl-holdings -L 400 --json ...` from 2026-08-31 (100 repos), so
the entire test suite — and `--offline` mode — runs with zero network access.
