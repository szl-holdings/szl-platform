"""Reality Debt register.

Reality Debt is the protocol's memory of everything that is NOT established:
conflicting evidence, a missing witness, a failed verification, an
unverified claim. Debt is the anti-"fake green" mechanism:

  * Debt items OPEN, they never close themselves.
  * OPEN debt of kind EVIDENCE_CONFLICT, MISSING_WITNESS or
    VERIFICATION_FAILED blocks promotion of an outcome to VERIFIED.
  * A debt resolves ONLY via an explicit reconciliation event naming the
    debt id. There is no auto-resolution, no timeout, no "probably fine".

A debt item::

    {"id": "debt-<12 hex>", "kind": <DebtKind>, "state": "OPEN"|"RESOLVED",
     "detail": <free-form mapping>, "opened_by": <event digest>,
     "resolved_by": <event digest or null>}
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any

__all__ = [
    "DebtError",
    "DebtKind",
    "DebtRegister",
    "DebtState",
]

#: Debt kinds that gate promotion of an outcome to VERIFIED.
BLOCKING_KINDS: frozenset[DebtKind]


class DebtKind(StrEnum):
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    MISSING_WITNESS = "MISSING_WITNESS"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"


BLOCKING_KINDS = frozenset(
    {
        DebtKind.EVIDENCE_CONFLICT,
        DebtKind.MISSING_WITNESS,
        DebtKind.VERIFICATION_FAILED,
    }
)


class DebtState(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class DebtError(RuntimeError):
    """Raised on debt-register misuse (e.g. resolving an unknown debt)."""


class DebtRegister:
    """In-memory Reality Debt register for one transaction or one node."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _make_id(kind: DebtKind, detail: dict[str, Any], opened_by: str) -> str:
        material = f"{kind.value}|{opened_by}|{sorted(map(str, detail.items()))}"
        return "debt-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]

    def open(
        self,
        kind: DebtKind | str,
        detail: dict[str, Any],
        *,
        opened_by: str,
    ) -> dict[str, Any]:
        """Open a debt item and return it.

        ``opened_by`` is the digest of the event that surfaced the debt, so
        every debt is traceable to the record that created it. Duplicate
        opens of identical (kind, detail, opened_by) are idempotent: the
        existing OPEN item is returned, not a second one.
        """

        kind = DebtKind(kind)
        debt_id = self._make_id(kind, detail, opened_by)
        existing = self._items.get(debt_id)
        if existing is not None:
            return existing
        item: dict[str, Any] = {
            "id": debt_id,
            "kind": kind.value,
            "state": DebtState.OPEN.value,
            "detail": dict(detail),
            "opened_by": opened_by,
            "resolved_by": None,
        }
        self._items[debt_id] = item
        return item

    def resolve(self, debt_id: str, *, resolved_by: str) -> dict[str, Any]:
        """Explicitly resolve a debt, naming the reconciliation event digest.

        Resolving an unknown or already-resolved debt is an error — debt
        accounting must stay exact, so sloppy resolution is refused, not
        tolerated.
        """

        item = self._items.get(debt_id)
        if item is None:
            raise DebtError(f"cannot resolve unknown debt {debt_id!r}")
        if item["state"] == DebtState.RESOLVED.value:
            raise DebtError(f"debt {debt_id!r} is already resolved")
        item["state"] = DebtState.RESOLVED.value
        item["resolved_by"] = resolved_by
        return item

    def is_open(self, debt_id: str) -> bool:
        item = self._items.get(debt_id)
        return item is not None and item["state"] == DebtState.OPEN.value

    def open_items(self) -> list[dict[str, Any]]:
        return [i for i in self._items.values() if i["state"] == DebtState.OPEN.value]

    def blocking_items(self) -> list[dict[str, Any]]:
        """OPEN items of a kind that blocks OUTCOME -> VERIFIED promotion."""

        return [i for i in self.open_items() if i["kind"] in {k.value for k in BLOCKING_KINDS}]

    def blocks_verification(self) -> bool:
        """True iff any OPEN blocking debt exists. Fail closed."""

        return bool(self.blocking_items())

    def to_list(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._items.values()]

    def __len__(self) -> int:
        return len(self._items)
