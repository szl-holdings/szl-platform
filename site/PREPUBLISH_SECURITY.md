# Pre-Publish Security Review — SZL Holdings Proof Surface

Scope: `/home/user/workspace/szl-platform/site` (static bundle: `index.html`, `assets/`, `data/`).
Reviewed prior to publish on a public `*.pplx.app` URL. Audience: public / investors / auditors.

---

## Check 1 — Dependency audit
**PASS** — No `package.json`, `requirements.txt`, `Pipfile`, `yarn.lock`, or `package-lock.json` exists anywhere under `site/`. The only non-web-asset file is `scripts/check_links.py`, a dev-only internal link checker using only the Python standard library (`re`, `urllib.request`, `html.parser`, `pathlib`) — zero third-party dependencies, not shipped as an active part of the published page.

## Check 2 — Hardcoded secrets
**PASS** — Full-repo grep for API-key patterns (`sk-`, `AKIA`, `ghp_`, `glpat-`, `xox[bprs]-`, PEM private-key headers, inline `password=`/`password:` literals, `hf_` tokens) returned zero matches. No `.env`/`.env.*` files exist anywhere under `site/`.

## Check 3 — Dangerous JS patterns
**PASS** — Only one hit for `eval(`/`new Function(`/`innerHTML =`/`document.write(`/`.html(` in `assets/app.js`: line 17, the `h()` DOM-builder helper's `html:` attribute path (`node.innerHTML = v`). Verified by tracing every call site:
- Exactly one call in the entire file passes the `html:` key (line 443), and it is a **literal, hardcoded, site-authored string** with no variable interpolation — a static "honesty note" about canonicalization.
- All other content that originates from fetched files (`data/*.json`, `data/*.jsonl`, `data/ESTATE_SUMMARY.md`, adversarial report text, repo/source names) is routed exclusively through the `text:` attribute, which maps to `node.textContent` (auto-escaped, non-executable) — confirmed across every `rec()`/`loadArtifact()` consumer, including the hand-rolled markdown renderer (`renderSummaryMd`), the adversarial results table, and the source-enumeration name list.
- No other injection sinks (`outerHTML`, `insertAdjacentHTML`, `document.write`) exist in the file.
- Conclusion: the `innerHTML` usage is safe and correctly scoped to trusted, non-remote strings only — no fetched JSON/CSV/MD content can reach an HTML-parsing sink.

## Check 4 — External requests
**PASS** — All `fetch()` calls in `assets/app.js` target same-origin relative paths: artifact loader (`path` argument, always a `data/...` string), `"index.html"` (self page-digest), and the claims-API placeholder `"__PORT_8011__/api/cps/claims"`, which is explicitly guarded by `if (url.includes("__PORT_")) return false;` — genuinely inert unless a deploy pipeline rewrites the placeholder to a real origin; confirmed no such rewrite is present in this bundle.
`index.html` contains **no** `<script src>` or `<link>` pointing off-origin — only `assets/site.css`, `assets/mark.svg`, and `assets/app.js`, all self-hosted. The only `https://` references anywhere are plain navigational `<a href>` anchors (not runtime resource loads) to the company's own domains (`a-11-oy.com`, `a11oy.net`), its GitHub org, its Hugging Face org, and two standards-body reference links (OWASP ASI, CSA MAESTRO). No CDN, font-loader, analytics, or tracker script/tag/pattern found (`gtag`, `googletagmanager`, `gstatic`, `jsdelivr`, `unpkg`, `sentry`, `segment`, `fonts.googleapis` all absent) — consistent with the self-contained, zero-third-party design stated in `README.md`.

## Check 5 — Data exposure
**PASS** — Reviewed all files in `data/` (`claims.json`, `enumeration.json`, `repo_matrix.json`, `kids_conformance.json`, `adversarial_run.json`, `adversarial/results.json`, `adversarial/attack-report.unsigned.json`, `beacon_chain.jsonl`, `events.jsonl`, `ESTATE_SUMMARY.md`).
- **Emails:** zero email-pattern matches anywhere in `site/` (the expected `eng@szlholdings.com` does not even appear — no email leakage of any kind).
- **IPs/hostnames:** zero IPv4 matches; the only non-`a-11-oy.com`/`a11oy.net` hostname found is `szl-holdings.github.io` (a public GitHub Pages subdomain — expected/benign, not an internal host).
- **Private repo names in `repo_matrix.json`:** all 5 flagged repos (`gdw-frontier`, `pitch-collateral`, `szl-defensive-control-plane`, `szl-estate-os`, `szl-org-health`) are present with `visibility: "PRIVATE"`. Inspected every field on their records — the schema across all 103 entries is limited to `state, name, visibility, archived, default_branch, pushed_at, primary_language, license_spdx, description_present, open_prs, ci_latest, forbidden_link_scan, findings_critical, findings_high, findings_total`. `description_present` is a boolean ("yes"/"no") flag only — **no actual description text, file paths, or contents are present for any private repo.** This is name-only disclosure as expected, and acceptable.
- **`beacon_chain.jsonl` / `events.jsonl`:** contain clearly-labeled synthetic demo actors (`resident-demo-42`, `a11oy-revA-demo`) and content-hash `event_id`s — not real user PII or credentials.
- Full-repo key search for `token`, `secret`, `session`, `cookie`, `api_key`, `password`, `private_key`, `access_key` inside `data/` returned zero hits.

## Check 6 — robots.txt / sitemap / credential-artifact sanity
**PASS** — `robots.txt` is well-formed (`User-agent: *` / `Allow: /`, with a comment correctly identifying canonical origins) — appropriate for a public proof/investor site meant to be indexed. No `sitemap.xml` exists; minor/informational only, not a security issue for a single-page site. No credential, session, certificate, or private-key material found in `data/` (`BEGIN CERTIFICATE`/`BEGIN PRIVATE`/`BEGIN OPENSSH` grep clean). The one artifact that looks signature-like, `data/adversarial/attack-report.unsigned.json`, was decoded: its base64 `payload` is plain audit metadata (outcome, policy digest, sha256 evidence hashes) with `signatures: []` — exactly as the site's own copy honestly discloses ("no operator key signed this run"). Confirmed `.git` lives only at the `szl-platform` monorepo root, not inside `site/`, so no git history ships in the published bundle.

---

## Summary

| Check | Result | Evidence |
|---|---|---|
| 1. Dependency audit | PASS | No `package.json`/`requirements.txt` under `site/`; only dep-free `scripts/check_links.py` |
| 2. Hardcoded secrets | PASS | Secret-pattern grep: 0 hits; no `.env` files |
| 3. Dangerous patterns | PASS | Single `innerHTML` sink, literal string only; all fetched content routed through `textContent` |
| 4. External requests | PASS | Only same-origin fetches + inert `__PORT_8011__` placeholder; zero CDN/analytics/tracker |
| 5. Data exposure | PASS | No emails/IPs; private repo names disclosed with metadata only, no description text |
| 6. robots.txt / artifacts | PASS | Clean robots.txt; no sitemap (informational); no credential/session/key artifacts; no `.git` in bundle |

**VERDICT: PUBLISH-SAFE**

No BLOCK or WARN findings. The site is a self-contained static bundle with no dependencies, no secrets, a single tightly-scoped and verified `innerHTML` use, no third-party network calls, and data files that disclose only what the stated design intends (public repo/name-level audit metadata, no PII, no credentials).
