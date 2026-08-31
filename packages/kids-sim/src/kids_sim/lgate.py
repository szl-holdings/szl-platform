"""KIDS v0.1 LGATE (Λ-gate): single-cycle policy gate in the datapath.

Before any privileged command executes, LGATE_CHECK(command_digest,
policy_digest) evaluates a PolicyRule set — allowed opcodes, bound
ranges, required receipts — and returns ALLOW or DENY.

The ISA defines LGATE evaluation as a SINGLE CYCLE: the performance model
in perf.py charges exactly 1 cycle per check. NOTE: single-cycle is a
SPEC TARGET to be proven in RTL (pipelined comparator against a fused
policy digest); the golden simulator fixes only the semantics, not the
microarchitecture.

Fail closed: DENY => the command does not execute, an event is logged as
DENIED with a reason, and architectural state is unchanged.
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field
from typing import Any

LGATE_POLICY_DOMAIN: bytes = b"SZL-KIDS-POLICY-V1"


class Decision(enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class PolicyRule:
    """One policy rule.

    allowed_opcodes: opcode names this policy permits (None = none).
    bounds: per-field inclusive (min, max) ranges checked against the
        command's numeric fields (e.g. {"bytes": (0, 65536)}).
    required_receipts: number of receipts that must already exist in the
        receipt chain before a privileged command may run.
    """

    allowed_opcodes: frozenset[str] = frozenset()
    bounds: dict[str, tuple[int, int]] = field(default_factory=dict)
    required_receipts: int = 0

    def digest(self) -> bytes:
        """Policy digest bound into LGATE_CHECK and the receipt chain."""
        canon = (
            sorted(self.allowed_opcodes),
            sorted((k, v[0], v[1]) for k, v in self.bounds.items()),
            self.required_receipts,
        )
        return hashlib.sha3_256(LGATE_POLICY_DOMAIN + repr(canon).encode()).digest()


def command_digest(command: dict[str, Any]) -> bytes:
    """Digest of the canonical command encoding."""
    import json

    c = json.dumps(command, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha3_256(b"SZL-KIDS-CMD-V1" + c).digest()


@dataclass(frozen=True)
class LGateVerdict:
    decision: Decision
    reason: str
    cycles: int = 1  # single-cycle spec target (see module docstring)


class LGate:
    """The policy gate. Pure function of (policy, command, receipt count)."""

    def __init__(self, policy: PolicyRule):
        self.policy = policy
        self.denied_log: list[dict[str, Any]] = []

    def check(self, command: dict[str, Any], receipt_count: int) -> LGateVerdict:
        op = command.get("op", "<none>")
        if op not in self.policy.allowed_opcodes:
            return self._deny(command, f"opcode {op} not in policy allow-list")
        for field_name, (lo, hi) in self.policy.bounds.items():
            v = command.get(field_name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue  # bound applies only where the field exists numerically
            if not (lo <= v <= hi):
                return self._deny(command, f"field {field_name}={v} outside bound [{lo}, {hi}]")
        if receipt_count < self.policy.required_receipts:
            return self._deny(
                command, f"requires {self.policy.required_receipts} receipts, have {receipt_count}"
            )
        return LGateVerdict(Decision.ALLOW, "ok")

    def _deny(self, command: dict[str, Any], reason: str) -> LGateVerdict:
        self.denied_log.append({"command": command, "reason": reason})
        return LGateVerdict(Decision.DENY, reason)
