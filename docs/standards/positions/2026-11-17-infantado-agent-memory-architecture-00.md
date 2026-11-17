# SZL Position — draft-infantado-agent-memory-architecture-00

**Date:** 2026-11-17
**Draft:** [Architecture and Data Model for Persistent Memory in Agentic Systems](https://datatracker.ietf.org/doc/html/draft-infantado-agent-memory-architecture-00) — R. M. Infantado (Ed.), R. Leroux, -00 (2026-07-19), Informational, independent.
**Position:** SUPPORT WITH EXTENSIONS.

## What the draft gets right

The core separation — persistent, addressable, governed memory vs. per-request
context — matches the model the SZL Memory Covenant has operated in production
since 2026: Memory Scope isolation, typed and versioned Memory Objects,
machine-readable provenance, and an append-only Event Ledger as the history of
record. This is, to our knowledge, the first IETF-track draft to state that
memory itself is a governed object. SZL endorses that framing.

## Required extensions (the four standing SZL positions)

1. **DSSE-style envelopes** for Event Ledger entries — provenance that is
   machine-readable but unsigned is paperwork; it cannot survive dispute.
2. **Chain digests** on the Event Ledger with periodic signed Merkle
   checkpoints, so history is verifiably append-only against the operator.
3. **Offline verification** of exported ledgers, objects, and provenance.
4. **Governed memory semantics**: deny-by-default policy enforcement with a
   monotonicity property (an approval MUST NOT lift a hard deny —
   Lean-verified in the Covenant as of 2026-11) and witness countersigning
   for memory-write receipts.

## Interaction to resolve

Right-to-erasure (GDPR Art. 17) vs. append-only history: the Covenant's
deployed estate documents erase semantics compatible with hash-chained logs
([a11oy GDPR erase runbook](https://github.com/szl-holdings/a11oy/blob/main/docs/GDPR_ERASE.md)).
The draft should say how erasure and append-only history coexist.

## Offer

SZL offers the [Memory Covenant spec](https://github.com/szl-holdings/szl-frontier/tree/main/covenant-spec)
and its running implementation as a reference realization of this
architecture, and `draft-lutar-governed-action-receipt-00` as the
receipt/envelope layer it composes with.
