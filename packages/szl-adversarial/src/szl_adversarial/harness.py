"""The execution engine: run every registered attack in isolation, report honestly.

Two invariants define an honest harness:

1. **Isolation.** Every attack gets a freshly built fixture (new temp dir,
   new org keypair, new 7-entry chain, new envelope) via the injected
   *ctx_factory*. No attack may inherit another attack's mutilations — a
   "blocked" that only happened because a previous attack already broke the
   fixture proves nothing.

2. **A crash is a finding.** If an attack makes the *verifier* throw, the
   verifier has a robustness bug — malformed input should return findings,
   not stack traces. The harness therefore converts any uncaught exception
   from an attack function into a ``blocked=False`` result whose detail is
   ``verifier crashed``, rather than dying itself. The run continues; the
   report shows the crash as a BROKEN row.

A run **passes** iff every non-limitation attack was blocked.
"""

from __future__ import annotations

import shutil
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field

from .attacks import ALL_ATTACKS, AttackContext, AttackFn, AttackResult, make_context

__all__ = ["HarnessResult", "run_all"]


@dataclass
class HarnessResult:
    """Aggregate verdict of one full harness run.

    ``passed`` is True iff every result with ``limitation=False`` is blocked.
    ``warnings`` lists the documented-limitation attacks (WARN rows) so the
    caller can print them loudly instead of letting them hide in the table.
    """

    results: list[AttackResult]
    passed: bool
    total: int
    warnings: list[str] = field(default_factory=list)
    started_at_unix: float = 0.0
    duration_seconds: float = 0.0

    @property
    def blocked_count(self) -> int:
        return sum(1 for r in self.results if r.blocked)

    @property
    def limitation_count(self) -> int:
        return sum(1 for r in self.results if r.limitation and not r.blocked)

    @property
    def broken(self) -> list[AttackResult]:
        """The attacks that WON — the honest failure list."""
        return [r for r in self.results if not r.blocked and not r.limitation]

    @property
    def non_limitation_total(self) -> int:
        return sum(1 for r in self.results if not r.limitation)

    def verdict_line(self) -> str:
        """The one-sentence public verdict of this run."""
        if self.passed:
            return (
                f"receipt chain resisted {self.blocked_count}/"
                f"{self.non_limitation_total} non-limitation attacks"
            )
        failures = "; ".join(f"{r.name} ({r.category}): {r.detail}" for r in self.broken)
        return f"receipt chain FAILED: {len(self.broken)} attack(s) succeeded — {failures}"

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "total": self.total,
            "blocked": self.blocked_count,
            "broken": [r.name for r in self.broken],
            "limitations_documented": self.limitation_count,
            "warnings": self.warnings,
            "verdict": self.verdict_line(),
            "started_at_unix": self.started_at_unix,
            "duration_seconds": self.duration_seconds,
            "results": [r.to_dict() for r in self.results],
        }


def run_all(
    ctx_factory: Callable[[], AttackContext] = make_context,
    attacks: list[AttackFn] | None = None,
    *,
    cleanup: bool = True,
) -> HarnessResult:
    """Execute every registered attack against its own fresh fixture.

    ``ctx_factory`` is injectable so tests (and future harness variants) can
    pin a fixture directory or substitute a weakened environment — e.g. a
    deliberately weak verifier proves the harness reports failure rather than
    vacuously passing.
    """
    battery = list(ALL_ATTACKS if attacks is None else attacks)
    results: list[AttackResult] = []
    warnings: list[str] = []
    started = time.time()

    for attack_fn in battery:
        ctx = ctx_factory()
        try:
            result = attack_fn(ctx)
        except Exception as exc:  # noqa: BLE001 — a crash is a finding, not an exit
            result = AttackResult(
                name=getattr(attack_fn, "__name__", repr(attack_fn)).removeprefix("attack_"),
                category="CRASH",
                blocked=False,
                detail=(f"verifier crashed under attack: {type(exc).__name__}: {exc}"),
                evidence={
                    "exception": type(exc).__name__,
                    "traceback": traceback.format_exc(limit=8),
                },
            )
        finally:
            if cleanup:
                shutil.rmtree(ctx.workdir, ignore_errors=True)
        results.append(result)
        if result.limitation and not result.blocked:
            warnings.append(f"WARN: {result.name}: {result.detail}")

    finished = time.time()
    passed = all(r.blocked or r.limitation for r in results)
    return HarnessResult(
        results=results,
        passed=passed,
        total=len(results),
        warnings=warnings,
        started_at_unix=started,
        duration_seconds=finished - started,
    )
