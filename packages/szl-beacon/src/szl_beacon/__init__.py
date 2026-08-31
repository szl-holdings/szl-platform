"""szl-beacon — reference implementation of the A11oy Beacon REALITY PROTOCOL.

The software SZL owns for the Beacon edge appliance: the Reality Protocol
state machine, receipt semantics, the policy engine, and signing-infrastructure
semantics (content-addressed, hash-chained events; production signatures via
the szl-receipts DSSE/Ed25519 layer).

HONESTY DOCTRINE (non-negotiable):
  * Unknown / unavailable / unverified states stay EXPLICIT. No fake green.
  * Reality Debt is never auto-resolved; it closes only via explicit
    reconciliation.
  * This package is a REFERENCE IMPLEMENTATION. Zero physical Beacon units
    exist. The RC1 module is a SOFTWARE SIMULATION of the hardware
    governance boundary. Nothing in this package claims otherwise.

Stdlib-only by design: the production canonicalizer is RFC 8785 (JCS) via
szl-receipts; here canonical JSON (sorted keys, no whitespace) is used and
documented as such. Do not claim RFC 8785 conformance for these digests.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
