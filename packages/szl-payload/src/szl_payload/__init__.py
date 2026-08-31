"""szl-payload — deterministic SZL master-payload builder with hard compile gates.

Doctrine invariants:

* ``sections/`` is the source of truth; ``dist/`` is derived and is never
  hand-edited.
* The payload body carries no timestamps and no randomness — build time lives
  only in the export receipt, which is what makes the idempotency proof
  (build → copy → rebuild → byte-identical diff) possible.
* UNKNOWN is never PASS.
"""

__version__ = "14.0.0"

__all__ = ["__version__"]
