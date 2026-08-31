"""szl-adversarial — the public attack harness for the SZL receipt chain.

An unattacked security claim is a liability. This package attacks the
estate's *real* receipt core (``szl_receipts``, imported from its public
top-level surface only) with a battery of named attacks — forgery, tamper,
canonicalization drift, chain surgery, naming downgrade, PAE confusion, and
outcome-gate bypass — executes them in isolated fixtures, and publishes the
verdict either way. If you break this, we publish the break: every report
carries a self-receipt binding the report's sha256 to the exact library
version under attack.

Result semantics: an attack is ``BLOCKED`` (defense held), ``BROKEN``
(attack won, or the verifier crashed — a crash is a successful attack), or
``WARN`` (a documented limitation of the security model, e.g. silent tail
truncation without an external anchor — not counted against the run, and
never hidden).
"""

from .attacks import ALL_ATTACKS, AttackContext, AttackFn, AttackResult, make_context
from .harness import HarnessResult, run_all
from .report import render_markdown, verdict_outcome, write_report

__version__ = "1.0.0"

__all__ = [
    "ALL_ATTACKS",
    "AttackContext",
    "AttackFn",
    "AttackResult",
    "HarnessResult",
    "__version__",
    "make_context",
    "render_markdown",
    "run_all",
    "verdict_outcome",
    "write_report",
]
