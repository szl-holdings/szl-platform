"""KIDS v0.1 RC1 mailbox model.

The RC1 mailbox is the ONLY path by which privileged commands may be
authorized. Only commands delivered via RC1_SEND with a valid envelope —
schema_version, target_id, command_type, bounds, nonce, expiry_cycle,
policy_digest, auth_tag — may execute privileged ops.

Anti-replay: a monotonic counter lives in protected NV (modeled by engine
state). A previously accepted nonce is never accepted again: the accepted
nonce must be strictly greater than every previously accepted nonce.

RC1-04 analogue ("Linux bypass"): any attempt by AP context to write the
mailbox directly — i.e. to toggle a privileged output NOT via the RC1
path — raises HardPartitionFault (see memory.py) and is logged as
BYPASS_ATTEMPT.

auth_tag in the v0.1 golden simulator is HMAC-SHA3-256 over the canonical
envelope fields under a test key. The RTL/secure-element design replaces
this with a hardware key; the sim fixes only the semantics.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

RC1_SCHEMA_VERSION = "1"
RC1_DOMAIN: bytes = b"SZL-KIDS-RC1-V1"

ENVELOPE_FIELDS = (
    "schema_version",
    "target_id",
    "command_type",
    "bounds",
    "nonce",
    "expiry_cycle",
    "policy_digest",
    "auth_tag",
)

# Fields covered by the auth tag (everything except the tag itself).
SIGNED_FIELDS = tuple(f for f in ENVELOPE_FIELDS if f != "auth_tag")


class RC1Reject(Exception):
    """Envelope rejected: malformed / expired / replayed / unauthorized."""


def canonical_envelope(env: dict[str, Any]) -> bytes:
    body = {f: env[f] for f in SIGNED_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def compute_auth_tag(env: dict[str, Any], key: bytes) -> str:
    return hmac.new(key, RC1_DOMAIN + canonical_envelope(env), hashlib.sha3_256).hexdigest()


@dataclass
class Mailbox:
    mailbox_id: int
    envelopes: list[dict[str, Any]]


class RC1Controller:
    """The RC1 governance engine side of the mailbox."""

    def __init__(self, device_id: str, auth_key: bytes, accepted_policy_digests: set[str]):
        self.device_id = device_id
        self._auth_key = auth_key
        self.accepted_policy_digests = set(accepted_policy_digests)
        # Protected NV monotonic anti-replay counter: highest accepted nonce.
        self.highest_nonce = -1
        self.mailboxes: dict[int, Mailbox] = {}
        self.reject_log: list[dict[str, Any]] = []

    # --- validation -----------------------------------------------------
    def validate_envelope(self, env: dict[str, Any], current_cycle: int) -> None:
        """Reject malformed/expired/replayed/unauthorized. Fail closed."""
        try:
            if not isinstance(env, dict):
                raise RC1Reject("envelope is not an object")
            missing = [f for f in ENVELOPE_FIELDS if f not in env]
            if missing:
                raise RC1Reject(f"malformed: missing fields {missing}")
            if env["schema_version"] != RC1_SCHEMA_VERSION:
                raise RC1Reject(f"unsupported schema_version {env['schema_version']!r}")
            if env["target_id"] != self.device_id:
                raise RC1Reject(f"wrong target_id {env['target_id']!r}")
            if not isinstance(env["nonce"], int) or isinstance(env["nonce"], bool):
                raise RC1Reject("nonce must be an integer")
            if env["nonce"] <= self.highest_nonce:
                raise RC1Reject(f"replayed/stale nonce {env['nonce']} <= {self.highest_nonce}")
            if not isinstance(env["expiry_cycle"], int):
                raise RC1Reject("expiry_cycle must be an integer")
            if current_cycle > env["expiry_cycle"]:
                raise RC1Reject(
                    f"expired: cycle {current_cycle} > expiry {env['expiry_cycle']}"
                )
            if env["policy_digest"] not in self.accepted_policy_digests:
                raise RC1Reject("policy_digest not authorized on this device")
            expected = compute_auth_tag(env, self._auth_key)
            if not hmac.compare_digest(expected, str(env["auth_tag"])):
                raise RC1Reject("auth_tag mismatch (unauthorized)")
            if not isinstance(env["bounds"], dict):
                raise RC1Reject("bounds must be an object")
            if not isinstance(env["command_type"], str):
                raise RC1Reject("command_type must be a string")
        except RC1Reject as e:
            self.reject_log.append({"envelope": env if isinstance(env, dict) else None,
                                    "reason": str(e)})
            raise

    # --- mailbox ---------------------------------------------------------
    def send(self, mailbox_id: int, env: dict[str, Any], current_cycle: int) -> None:
        """RC1_SEND: validate then enqueue. On success the nonce is burned
        into protected NV — it can never be accepted again."""
        self.validate_envelope(env, current_cycle)
        self.highest_nonce = env["nonce"]  # anti-replay, monotonic in protected NV
        self.mailboxes.setdefault(mailbox_id, Mailbox(mailbox_id, [])).envelopes.append(env)

    def recv(self, mailbox_id: int) -> dict[str, Any] | None:
        """RC1_RECV: pop the next validated envelope from a mailbox."""
        mb = self.mailboxes.get(mailbox_id)
        if mb is None or not mb.envelopes:
            return None
        return mb.envelopes.pop(0)
