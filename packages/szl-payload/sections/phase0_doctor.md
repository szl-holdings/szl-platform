# Phase 0 — Doctor

Doctor is the first executable gate of every run. Its top section reads,
literally:

## BLOCKERS THAT OUTRANK ALL COSMETIC WORK

No cosmetic work — no README polish, no badge, no copy edit — is scheduled
while any blocker below is open. Doctor exits non-zero when any hard gate
fails; a failing doctor stops the run, it never gets worked around.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## Hard gates

1. **Cloudflare token verify.** `GET /client/v4/user/tokens/verify` must
   return `"status":"active"`. This is a hard `sys.exit()` gate: while the
   credential is malformed (error-6003 class, see Phase -1), every downstream
   DNS check is UNKNOWN, and UNKNOWN is never PASS.
2. **Hugging Face inventory probe.** With `huggingface_hub>=1.0`, a failing
   `list_user_repos(namespace=...)` call is **FATAL**: it is the only call
   that surfaces buckets and storage bytes, and an audit that cannot see
   buckets is structurally incomplete (Phase 2). `author=` listings are not a
   substitute.
3. **Standing blockers printed verbatim.** The known blocker list (zone
   NXDOMAIN, Cloudflare key, Model BOM incomplete, unattacked receipt claim,
   no pricing, solo-founder gate, Daybreak Blue key deadline) prints under the
   header above on every run until each is retired with evidence.

## Per-phase print block

Every phase — doctor included — prints:

```
STATUS: PASS|WARN|FAIL|BLOCKED|UNKNOWN
EVIDENCE: <command output, digests, URLs probed>
ROLLBACK: <exact reversal for anything this phase changed, or "none — read-only">
NEXT SAFE ACTION: <the single next command an operator may safely run>
RECEIPT: <path to the receipt this phase emitted>
```

Never report "fixed" without a post-fix check; never report "deployed"
without a serving revision. UNKNOWN is a distinct printed state and is never
promoted to PASS.

## Scaffold

The extract below is the runnable doctor seed for the `szl-v14/` scaffold
(constructed from `dist/extracted/` per the Codex contract). It implements the
two hard gates above, prints the blocker header first, and exits non-zero on
any failure. Credentials are read from the environment and are never printed.

<!-- extract: szl_v14/doctor.py mode=755 -->
```python
#!/usr/bin/env python3
"""szl-v14 doctor — Phase 0 hard gates.

Gate 1: Cloudflare credential must verify "status":"active" via
        /user/tokens/verify. Failure is a hard exit: every downstream DNS
        check is UNKNOWN while the credential is malformed.
Gate 2: huggingface_hub >= 1.0 list_user_repos(namespace=...) must succeed;
        it is the only bucket-visible call and a failed call means the audit
        is structurally incomplete. Failure is FATAL.

Never prints credential material. Exits 0 only when every gate passes;
exits 2 on any gate failure; exits 3 on operational error.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BLOCKER_HEADER = "BLOCKERS THAT OUTRANK ALL COSMETIC WORK"


def check_cloudflare() -> tuple[str, str]:
    """Return (status, evidence). Hard gate: /user/tokens/verify."""
    credential = os.environ.get("CLOUDFLARE_CREDENTIAL", "")
    if not credential:
        return "FAIL", "CLOUDFLARE_CREDENTIAL is not set in the environment"
    request = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/user/tokens/verify",
        headers={"Authorization": "Bearer " + credential},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # network and API errors both fail closed
        return "FAIL", f"/user/tokens/verify request failed: {exc!r}"
    status = body.get("result", {}).get("status", "unknown")
    if status != "active":
        return "FAIL", f"/user/tokens/verify returned status={status!r}"
    return "PASS", "/user/tokens/verify returned status='active'"


def check_hf_inventory(namespace: str) -> tuple[str, str]:
    """Return (status, evidence). FATAL on failure: bucket-visible call."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return "FAIL", "huggingface_hub>=1.0 is not installed"
    credential = os.environ.get("HF_CREDENTIAL") or None
    try:
        repos = list(HfApi(token=credential).list_user_repos(namespace=namespace))
    except Exception as exc:
        return "FAIL", f"list_user_repos(namespace={namespace!r}) failed: {exc!r}"
    return "PASS", f"list_user_repos(namespace={namespace!r}) returned {len(repos)} repos"


def main() -> int:
    print(BLOCKER_HEADER)
    findings = []
    for name, check in [
        ("cloudflare", check_cloudflare),
        ("hf_inventory", lambda: check_hf_inventory("SZLHOLDINGS")),
    ]:
        status, evidence = check()
        print(f"STATUS: {status}")
        print(f"EVIDENCE: {evidence}")
        print("ROLLBACK: none — read-only")
        print("NEXT SAFE ACTION: repair the credential, then re-run doctor")
        print(f"RECEIPT: stdout (gate={name})")
        findings.append(status)
    return 0 if all(s == "PASS" for s in findings) else 2


if __name__ == "__main__":
    sys.exit(main())
```

UNKNOWN is never PASS: any check that cannot produce evidence prints UNKNOWN
and the phase blocks.
