# SZL Position — draft-infantado-agent-memory-architecture-00

**Date:** 2026-11-17 (revised same day after full-text review)
**Draft:** [Architecture and Data Model for Persistent Memory in Agentic Systems](https://datatracker.ietf.org/doc/html/draft-infantado-agent-memory-architecture-00) (PAMSPEC) — R. M. Infantado (Ed.), R. Leroux, -00 (2026-07-19), Informational, independent.
**Position:** SUPPORT WITH EXTENSIONS.

## What the draft gets right

The core separation — persistent, addressable, governed memory vs.
per-request context, with Memory Scope isolation, typed/versioned Memory
Objects, machine-readable provenance, an append-only Event Ledger, and
non-authoritative Derived Indexes — matches the model the SZL Memory
Covenant has operated in production since 2026. This is, to our knowledge,
the first IETF-track draft to state that memory itself is a governed
object. SZL endorses that framing.

Section 16.3 also correctly resolves the erasure-vs-append-only tension
(immutable operational history separated from prohibited retained content,
content-free tombstones) — the same coexistence our deployed estate
documents ([a11oy GDPR erase runbook](https://github.com/szl-holdings/a11oy/blob/main/docs/GDPR_ERASE.md)).

## The gap: integrity is optional

Sections 8.7 (Integrity Metadata) and 15.6 (Integrity and Tamper Evidence)
explicitly decline to mandate a cryptographic mechanism: "Cryptographic
continuity, signatures, or content hashing **may** be used to make
tampering evident, but this -00 draft does not mandate a particular
cryptographic mechanism." Provenance that is machine-readable but optional
to protect cannot survive dispute — an operator motivated to revise history
is exactly the threat (Section 15.1) that an unsigned ledger does not answer.

## Requested extensions

1. **Mandate a concrete mechanism in the PAMSPEC-Ledger profile.** The
   conformance profiles (Section 18) are the right vehicle: PAMSPEC-Ledger
   SHOULD require DSSE-style envelopes (RFC 9052/COSE-compatible) for Event
   Ledger entries, record-level chain digests, periodic signed Merkle
   checkpoints (RFC 6962-style), and offline verification of exported
   ledgers, objects, and provenance.
2. **Governed memory semantics.** Deny-by-default policy enforcement with
   a monotonicity property — an approval MUST NOT lift a hard deny
   (machine-checked in Lean in the Covenant as of 2026-11) — and witness
   countersigning for memory-write receipts, directly strengthening the
   memory-poisoning section (15.5).
3. **Bind receipts to erasure events.** Erasure (16.3) and redaction are
   themselves memory operations that should leave signed, content-free
   evidence — a tombstone with a receipt, not just a tombstone.

## Offer

SZL offers the [Memory Covenant spec](https://github.com/szl-holdings/szl-frontier/tree/main/covenant-spec)
and its running implementation as a reference realization of this
architecture, and `draft-lutar-governed-action-receipt-00` (individual
I-D, [DOI 10.5281/zenodo.22217725](https://doi.org/10.5281/zenodo.22217725))
as the receipt/envelope layer it composes with. We would welcome
collaboration on the PAMSPEC-Ledger profile.
