"""Read-time GovernedAction/v1 receipts for served claims.

Doctrine rule 1 of szl-receipts is *bytes, not names*: the digested subject
of a claim receipt is the claim's **canonical record bytes** (RFC 8785 JCS of
the full eight-key record), so the receipt binds exactly what was served —
from the Unicode in a description to the null of an unobserved claim.

Verdict → outcome mapping, fixed here in one place:

    PASS    → Outcome.PASS
    DRIFT   → Outcome.FAIL     (drift is the service catching its own org lying)
    UNKNOWN → Outcome.UNKNOWN  (never passing; the doctrine's first rule)

Receipts are cached in memory keyed by claim content hash. A claim whose
``observed`` changed hashes differently and therefore gets a NEW receipt —
the cache makes stale-receipt reuse structurally impossible, because the
stale receipt cannot be found under the new content's key. The policy block's
``version`` pins the claim's ``last_run``, so the receipt for one run cannot
sit under a later run's key either. Together this keeps a *re-verified* claim
byte-reproducible at a pinned ``created_at`` while guaranteeing that any
change in claim content or run mints a fresh identity.

The policy digest is sha256 over the canonical bytes of the seed registry —
the quoted “claims budget” this service holds the org to. It identifies the
policy document by its bytes, never by a filename anyone could rename.
"""

from __future__ import annotations

import threading
from typing import Any

from szl_receipts import (
    Outcome,
    build_receipt,
    jcs_canon_bytes,
    sha256_bytes,
    verify_receipt,
)

from szl_claims_api.seed import load_seed_registry

__all__ = [
    "CLAIM_VERIFY_ACTION",
    "POLICY_ID",
    "ReceiptMinter",
    "policy_digest",
]

#: The governed action every claim receipt records.
CLAIM_VERIFY_ACTION = "claim.verify"

#: Human id of the policy under which claim verification happens. The policy
#: is identified by digest, not name — see ``policy_digest``.
POLICY_ID = "szl-cps-claims-budget"

#: Fixed mapping from claims-file verdict to receipt outcome. DRIFT is not a
#: receipt verdict (the vocabulary is closed): a drifted claim is a governed
#: action whose measurement contradicted the claim — that is a FAIL.
_OUTCOME_BY_VERDICT: dict[str, Outcome] = {
    "PASS": Outcome.PASS,
    "DRIFT": Outcome.FAIL,
    "UNKNOWN": Outcome.UNKNOWN,
}

_RATIONALE_BY_VERDICT = {
    "PASS": "run recomputation matches the quoted claim",
    "DRIFT": "DRIFT: run recomputation contradicts the quoted claim — "
    "a blocker finding, not a statistic",
    "UNKNOWN": "claim not recomputed; UNKNOWN is never passing",
}

_policy_digest_cache: str | None = None


def policy_digest() -> str:
    """sha256 hex of the canonical seed-registry bytes (cached process-wide)."""
    global _policy_digest_cache
    if _policy_digest_cache is None:
        canonical = jcs_canon_bytes(load_seed_registry())
        _policy_digest_cache = sha256_bytes(canonical).hex()
    return _policy_digest_cache


#: Placeholder timestamp for UNKNOWN claims, which name no run. A timestamp
#: must still be timezone-grammatical (receipt schema demands it), and this
#: deterministic epoch value says exactly what it is: not a measurement
#: moment, because no measurement exists. It never masquerades as "now".
UNKNOWN_CREATED_AT = "1970-01-01T00:00:00Z"


def claim_canonical_bytes(claim: dict[str, Any]) -> bytes:
    """RFC 8785 canonical bytes of the full claim record (UTF-8 encoded)."""
    return jcs_canon_bytes(claim)


def claim_content_hash(claim: dict[str, Any]) -> str:
    """sha256 hex of the claim's canonical bytes — the cache key and subject digest."""
    return sha256_bytes(claim_canonical_bytes(claim)).hex()


class ReceiptMinter:
    """Builds claim receipts at read time, memoized by claim content hash.

    The cache lives in memory and dies with the process; nothing about a
    receipt needs persistence because any holder of the claims file can
    re-derive every receipt_id deterministically.
    """

    def __init__(self, actor: str = "szl-claims-api") -> None:
        self._actor = actor
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _created_at_for(self, claim: dict[str, Any]) -> str:
        last_run = claim.get("last_run")
        return last_run if isinstance(last_run, str) and last_run else UNKNOWN_CREATED_AT

    def _build(self, claim: dict[str, Any], content_hash: str) -> dict[str, Any]:
        verdict = claim["verdict"]
        outcome = _OUTCOME_BY_VERDICT[verdict]
        policy = {
            "id": POLICY_ID,
            "version": claim.get("last_run") or "unverified",
            "digest_sha256": policy_digest(),
        }
        return build_receipt(
            actor=self._actor,
            action=CLAIM_VERIFY_ACTION,
            policy=policy,
            outcome=outcome,
            rationale=(
                f"{claim['claim_id']} claimed {claim['expected']!r}: "
                f"{_RATIONALE_BY_VERDICT[verdict]}"
            ),
            subjects=[{"name": claim["claim_id"], "sha256": content_hash}],
            evidence=[{"uri": str(claim["source"])}],
            created_at=self._created_at_for(claim),
        )

    def receipt_for(self, claim: dict[str, Any]) -> dict[str, Any]:
        """The GovernedAction/v1 receipt for this claim, cached by content hash.

        A claim whose served bytes changed — a new observed value, a new
        last_run, anything — hashes to a new key and mints a new receipt.
        The documented self-check runs verify_receipt on every minted
        receipt and would raise AssertionError on any finding; it exists so
        a bug in this module surfaces loudly in tests rather than shipping
        an unverifiable receipt.
        """
        content_hash = claim_content_hash(claim)
        with self._lock:
            cached = self._cache.get(content_hash)
            if cached is not None:
                return dict(cached)
        receipt = self._build(claim, content_hash)
        findings = verify_receipt(receipt)
        if findings:  # pragma: no cover — a build-time bug, loudly surfaced
            raise AssertionError(f"self-built receipt failed verification: {findings}")
        with self._lock:
            self._cache[content_hash] = receipt
        return dict(receipt)

    def __len__(self) -> int:
        return len(self._cache)
