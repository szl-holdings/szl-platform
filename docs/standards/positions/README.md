# SZL Positions on External Standards Drafts

Dated, citable position statements filed by SZL Holdings on third-party
standards drafts in the agent-audit / agent-memory space. Each position is
authored against the specific revision named in its filename and linked to
the SZL artifacts that realize it in running code. Every position below was
verified against the full draft text before filing.

## Standing positions (advocated on every audit-record or agent-memory format proposal)

1. **DSSE-style envelopes.** Audit records and memory events should be
   wrapped as detached-signature envelopes (RFC 9052/COSE-compatible,
   DSSE-style) so a verifier checks the exact bytes signed — never a
   re-serialization.
2. **Chain digests.** Each record carries the digest of its predecessor;
   logs publish periodic signed Merkle checkpoints (RFC 6962-style signed
   tree heads) for efficient tamper-evidence.
3. **Offline verification.** A verifier or regulator MUST be able to verify
   exported artifacts with no network access to the producing system.
4. **Memory governance.** Writes to and recalls from persistent agent memory
   are first-class audit events (the Memory Covenant position — the gap no
   current audit draft covers normatively).

## Index

| Date | Draft | Position |
|---|---|---|
| 2026-11-17 | [draft-sharif-agent-audit-trail-09](2026-11-17-aat-09.md) | Support — convergence with standing positions 1–3 acknowledged; extensions requested |
| 2026-11-17 | [draft-infantado-agent-memory-architecture-00](2026-11-17-infantado-agent-memory-architecture-00.md) | Support with extensions (integrity currently optional per 8.7/15.6) |
| 2026-11-17 | [draft-piehl-agent-rule-provenance-00](2026-11-17-piehl-agent-rule-provenance-00.md) | Support — rule layer realizes standing positions 1–3; memory-governance extension requested |
| 2026-11-17 | [Proposed AUDIT WG](2026-11-17-audit-wg-note.md) | Charter-shaping input |
| 2026-11-17 | [Weekly watch record](2026-11-17-watch-record.md) | Landscape snapshot |
| 2026-11-23 | [draft-sharif-agent-audit-trail-11](2026-11-23-aat-11.md) | Support reaffirmed — -10/-11 diffs verified; four requested extensions all still open |
| 2026-11-23 | [Weekly watch record](2026-11-23-watch-record.md) | AUDIT BoF held at IETF 127; list closed until Dec 3; gilda-04 adopts DSSE envelopes normatively |

## Realizing artifacts

- Governed Action Receipt (GAR) draft — **Zenodo-published only, not
  registered with the IETF datatracker as of 2026-11-23**
  ([DOI 10.5281/zenodo.22217725](https://doi.org/10.5281/zenodo.22217725));
  datatracker submission and an acronym de-collision (vs draft-sato-soos-gar,
  Governance Audit Record) are open owner actions.
- [Memory Covenant spec](https://github.com/szl-holdings/szl-frontier/tree/main/covenant-spec)
- governed-receipt-spec + `szl-receipt-dsse` reference implementation
- khipu-consensus BFT witness countersigning; szl-eclipse mutation-tested
  verifiers
