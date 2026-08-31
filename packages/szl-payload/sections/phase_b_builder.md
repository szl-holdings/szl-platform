# Phase B — The Payload Builder (this contract)

Phase B builds the document you are reading. It exists as a contract: the
builder is a deterministic function of `sections/` plus `manifest.toml`, and
anything it cannot prove, it refuses to emit.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## Source and output

`sections/` is the source of truth; `dist/ is derived` — never hand-edit
anything under `dist/`, because the next build overwrites it and the hand
edit becomes invisible drift. The single output document is
`dist/SZL_MASTER_PAYLOAD_V14.md`.

## Manifest

`manifest.toml` carries an explicit, ordered `[[sections]]` list of
`{id, path, must_contain}` entries — **never a glob**. A glob silently
reorders sections and DNS stops being Phase -1; ordering is doctrine, not
presentation. Every section's `must_contain` tokens are asserted against the
section text at build time; a missing token fails the compile and names the
section and token.

## Compile gates

Gates run over the built output and fail the build with line-numbered
findings:

- `lint/forbidden.txt` — one regex per line covering the estate's named
  defects: name-hashing instead of byte digests, empty signature fields,
  placeholder key identities, hardcoded SBOM spec versions, the
  author-filtered collections query shape, credential values passed to a
  print call, and the forbidden unhyphenated `.com` domain (written defanged
  throughout this document precisely because the gate watches for it).
- `lint/banned_claims.txt` — unprovable superiority and priority claims, plus
  a proximity rule: the standalone word for "carrying a signature" may not
  appear within 200 characters of an `.unsigned.json` reference, so an
  unattested artifact is never described as attested.
- `proxied_pages_apex` (compound, enforced in code): a proxy-enabled flag
  near a `185.199.*` Pages address is the orange-cloud-on-apex bug and fails
  the build.
- `require_dns_first`: the `phase_neg1_dns` section must precede every
  section whose id contains `train`. DNS-first is enforced twice — once by
  document order, once here.

## Determinism

Each section is emitted behind an inline digest comment naming the section id
and the sha256 of its exact bytes. The build is a pure function of sections +
manifest: no timestamps, no randomness, no environment leakage. Build time
lives only in the export receipt (`embed_build_time_in_body = false`), which
is what makes the idempotency proof possible: build, copy `dist/`, rebuild,
`diff -q` must report byte-identical output.

## Extract tags

A comment of the form `<!-- extract: <relpath> mode=<octal> -->` immediately
followed by a fenced code block writes that block to
`dist/extracted/<relpath>` with the given mode, reporting a sha256 per file.
Because this document is fed to agents, the extract path is a security
boundary: any path containing `..` or an absolute path is rejected before
anything is written.

## Export

Export writes `dist/export/export_manifest.unsigned.json` — payload digest,
per-section digests, extracted-file subjects, `generated_by`, and
`publication_eligible` (false in the default build) — canonicalized with
RFC 8785 before its digest is taken. The file is named `.unsigned.json`
because its `signatures` array is empty; honest naming is the doctrine, and
this package obeys it on itself. The export also renders the operator-facing
report, the ten-answer operator packet (every answer UNKNOWN until evidence
exists), and the receipt.

## Verify

`verify` re-digests every section against the digest comments in the built
document, re-runs all gates over the built file, asserts the export manifest
is named `.unsigned.json` with an empty `signatures` array, greps all of
`dist/` for the forbidden domain, and asserts `publication_eligible` is
false. Exit codes: 0 clean, 2 gate failure, 3 operational error.

## Hand-off (Codex contract)

Codex receives exactly two paths: `dist/SZL_MASTER_PAYLOAD_V14.md` (the
doctrine) and `dist/extracted/` (the scaffold). No retyping; every file is
digested; every command supports `--help` and `--json` and emits its own
receipt. Pass 1 is read-only: build, verify, idempotency, doctor, audit,
dns/tunnel/deploy inspect, remediate and dns plans, correctness fixes with
tests — then stop. Pass 2 is authorized only: pins, baseline-first eval, DNS
apply one record set at a time, train, sealed eval, attest, publish gated on
the computed eligibility boolean.

UNKNOWN is never PASS.
