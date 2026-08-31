"""RC1 governance boundary — SOFTWARE SIMULATION.

*** SIMULATION — NOT HARDWARE. ***
This module models the RC1 microcontroller's acceptance behavior so the four
EVT acceptance tests (RC1-01..04) exist as executable fixtures before any
silicon exists. Zero physical units have been built. Nothing here energizes
anything; "output" is a software flag, "NV storage" is the event log.

RC1's job on real hardware: sit between the application processor and the
privileged output path, and refuse — electrically — any command that fails
validation. The tests:

  RC1-01  Unauthorized output stays safe: a command without valid
          authorization never energizes the output.
  RC1-02  Replay rejected: a previously accepted privileged command cannot
          be replayed (monotonic anti-replay, persisted in the log).
  RC1-03  Expired envelope rejected: expiry strictly less than now refuses.
  RC1-04  Application-processor bypass attempt raises BypassAttempt and
          energizes nothing.

Hardware safe-state on watchdog/reset/brownout is simulated as an explicit
SAFE_STATE event on the chain — on hardware this is electrical; here it is
modeled, and the log records that it is modeled.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import events as ev
from . import log as eventlog
from .labels import Label

__all__ = [
    "ActionEnvelope",
    "BypassAttempt",
    "EnvelopError",
    "RC1",
    "RC1Decision",
    "make_auth_tag",
]

SIM_LABEL = "RC1 SIMULATION — no hardware output is or can be energized"


class RC1Decision(StrEnum):
    ACCEPTED = "ACCEPTED"  # envelope valid; simulated output energized
    REJECTED = "REJECTED"  # malformed / expired / replayed / unauthorized
    BYPASS_REFUSED = "BYPASS_REFUSED"  # AP tried to skip RC1 entirely


class EnvelopError(ValueError):
    """Structural envelope validation failure."""


class BypassAttempt(RuntimeError):
    """The application processor tried to drive the privileged output
    directly, outside the RC1 path. On hardware this is electrically
    impossible by construction; in simulation it raises, loud, always."""


def make_auth_tag(envelope_fields: dict[str, Any], key: bytes) -> str:
    """HMAC-SHA256 over the canonical envelope fields (minus auth_tag).

    Simulation stand-in for the production authorization signature/MAC
    (secure-element-backed key on hardware).
    """

    body = {k: v for k, v in envelope_fields.items() if k != "auth_tag"}
    canonical = ev.canonical_dumps(body)
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


class ActionEnvelope:
    """The narrow-interface action envelope RC1 accepts.

    Fields (all required)::

        schema_version   int, must equal SCHEMA_VERSION
        target_id        str, device identity the command is for
        command_type     str, one of ALLOWED_COMMANDS
        bounds           mapping of numeric limits the command must stay in
        nonce            int, strictly greater than every accepted nonce
        expiry           int, POSIX seconds; now < expiry required
        policy_digest    str, sha256 hex of the policy decision authorizing
        auth_tag         str, HMAC-SHA256 hex over the other fields
    """

    SCHEMA_VERSION = 1
    ALLOWED_COMMANDS = frozenset({"OUTPUT_ON", "OUTPUT_OFF", "OUTPUT_PULSE"})

    REQUIRED_FIELDS = (
        "schema_version",
        "target_id",
        "command_type",
        "bounds",
        "nonce",
        "expiry",
        "policy_digest",
        "auth_tag",
    )

    def __init__(self, fields: dict[str, Any]) -> None:
        self.fields = dict(fields)
        self.validate()

    def validate(self) -> None:
        fields = self.fields
        for name in self.REQUIRED_FIELDS:
            if name not in fields:
                raise EnvelopError(f"missing envelope field: {name}")
        if fields["schema_version"] != self.SCHEMA_VERSION:
            raise EnvelopError(
                f"unsupported schema_version {fields['schema_version']!r}; "
                f"require {self.SCHEMA_VERSION}"
            )
        if not isinstance(fields["target_id"], str) or not fields["target_id"]:
            raise EnvelopError("target_id must be a non-empty string")
        if fields["command_type"] not in self.ALLOWED_COMMANDS:
            raise EnvelopError(f"unknown command_type {fields['command_type']!r}")
        if not isinstance(fields["bounds"], dict):
            raise EnvelopError("bounds must be a mapping of limits")
        for key, value in fields["bounds"].items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise EnvelopError(f"bounds.{key} must be numeric")
        if not isinstance(fields["nonce"], int) or isinstance(fields["nonce"], bool):
            raise EnvelopError("nonce must be an integer")
        if not isinstance(fields["expiry"], int) or isinstance(fields["expiry"], bool):
            raise EnvelopError("expiry must be integer POSIX seconds")
        for name in ("policy_digest", "auth_tag"):
            value = fields[name]
            if not (isinstance(value, str) and len(value) == 64):
                raise EnvelopError(f"{name} must be a 64-char hex digest")
            if set(value) - set("0123456789abcdef"):
                raise EnvelopError(f"{name} must be lowercase hex")

    def to_dict(self) -> dict[str, Any]:
        return dict(self.fields)


class RC1:
    """Simulated RC1 controller.

    Anti-replay state (the highest accepted nonce) is PERSISTED by appending
    acceptance decisions to the node's event log and rebuilding from it on
    construction — the simulation's stand-in for protected NV storage.
    """

    def __init__(
        self,
        logdir: Path | str,
        *,
        target_id: str,
        hmac_key: bytes,
        now: int,
    ) -> None:
        self.logdir = Path(logdir)
        self.target_id = target_id
        self._key = hmac_key
        self._now = now
        self._highest_nonce = self._restore_anti_replay()
        self.output_energized = False
        self.safe_state = False

    # ------------------------------------------------------- anti-replay NV

    def _restore_anti_replay(self) -> int:
        """Rebuild the monotonic nonce ceiling from the event log."""

        highest = 0
        logfile = self.logdir / eventlog.LOG_FILENAME
        if not logfile.exists():
            return highest
        try:
            for event in eventlog.read_events(self.logdir):
                payload = event.get("payload") or {}
                if payload.get("type") == "RC1_DECISION" and payload.get("decision") == (
                    RC1Decision.ACCEPTED.value
                ):
                    nonce = (payload.get("envelope") or {}).get("nonce")
                    if isinstance(nonce, int):
                        highest = max(highest, nonce)
        except ValueError:
            # A corrupt log loses anti-replay history: fail closed by
            # refusing everything (highest = infinity equivalent).
            return 2**63 - 1
        return highest

    # ------------------------------------------------------------- decisions

    def _record(self, decision: RC1Decision, *, reason: str, envelope: dict | None) -> dict:
        """Append the decision to the chain. Every decision is receipted."""

        from datetime import datetime

        head = eventlog.head(self.logdir)
        seq = 0 if head is None else int(head["seq"]) + 1
        prev = None if head is None else str(head["event_id"])
        event = ev.new_event(
            seq=seq,
            prev=prev,
            state_from=None if seq == 0 else "RC1",
            state_to="RC1",
            actor={"kind": "node", "id": self.target_id},
            payload={
                "type": "RC1_DECISION",
                "simulation": True,
                "simulation_note": SIM_LABEL,
                "decision": decision.value,
                "reason": reason,
                "envelope": envelope,
                "output_energized": self.output_energized,
            },
            evidence_refs=[],
            label=Label.AUTHORIZED_OPERATOR
            if decision is RC1Decision.ACCEPTED
            else Label.UNVERIFIED,
            created_at=datetime.fromtimestamp(self._now, tz=UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        )
        eventlog.append_event(self.logdir, event)
        return event

    def _reject(self, reason: str, envelope: dict | None) -> dict[str, Any]:
        self.output_energized = False  # rejected commands energize nothing
        event = self._record(RC1Decision.REJECTED, reason=reason, envelope=envelope)
        return {
            "decision": RC1Decision.REJECTED.value,
            "reason": reason,
            "output_energized": False,
            "simulation": True,
            "receipt": event["event_id"],
        }

    def receive(self, raw_envelope: dict[str, Any]) -> dict[str, Any]:
        """Validate an envelope and decide. NEVER raises for bad envelopes —
        on hardware a malformed envelope is a non-event; here it is a
        receipted rejection. The output stays de-energized on every failure.
        """

        if not isinstance(raw_envelope, dict):
            return self._reject("envelope is not a mapping", None)
        try:
            envelope = ActionEnvelope(raw_envelope)
        except EnvelopError as exc:
            return self._reject(f"malformed envelope: {exc}", raw_envelope)

        fields = envelope.fields

        if fields["target_id"] != self.target_id:
            return self._reject(
                f"envelope targets {fields['target_id']!r}, this RC1 is {self.target_id!r}",
                fields,
            )
        if self._now >= fields["expiry"]:
            self.output_energized = False
            return self._reject("envelope expired", fields)
        if fields["nonce"] <= self._highest_nonce:
            return self._reject(
                f"nonce {fields['nonce']} not greater than highest accepted "
                f"{self._highest_nonce}: replay refused",
                fields,
            )
        expected_tag = make_auth_tag(fields, self._key)
        if not hmac.compare_digest(expected_tag, fields["auth_tag"]):
            return self._reject("authorization tag invalid", fields)

        # All checks passed: energize (simulated flag) and record acceptance,
        # advancing the monotonic nonce ceiling.
        self._highest_nonce = fields["nonce"]
        self.output_energized = True
        event = self._record(
            RC1Decision.ACCEPTED,
            reason="envelope valid; simulated output energized",
            envelope=fields,
        )
        return {
            "decision": RC1Decision.ACCEPTED.value,
            "reason": "envelope valid",
            "output_energized": True,
            "simulation": True,
            "receipt": event["event_id"],
            "nonce_ceiling": self._highest_nonce,
        }

    def bypass_output(self, *, origin: str = "application_processor") -> None:
        """The RC1-04 path: AP attempts to drive the output without RC1.

        Always raises :class:`BypassAttempt`; the simulated output flag is
        forced off and an explicit BYPASS_REFUSED record hits the chain.
        """

        self.output_energized = False
        self._record(
            RC1Decision.BYPASS_REFUSED,
            reason=f"direct output drive attempted by {origin}; refused, nothing energized",
            envelope=None,
        )
        raise BypassAttempt(
            f"{origin} attempted to bypass the RC1 governance boundary; "
            "nothing energized (simulation)"
        )

    def safe_state_event(self, *, reason: str) -> dict[str, Any]:
        """Model the hardware safe-state on watchdog/reset/brownout.

        The output is de-energized and an explicit SAFE_STATE event is
        appended — labeled as simulation, never implied to be hardware.
        """

        self.output_energized = False
        self.safe_state = True
        head = eventlog.head(self.logdir)
        seq = 0 if head is None else int(head["seq"]) + 1
        prev = None if head is None else str(head["event_id"])
        from datetime import datetime

        event = ev.new_event(
            seq=seq,
            prev=prev,
            state_from=None if seq == 0 else "RC1",
            state_to="SAFE_STATE",
            actor={"kind": "node", "id": self.target_id},
            payload={
                "type": "SAFE_STATE",
                "simulation": True,
                "simulation_note": SIM_LABEL,
                "reason": reason,
                "output_energized": False,
            },
            evidence_refs=[],
            label=Label.UNVERIFIED,
            created_at=datetime.fromtimestamp(self._now, tz=UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        )
        eventlog.append_event(self.logdir, event)
        return event


# -- the four EVT acceptance fixtures, executable ----------------------------


def build_valid_envelope(rc1: RC1, *, nonce: int, expiry: int, command: str = "OUTPUT_ON") -> dict:
    """Helper: a fully valid envelope for ``rc1`` (tests and CLI use this)."""

    fields: dict[str, Any] = {
        "schema_version": ActionEnvelope.SCHEMA_VERSION,
        "target_id": rc1.target_id,
        "command_type": command,
        "bounds": {"max_duration_s": 5},
        "nonce": nonce,
        "expiry": expiry,
        "policy_digest": hashlib.sha256(b"reference-policy").hexdigest(),
    }
    fields["auth_tag"] = make_auth_tag(fields, rc1._key)
    return fields


def run_acceptance_fixtures(logdir: Path | str) -> list[dict[str, Any]]:
    """Run RC1-01..RC1-04 as executable fixtures. Returns four results."""

    results: list[dict[str, Any]] = []
    now = 1_800_000_000
    rc1 = RC1(logdir, target_id="RC1-SIM-01", hmac_key=b"reference-test-key", now=now)

    # RC1-01: unauthorized output stays safe --------------------------------
    bad = build_valid_envelope(rc1, nonce=1, expiry=now + 60)
    bad["auth_tag"] = "0" * 64  # forged/invalid authorization
    res = rc1.receive(bad)
    results.append(
        {
            "test": "RC1-01",
            "name": "unauthorized output stays safe",
            "passed": res["decision"] == RC1Decision.REJECTED.value
            and res["output_energized"] is False,
            "detail": res["reason"],
        }
    )

    # RC1-02: replay rejected ------------------------------------------------
    good = build_valid_envelope(rc1, nonce=1, expiry=now + 60)
    first = rc1.receive(good)
    replay = rc1.receive(dict(good))
    results.append(
        {
            "test": "RC1-02",
            "name": "replayed command rejected",
            "passed": first["decision"] == RC1Decision.ACCEPTED.value
            and replay["decision"] == RC1Decision.REJECTED.value
            and replay["output_energized"] is False,
            "detail": replay["reason"],
        }
    )

    # RC1-03: expired rejected ----------------------------------------------
    stale = build_valid_envelope(rc1, nonce=2, expiry=now - 1)
    res = rc1.receive(stale)
    results.append(
        {
            "test": "RC1-03",
            "name": "expired envelope rejected",
            "passed": res["decision"] == RC1Decision.REJECTED.value
            and res["output_energized"] is False,
            "detail": res["reason"],
        }
    )

    # RC1-04: application-processor bypass attempt ---------------------------
    rc1.output_energized = True  # pretend prior accepted command energized it
    try:
        rc1.bypass_output(origin="application_processor")
        bypass_raised = False
    except BypassAttempt:
        bypass_raised = True
    results.append(
        {
            "test": "RC1-04",
            "name": "AP bypass attempt raises BypassAttempt, energizes nothing",
            "passed": bypass_raised and rc1.output_energized is False,
            "detail": "BypassAttempt raised" if bypass_raised else "no exception — FAILURE",
        }
    )

    return results
