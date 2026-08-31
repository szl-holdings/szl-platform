# Phase -1 — DNS + Credential Repair (hoisted ahead of everything)

Nothing deploys, attests, trains, or publishes while the estate's names and
credentials are broken. DNS-first is enforced twice: by this document order
and by the builder gate `require_dns_first` (Phase B), which refuses to
compile any payload that places a `*train*` section before this one.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

All mutation flags default to false. Every apply is gated behind a printed
authorization packet — current and proposed manifest digest, add/modify/remove
list, rollback file, prechecks — and then STOP.

## 1. Cloudflare credential repair (hard gate)

The connector currently fails with API error **6003** — "Invalid request
headers / Invalid format for X-Auth-Key header" — before it can list accounts
or zones. That is a malformed connector credential; it is **not** evidence
about any zone. Repair:

1. My Profile → API Tokens (user), or Manage Account → Account API Tokens.
2. Use the "Edit zone DNS" template with scope **`Zone:DNS:Edit` +
   `Zone:Zone:Read`**, zone-scoped only. Granting Zone DNS Read on one zone
   errors on every other; never fall back to a Global API Key.
3. Verify with `GET /client/v4/user/tokens/verify` — the `/user/tokens/verify`
   endpoint must return `"status":"active"`. This is a hard gate: doctor
   (Phase 0) exits non-zero until it does.

A broken key blocks **applying**, never **planning**: the offline
zone-snapshot import path (`dns_plan.schema.json` /
`deployment_plan.schema.json` with `records_to_add/update/remove`,
`verification_records`, `rollback_records`, `prechecks_passed`) keeps DNS
planning read-only and least-change (MX/TXT/NS/SOA preserved). Take a zone
snapshot before any write and store it as `artifacts/dns/<zone>.rollback.json`
— that file is the rollback.

## 2. a11oy.net — public proof/registry origin

- Apex: four A records — `185.199.108.153`, `185.199.109.153`,
  `185.199.110.153`, `185.199.111.153` (GitHub Pages) — or ALIAS/ANAME to
  `szl-holdings.github.io` if the provider supports it.
- `www`: CNAME to `szl-holdings.github.io`.
- The Cloudflare proxy must stay **DNS-only (grey cloud)** while GitHub
  provisions the certificate. If the orange cloud is ever used, set SSL/TLS to
  Full / Full-strict *before* enabling the proxy — the wrong order produces
  redirect loops. A proxied flag on any `185.199.*` Pages apex record is the
  orange-cloud-on-Pages-apex bug and fails the compile gate
  (`proxied_pages_apex`, Phase B).
- Pages cert re-issue trick: remove the custom domain → save → wait ~60 s →
  re-add the identical domain → save; optionally toggle Enforce HTTPS after
  15–20 minutes.

## 3. a-11oy.com → a-11-oy.com — command center

Plan: CNAME to **`hf.space`** via Space → Settings → Custom Domain, then wait
for "ready". Prechecks, in order:

- HF custom domains are PRO/Team/Enterprise only — a free tier stays
  "pending" forever regardless of DNS.
- An apex cannot hold a CNAME. Resolve via Cloudflare CNAME flattening (only
  if confirmed for the zone) or make `www` canonical with a 301 from the apex.
- A CNAME cannot coexist with any A/AAAA/TXT/MX at the same label: delete the
  sibling records, then delete and re-add the HF custom domain to retrigger
  validation. This is the #1 cause of a stuck "pending".
- The domain is managed at Namecheap per the public DNS page, which documents
  a pending record `immune.a-11-oy.com → 167.233.50.75` — documentation, not
  authoritative verification.

## 4. szl.dev — NXDOMAIN triage

`szl.dev` returns NXDOMAIN. That is a registrar/delegation state, not a
records problem. Triage order: `whois` → `dig +trace NS` → zone SOA. If whois
shows expired/redemptionPeriod it is a registrar payment issue, not
engineering; if registrar access is unavailable, report `BLOCKED: registrar
ownership cannot be verified` — do not claim expired and do not claim
available. `.dev` is on the **HSTS** preload list compiled into Chrome and
Firefox: HTTP literally cannot connect, there is no opt-out. Deploy order is
DNS → certificate → verify with curl / `openssl s_client` → *then* link or
announce. If HSTS preload is ever self-set: `max-age ≥ 31536000` with
`includeSubDomains`, ramped 5 minutes → 1 week → 1 month.

## 5. Forbidden domain

The unhyphenated `.com` variant (`a11oy[.]com`, written defanged because the
lint gate is watching) is a third-party WordPress furniture store — a brand
collision. Never link it, redirect to it, crawl it, or CNAME it. Any reference
anywhere is a release-blocking `CRITICAL/FORBIDDEN_LINK` enforced by regex
gate. Canonical surfaces are `a-11-oy.com` (command center) and `a11oy.net`
(proof origin) — nothing else.

## 6. Tunnel 1033 fleet

Six proxied CNAMEs point at three `cfargotunnel.com` tunnels; **five hosts
return 530 / error 1033** — "tunnel configured, no active connector
registered". Error 1033 is fixed on the origin host, not in DNS. Hosts
carried: `gateway`, `gpu`, `meter`, `gdw`, `meter2`, `gpu2`. Repair sequence:

1. `cloudflared tunnel list`
2. `cloudflared tunnel info <id>`
3. `systemctl status cloudflared`
4. `journalctl -u cloudflared --since "24 hours ago"`
5. conditional `cloudflared service install`
6. restart, then re-probe every host.

Pre-reinstall checklist: back up `config.yml`; record the service unit, tunnel
ID, and hostname mapping; verify the token belongs to the correct tunnel;
verify the origin listens on the intended loopback port; verify no competing
connector. Finding codes: `TUNNEL_1033` / `TUNNEL_DISCONNECTED`.

## 7. gpu2 403 is Access working

A Cloudflare Access 403 on `gpu2` means Access is working correctly. **Never
remove Access solely to make a probe return 200.** Verify the intended
deny-by-default policy and test with an authorized identity.

## 8. Daybreak Blue deadline

FIDO hardware-key registration for Daybreak Blue (Advanced Account Security)
has a **non-recoverable deadline of September 1, 2026**; missing it loses
frontier cyber-model access and falls back to standard models. It ranks above
every other item in every round.

## 9. Apply discipline (Pass 2 only)

DNS apply runs one record set at a time with a pre-change zone export and
propagation polling across multiple resolvers (authoritative + 1.1.1.1 +
8.8.8.8 + system). Each step prints its authorization packet and stops. Every
change ships with its rollback file already on disk before the write.

Per-phase print block, always: STATUS / EVIDENCE / ROLLBACK / NEXT SAFE
ACTION / RECEIPT. UNKNOWN is never PASS.
