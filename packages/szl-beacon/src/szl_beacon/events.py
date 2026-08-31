"""Event model for the A11oy Beacon REALITY PROTOCOL.

A Reality Transaction is a sequence of signed-style events, one per state
transition, appended to an append-only hash-chained log. Every event carries
exactly one evidence label (see :mod:`szl_beacon.labels`) — an event without a
label is a protocol violation and is refused fail-closed.

Event fields::

    event_id      sha256 hex digest of the canonical body (content address)
    seq           monotonically increasing integer position in the local log
    prev          hex digest of the previous event, or null at genesis
    state_from    protocol state the transition leaves (null at genesis)
    state_to      protocol state the transition enters
    actor         who/what produced the event: {"kind", "id"}
    payload       transition-specific body (free-form mapping)
    evidence_refs list of content digests of the evidence this event relies on
    label         evidence label (see labels.py) — REQUIRED
    created_at    ISO-8601 UTC timestamp string

CANONICAL FORM — READ THIS BEFORE INTEROP.
    In this reference implementation the canonical form is
    ``json.dumps(body, sort_keys=True, separators=(",", ":"))`` encoded as
    UTF-8: sorted keys, no whitespace. This is **not** RFC 8785 (JCS): JCS
    additionally pins number serialization (ECMAScript ``Number::toString``)
    and Unicode handling, which ``json.dumps`` does not guarantee. The
    production implementation canonicalizes with RFC 8785 via the
    ``szl-receipts`` package. This package is deliberately stdlib-only, and
    says so: do not claim JCS conformance for these digests. Integers and
    strings canonicalize identically under both schemes; non-integer floats
    are the divergence risk and are rejected from canonical bodies here.

SIGNING.
    "Signed-style" means every event is content-addressed and hash-chained.
    Real digital signatures (per-device Ed25519 keys, TPM-backed) attach in
    production via szl-receipts' DSSE envelope; this reference implementation
    models the chain integrity and actor binding, not key management.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .labels import Label, LabelError, validate_event_label

__all__ = [
    "GENESIS_PREV",
    "EventValidationError",
    "canonical_dumps",
    "event_digest",
    "new_event",
    "validate_event",
    "validate_event_dict",
]

#: The ``prev`` value of the first event in a log. Explicit null-equivalent.
GENESIS_PREV = None

#: Fields that make up a well-formed event, in schema order.
EVENT_FIELDS = (
    "event_id",
    "seq",
    "prev",
    "state_from",
    "state_to",
    "actor",
    "payload",
    "evidence_refs",
    "label",
    "created_at",
)

#: Fields covered by the content digest (everything except event_id itself).
_DIGESTED_FIELDS = tuple(f for f in EVENT_FIELDS if f != "event_id")

_HEX_DIGITS = frozenset("0123456789abcdef")


class EventValidationError(ValueError):
    """Raised when an event fails schema or label validation. Fail closed."""


def _reject_noninteger_floats(value: Any, path: str = "$") -> None:
    """Refuse floats that JCS and json.dumps serialize differently.

    Integers-valued floats (``3.0``) canonicalize identically; anything else
    is a cross-implementation divergence risk, so the reference
    implementation refuses it rather than emitting an ambiguous digest.
    """

    if isinstance(value, float):
        if not value.is_integer():
            raise EventValidationError(
                f"non-integer float at {path} is not portable across canonicalizers; "
                "use an integer or a decimal string"
            )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_noninteger_floats(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_noninteger_floats(item, f"{path}[{index}]")


def canonical_dumps(body: dict) -> str:
    """Canonical JSON for this reference implementation.

    Sorted keys, no whitespace, UTF-8. NOT RFC 8785 — see module docstring.
    Raises :class:`EventValidationError` for non-portable values.
    """

    _reject_noninteger_floats(body)
    try:
        return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise EventValidationError(f"event body is not JSON-serializable: {exc}") from exc


def event_digest(body: dict) -> str:
    """sha256 hex digest of the canonical form of ``body``.

    ``body`` must contain the digested fields (all fields except event_id);
    extra keys are ignored so callers may pass a full event.
    """

    canonical = {key: body.get(key) for key in _DIGESTED_FIELDS}
    return hashlib.sha256(canonical_dumps(canonical).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EventValidationError(message)


def _validate_actor(actor: object) -> None:
    _require(isinstance(actor, dict), "actor must be an object {kind, id}")
    kind = actor.get("kind")
    _require(isinstance(kind, str) and bool(kind), "actor.kind must be a non-empty string")
    ident = actor.get("id")
    _require(isinstance(ident, str) and bool(ident), "actor.id must be a non-empty string")


def _validate_evidence_refs(refs: object) -> None:
    _require(isinstance(refs, list), "evidence_refs must be a list")
    for ref in refs:
        _require(isinstance(ref, str), "evidence_refs entries must be strings")
        _require(len(ref) > 0, "evidence_refs entries must be non-empty")


def validate_event_dict(event: dict, *, require_digest_match: bool = True) -> None:
    """Validate a complete event mapping. Raises :class:`EventValidationError`.

    Checks, in order: field set, types, hash-chain shape (``prev`` is null iff
    ``seq == 0``), digest integrity (``event_id`` matches the canonical body),
    and label validity via :func:`szl_beacon.labels.validate_event_label`.
    """

    _require(isinstance(event, dict), "event must be a JSON object")

    unknown = set(event) - set(EVENT_FIELDS)
    _require(not unknown, f"unknown event fields: {sorted(unknown)}")
    missing = [f for f in EVENT_FIELDS if f not in event]
    _require(not missing, f"missing event fields: {missing}")

    seq = event["seq"]
    _require(isinstance(seq, int) and not isinstance(seq, bool), "seq must be an integer")
    _require(seq >= 0, "seq must be >= 0")

    prev = event["prev"]
    if seq == 0:
        _require(prev is None, "genesis event (seq 0) must have prev = null")
    else:
        _require(
            isinstance(prev, str) and len(prev) == 64 and set(prev) <= _HEX_DIGITS,
            "prev must be a lowercase sha256 hex digest",
        )

    for state_field in ("state_from", "state_to"):
        value = event[state_field]
        if state_field == "state_from" and seq == 0:
            _require(value is None, "genesis event must have state_from = null")
        else:
            _require(
                isinstance(value, str) and bool(value),
                f"{state_field} must be a non-empty string",
            )

    _validate_actor(event["actor"])
    _require(isinstance(event["payload"], dict), "payload must be an object")
    _validate_evidence_refs(event["evidence_refs"])

    created_at = event["created_at"]
    _require(
        isinstance(created_at, str) and created_at.endswith("Z") and "T" in created_at,
        "created_at must be an ISO-8601 UTC timestamp ending in 'Z'",
    )

    origin = event["actor"].get("kind")
    try:
        validate_event_label(event["label"], origin=origin)
    except LabelError as exc:
        raise EventValidationError(str(exc)) from exc

    if require_digest_match:
        actual = event["event_id"]
        _require(
            isinstance(actual, str) and len(actual) == 64 and set(actual) <= _HEX_DIGITS,
            "event_id must be a lowercase sha256 hex digest",
        )
        expected = event_digest(event)
        _require(
            actual == expected,
            f"event_id digest mismatch: declared {actual[:16]}… != computed {expected[:16]}…",
        )


def validate_event(event: dict) -> dict:
    """Validate and return the event. Convenience wrapper."""

    validate_event_dict(event)
    return event


def new_event(
    *,
    seq: int,
    prev: str | None,
    state_from: str | None,
    state_to: str,
    actor: dict,
    payload: dict | None = None,
    evidence_refs: list[str] | None = None,
    label: Label | str,
    created_at: str,
) -> dict:
    """Construct, digest, and validate a new event.

    The caller supplies everything except ``event_id``, which is computed
    from the canonical body. Construction is fail-closed: the returned event
    has passed full validation or no event is returned at all.
    """

    event = {
        "seq": seq,
        "prev": prev,
        "state_from": state_from,
        "state_to": state_to,
        "actor": actor,
        "payload": dict(payload or {}),
        "evidence_refs": list(evidence_refs or []),
        "label": label.value if isinstance(label, Label) else label,
        "created_at": created_at,
    }
    event["event_id"] = event_digest(event)
    # Full validation at birth: no malformed event ever enters a log through
    # this constructor.
    validate_event_dict(event)
    return event
