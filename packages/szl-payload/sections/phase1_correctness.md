# Phase 1 — Correctness Fixes

Four defects, now unanimous across every review. They are fixed first because
every later phase — audit, corpus seal, MCP drift, attestation — inherits
their semantics. Each fix lands with tests in Pass 1 (local code only; no
network mutation).

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## Defect 1 — digest artifact bytes, never names

Hash a file by reading it: chunked `sha256_file()` over the artifact bytes,
1 MiB chunks, so a 40 GB model and a 4 KB manifest take the same code path.
The anti-pattern is `sha256(name.encode())` where `name` is a string literal
like the repo slug — that produces a digest of a *label*, not of the artifact,
and it is a diligence-ending defect: a reviewer who recomputes the digest gets
different bytes and every downstream receipt is void. The lint gate carries a
regex for this shape; it fails the build on sight.

## Defect 2 — real RFC 8785, not sorted-key dumps

Canonicalization uses a genuine RFC 8785 JCS implementation (the `rfc8785`
package, pinned exact). `json.dumps(sort_keys=True)` is **not** JCS: number
serialization (ES6 shortest-round-trip notation, the 1e20/1e21 boundary) and
unicode/string escaping differ, so two honest implementations canonicalize the
same document to different bytes. False drift kills the gate; missed drift
lets poison through. This is also why the Phase 6 MCP drift check compares
canonical bytes: a whitespace-only, canonical-equivalent change must NOT
raise drift.

## Defect 3 — honest naming for unattested artifacts

An artifact with no signature is named `*.unsigned.json` — for example the
builder's own `export_manifest.unsigned.json`. An envelope with an empty
`sig` field or a blank `signatures` array is not an attestation and must never
be presented as one; the name says what the bytes prove. The estate already
ships this doctrine in `szl-router` (armed key produces an attestation,
otherwise the UNSIGNED-honest path) — reuse it, do not reimplement it. A
placeholder key identity such as `PENDING-SIGSTORE` is a compile-blocking
pattern for the same reason.

## Defect 4 — UNKNOWN is never PASS

`UNKNOWN` is a distinct terminal state in
`PASS | WARN | FAIL | BLOCKED | UNKNOWN` and is never coerced to PASS. If
evidence cannot be produced — a probe fails, a credential is malformed, a
measurement is unavailable — the state stays OPEN/UNVERIFIED and the phase
blocks. No fake green.

Companion rule: stop hardcoding the CycloneDX `specVersion` value `1.6` in
exporters. Read it from `configs/export_policy.json` — a 1.7 schema is
already in circulation and a hardcoded version silently invalidates every
SBOM the estate emits.

## Scaffold

`sha256_file` — the only way this estate digests files:

<!-- extract: szl_v14/hashing.py mode=644 -->
```python
"""Chunked artifact digests. Bytes in, digest out — never a name."""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 1 << 20  # 1 MiB


def sha256_file(path: str | Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Digest the exact bytes of `path`, read in chunks.

    The digest commits to the artifact, not to its label: two files with the
    same name and different bytes produce different digests, and one file
    renamed produces the same digest. That is the property receipts need.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
```

Export policy — versions are configuration, not string literals in code:

<!-- extract: configs/export_policy.json mode=644 -->
```json
{
  "cyclonedx_spec_version": "1.7",
  "receipt_predicate_type": "https://szlholdings.com/receipt/v1",
  "intoto_statement_version": 1,
  "digest_algorithm": "sha256"
}
```

Pass 1 applies these fixes with tests and then stops; that stop is the
correct outcome, not a failure.
