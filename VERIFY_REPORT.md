# Proof surface — verification report (2026-08-31)

## Deliverables (`site/`)

| File | Purpose |
|---|---|
| `index.html` | Single-page proof surface: hero, proof explorer (7 tabs), estate audit, KIDS/KHIPU-X1, standards, doctrine, footer |
| `assets/site.css` | Hand-rolled KANCHAY-derived design system (zero CDN, zero webfonts) |
| `assets/app.js` | Vanilla-JS engine: fetches `data/*`, computes sha256 in-browser, renders everything dynamically |
| `assets/mark.svg` | Brand mark + favicon (holographic diamond, check stroke) |
| `assets/site.css`/`app.js` |
| `README.md` | Serve + exact regeneration commands per artifact |
| `robots.txt` | Public crawl surface |
| `scripts/check_links.py` | Link/fetch-path/anchor checker (34 internal refs) |
| `data/*` | Committed artifacts (see README table); `data/adversarial/*` + `data/adversarial_run.json` were generated this run via `python -m szl_adversarial run --out site/data/adversarial --json` (exit 0) |

## Verification results

- **Local serve**: `python3 -m http.server 8137` in `site/` → `index.html` 200; all anchors `#proof-explorer`, `#estate-audit`, `#kids`, `#standards`, `#doctrine` resolve.
- **Link check**: `scripts/check_links.py` → 34 internal references checked (every `fetch()` path in app.js, every href/src in index.html, all in-page anchors); **ALL RESOLVE, zero 404s**. The three `../docs/standards/*` links are repo-browsing relatives (outside the served root) — verified to exist on disk.
- **JSON parse check**: all 7 `data/**/*.json` files parse; both `.jsonl` chains parse line-by-line. PASS.
- **Forbidden gate**: `grep -rnP '(?<!-)a11oy\.com' site/` → **ZERO hits** (sites doctrine pattern is displayed only escaped, `\`, which the estate gate accepts).
- **Browser QA (Chromium/Playwright)**: hero counters computed live (100 · 19/19 · 8/8 · 9 claims 0/3/6); attack table 20 rows with verbatim verdict and gold limitation panel; beacon stepper 12 steps, in-browser recompute → "VERIFIED — all 12 digests recomputed, all 11 prev-links intact · tx-1e4a3124cac6" (in-browser sha256 matches committed event_ids); matrix search/filter/sort/lazy-chunks all functional; claims wall shows DRIFT (red) / UNKNOWN (amber) first-class with findings box; `szl-v14` delta computed live by set difference; page self-digest line in footer matches served bytes; zero console/page errors on localhost and file://.
- **file:// behavior**: static page renders; fetches fail-closed into styled panels naming `python3 -m http.server` (doctrine: serve the proof, don't assert it).
- **index.html sha256**: `eb380d2c5497abc1a309e909fae88e7c74d1a42343711792a4e6f74a7a5139f0` — and the footer recomputes the digest of the actually-served bytes at load.

## Data fields not rendered (and why)

- `events.jsonl`: byte-identical duplicate of `beacon_chain.jsonl` — not linked/fetched (would double-fetch the same bytes); documented in README.
- `adversarial/results.json`: identical content to `adversarial_run.json` (the copy the task names); kept on disk as the harness's original filename, not separately rendered.
- Per-attack `evidence` objects in `adversarial_run.json` (internal key ids, byte-flip offsets): the table renders name/category/result/detail; raw evidence stays in the JSON for auditors, linked from the artifact card.
- Beacon event `evidence_refs` arrays are rendered only when non-empty (only seq 1 carries one) — avoids noise on 11 empty cells.
- `enumeration.json` `missing_in_a`/`missing_in_b` are both empty arrays — not shown as separate UI; the PARTIAL story is carried by the per-source panel error states.
