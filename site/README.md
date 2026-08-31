# SZL Holdings — public proof surface (`site/`)

The investor / auditor / engineer frontend for the estate's committed evidence.
Every figure on the page is computed in the browser from the files under
`data/` — fetched as bytes, hashed with the Web Crypto API, and counted.
Nothing is hardcoded; if a fetch fails, the page shows the error and the exact
command to serve the proof instead of asserting it.

## Serve

Any static host works. `file://` works for static content, but browsers refuse
`fetch()` of local files there — the page detects this and tells you to serve:

```bash
cd site
python3 -m http.server 8000
# open http://localhost:8000/
```

No build step. No CDN. No fonts to download. Three files make the page:
`index.html`, `assets/site.css`, `assets/app.js`.

## Regenerate the data

All commands run from the repo root, after `make install` (editable-installs
every package and adds pytest/ruff).

| Artifact | Command |
|---|---|
| `data/enumeration.json` | `python -m szl_estate.enumerate --org szl-holdings --out artifacts/audits` (offline replay: add `--offline`) |
| `data/repo_matrix.json` | `python -m szl_estate.audit --org szl-holdings --out artifacts/audits` — the audit writes `artifacts/audits/REPOSITORY_MATRIX.csv`; this JSON is that matrix, row for row |
| `data/ESTATE_SUMMARY.md` | same audit run: `artifacts/audits/ESTATE_SUMMARY.md` |
| `data/claims.json` | `python -m szl_estate.verify_claims --out artifacts/claims` |
| `data/adversarial_run.json` + `data/adversarial/` | `python -m szl_adversarial run --out <dir> --json` — writes `ATTACK_REPORT.md`, `attack-report.unsigned.json`, and `results.json` (copied here as `adversarial_run.json`). Exit 0 = the claim held; exit 2 = an attack won |
| `data/beacon_demo.txt` + `data/beacon_chain.jsonl` | `python -m szl_beacon demo` — writes the transaction's log to a temp dir it prints; the chain is its `events.jsonl`, copied here as `beacon_chain.jsonl` |
| `data/kids_conformance.json` | `python -m kids_sim.conformance run --vectors packages/kids-sim/vectors --json` |

`data/events.jsonl` is the identical byte copy of the same Beacon run
(kept under the package's canonical log name).

## Verifying what the site claims

- Artifact digests: the page prints `sha256` over the exact bytes it fetched;
  compare with `sha256sum data/<file>` locally.
- Beacon chain: the "verify chain" button recomputes every `event_id` and every
  `prev` link in-browser (Web Crypto sha256 over `json-sortkeys` reference-mode
  canonical bytes — honestly labeled on the page; production uses RFC 8785).
- Attack run: re-run the harness — exit code is the verdict. A signed run
  (`--sign-with KEY.pem`) turns `attack-report.unsigned.json` into a signed
  envelope; this public copy is unsigned and says so in the filename.
- Forbidden-domain gate: `rg -P '(?<!-)a11oy\.com' site/` must print nothing.
  This site is held to the same release gate as every repo in the estate.

## Doctrine reminder

Unsigned artifacts are named `.unsigned.json` — an empty signatures array is
not a signature. UNKNOWN is never PASS.
