# Site build result — proof explorer (2026-08-31)

Built at `/home/user/workspace/szl-platform/site/` — committed as `7973f26`.

## File list (site/)
- `index.html` — single-page surface, anchored sections: hero / #proof-explorer (7 tabs) / #estate-audit / #kids / #standards / #doctrine / footer
- `assets/site.css` — hand-rolled KANCHAY-derived design system, zero CDN/fonts
- `assets/app.js` — vanilla JS: fetches all data files, computes sha256 in-browser (Web Crypto), renders everything dynamically
- `assets/mark.svg` — brand mark + favicon
- `README.md` — serve (`python3 -m http.server`) + exact regeneration commands per artifact
- `robots.txt`
- `scripts/check_links.py` — link/anchor/fetch-path checker
- `VERIFY_REPORT.md` — full verification log
- `data/adversarial_run.json` + `data/adversarial/{ATTACK_REPORT.md, attack-report.unsigned.json, results.json}` — GENERATED this run via `python -m szl_adversarial run --out site/data/adversarial --json` (exit 0, verdict "receipt chain resisted 19/19 non-limitation attacks")

## sha256(index.html)
`eb380d2c5497abc1a309e909fae88e7c74d1a42343711792a4e6f74a7a5139f0`
(footer recomputes the digest of the served bytes at load and matches)

## Forbidden gate
`grep -rP '(?<!-)a11oy\.com' site/` → **ZERO hits, gate PASSES** (exit 1). The doctrine code blocks display the pattern only in escaped form, which the gate accepts; canonical links use only a-11-oy.com and a11oy.net.

## Verification performed
- Local serve on :8137 → index.html + all 5 section anchors 200
- Link check: 34 internal refs (fetch paths, href/src, anchors) → ALL RESOLVE, zero 404s
- All 7 data/**/*.json parse; both .jsonl chains parse line-wise
- Playwright/Chromium QA: counters live-computed (100 · 19/19 · 8/8 · 9 claims 0 PASS/3 DRIFT/6 UNKNOWN); beacon in-browser chain re-verify → VERIFIED (12 digests, 11 prev-links, tx-1e4a3124cac6), matching committed event_ids; matrix search/sort/lazy-render OK; claims wall shows DRIFT red / UNKNOWN amber; szl-v14 delta computed live by set difference; mobile menu OK; zero console errors; file:// fails closed with styled serve-the-proof panels

## Data fields not rendered (why)
- `events.jsonl`: byte-identical dup of `beacon_chain.jsonl` — not separately linked (would double-fetch same bytes); documented in README
- `adversarial/results.json`: identical content to `adversarial_run.json` (task-named copy); kept on disk as harness's original name
- per-attack `evidence` objects (internal key ids, flip offsets): table renders name/category/result/detail; raw evidence stays in JSON for auditors
- beacon `evidence_refs` rendered only when non-empty (only seq 1 has one)
- enumeration `missing_in_a`/`missing_in_b` (both empty arrays): not separate UI; PARTIAL story carried by per-source error panels

## Note
`python3 docs/standards/build_draft.py` was run once (it regenerates `docs/standards/draft-lutar-governed-action-receipt-00.{txt,md}` + `validate_draft.py`, left untracked — the site's standards links resolve to them); `build_draft.py` itself was restored to its committed state.
