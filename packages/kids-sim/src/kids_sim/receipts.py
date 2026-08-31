"""KIDS v0.1 SHA3-256 receipt engine.

receipt = sha3_256(DOMAIN || prev_digest || canonical_event_bytes)

with DOMAIN = b"SZL-KIDS-RECEIPT-V1".

DOMAIN SEPARATION IS MANDATORY. The KHIPU receipt chain uses SHA3-256
while the wider provenance estate uses SHA-256; mixing two hash functions
across one provenance chain without domain separation is a cross-domain
preimage risk (structurally the same class as the fixed SIGv1-vs-DSSEv1
bug — see discovery/fork_findings.md section 3). The domain constant makes
a KIDS receipt digest provably disjoint from any bare SHA3-256 digest and
from every other estate chain. vectors/receipt_domain_vector.json pins one
fixed event with an independently computed expected digest.

Every receipt carries a monotonic counter; verify_chain detects
truncation, reorder, and replay.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

DOMAIN: bytes = b"SZL-KIDS-RECEIPT-V1"
GENESIS: bytes = b"\x00" * 32


def canonical_event_bytes(event: dict[str, Any]) -> bytes:
    """Deterministic serialization: sorted keys, compact separators, UTF-8."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def compute_receipt(prev_digest: bytes, event: dict[str, Any]) -> bytes:
    """sha3_256(DOMAIN || prev_digest || canonical_event_bytes)."""
    h = hashlib.sha3_256()
    h.update(DOMAIN)
    h.update(prev_digest)
    h.update(canonical_event_bytes(event))
    return h.digest()


@dataclass(frozen=True)
class Receipt:
    counter: int  # monotonic, one per receipt, gapless from 0
    event: dict[str, Any]
    prev_digest: bytes
    digest: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "counter": self.counter,
            "event": self.event,
            "prev_digest": self.prev_digest.hex(),
            "digest": self.digest.hex(),
        }


class ReceiptEngine:
    """Stateful receipt chain. Counter is monotonic and never reused."""

    def __init__(self) -> None:
        self._receipts: list[Receipt] = []
        self._counter = 0

    @property
    def counter(self) -> int:
        return self._counter

    @property
    def root(self) -> bytes:
        return self._receipts[-1].digest if self._receipts else GENESIS

    @property
    def receipts(self) -> list[Receipt]:
        return list(self._receipts)

    def emit(self, event: dict[str, Any]) -> Receipt:
        event = dict(event)
        event["counter"] = self._counter  # monotonic counter bound INTO the event
        prev = self.root
        digest = compute_receipt(prev, event)
        r = Receipt(counter=self._counter, event=event, prev_digest=prev, digest=digest)
        self._receipts.append(r)
        self._counter += 1
        return r


class ChainVerificationError(ValueError):
    pass


def verify_chain(receipts: list[Receipt | dict[str, Any]],
                 events: list[dict[str, Any]] | None = None) -> bool:
    """Verify a receipt chain: linkage, counters, digests, and (if given)
    exact correspondence to the claimed events.

    Detects truncation (events longer than receipts), reorder, replay, and
    tampering. Raises ChainVerificationError on any failure; returns True
    on success.
    """
    rs: list[Receipt] = []
    for r in receipts:
        if isinstance(r, dict):
            r = Receipt(
                counter=r["counter"],
                event=r["event"],
                prev_digest=bytes.fromhex(r["prev_digest"]),
                digest=bytes.fromhex(r["digest"]),
            )
        rs.append(r)

    if events is not None and len(events) != len(rs):
        raise ChainVerificationError(
            f"truncation/length mismatch: {len(events)} events vs {len(rs)} receipts"
        )

    prev = GENESIS
    for i, r in enumerate(rs):
        if r.counter != i:
            raise ChainVerificationError(f"receipt {i}: counter {r.counter} != {i} (reorder/replay)")
        if r.prev_digest != prev:
            raise ChainVerificationError(f"receipt {i}: broken chain linkage")
        if r.event.get("counter") != i:
            raise ChainVerificationError(f"receipt {i}: event counter mismatch")
        if events is not None:
            expected_event = dict(events[i])
            expected_event["counter"] = i
            if r.event != expected_event:
                raise ChainVerificationError(f"receipt {i}: event does not match claimed event")
        if compute_receipt(r.prev_digest, r.event) != r.digest:
            raise ChainVerificationError(f"receipt {i}: digest mismatch (tamper)")
        prev = r.digest
    return True
