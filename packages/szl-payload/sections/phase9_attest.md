# Phase 9 — Attest

Attestation binds the run to its artifacts. Everything attested here is
digested over bytes, wrapped in a standard envelope, and published only when
the computed eligibility chain says so.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## Byte digests

Every subject gets byte digests via chunked `sha256_file` over its exact
bytes — the payload, each extracted scaffold file, the corpus seal, the
model artifacts, the audit matrix. A name-derived digest voids the
attestation (Defect 1).

## Envelope and predicate

Subjects are wrapped in an in-toto v1 Statement with `predicateType`
`https://szlholdings.com/receipt/v1`, serialized as canonical RFC 8785 JSON
before the payload digest is taken, and carried in a DSSE envelope.

## Key-armed attestation

With an armed key (Pass 2), the envelope is attested with
**cosign attest-blob** against the digest set. Until a key is armed — which is the
default state, `PRODUCTION_SIGNING=false` — every manifest this estate emits
keeps an empty `signatures` array and carries the honest `.unsigned.json`
name; the naming doctrine from Phase 1 applies to this package's own export
manifest exactly as it applies to everything else.

## publication_eligible is computed, never asserted

`publication_eligible` is an AND-chain over measured terms —
`inventory_complete`, `artifact_hashes_verified`, `dns_verified`,
`deployment_health_passed`, `forbidden_domain_scan_passed`, and their peers —
not a flag anyone sets. Manually asserting release eligibility is on the V13
hard-failure list. Exceptions require a new, separately attested public
exception predicate. The default build serializes `publication_eligible` as
false.

## One hash per provenance chain

The estate provenance chain runs SHA-256 end to end. Where another hash
family is specified for a hardware receipt engine, the two domains must not
cross without explicit domain separation plus a cross-language test vector —
the SIGv1/DSSEv1 preimage regression (pinned as a CI assertion in Phase 10's
queue) is the standing example of what happens when they do.

UNKNOWN is never PASS: an artifact whose digest cannot be recomputed is
UNKNOWN, and the attestation lists it as failed verification, not as absent.
