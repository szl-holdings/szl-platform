# Weekly Standards Watch Record — 2026-11-17

Watcher scope: draft-sato-soos-gar, draft-piehl-agent-rule-provenance,
draft-sharif-agent-audit-trail, draft-mw-spice-inference-chain; new drafts
covering agent memory provenance or agent audit (Memory Covenant gap).

## Findings

**Tracked drafts**

- [draft-sato-soos-gar](https://datatracker.ietf.org/doc/draft-sato-soos-gar/) — **unchanged at -08 (2026-09-07)**. GAR is now framed as a SCITT application (RFC 9943) with Authority Lifecycle Events and a tamper-evident event log; SZL's governed-action-receipt draft already composes with SCITT.
- [draft-piehl-agent-rule-provenance](https://datatracker.ietf.org/doc/html/draft-piehl-agent-rule-provenance-00) — **-00 published 2026-10-11** (first sighting this cycle). Rule-provenance lineage for autonomous-agent audit records; individual, Experimental. Position filing deferred to next cycle unless owner directs sooner.
- [draft-sharif-agent-audit-trail](https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/) — **-09 (2026-10-26)**, three revisions since late September, still individual, no WG. → [SZL position filed](2026-11-17-aat-09.md).
- [draft-mw-spice-inference-chain](https://datatracker.ietf.org/doc/draft-mw-spice-inference-chain/) — **-00, now EXPIRED** (no -01 posted). TEE-free post-quantum profile appeared: [draft-rotzin-spice-afir-profile](https://datatracker.ietf.org/doc/draft-rotzin-spice-afir-profile/). Offline-verification angle live; SZL position deferred to next cycle.

**Memory-governance gap filling fast** (SZL Memory Covenant targets exactly this):

- [draft-infantado-agent-memory-architecture-00](https://datatracker.ietf.org/doc/html/draft-infantado-agent-memory-architecture-00) (2026-07-19) — typed Memory Objects, provenance, append-only Event Ledger. → [SZL position filed](2026-11-17-infantado-agent-memory-architecture-00.md).
- [draft-saihm-memory-protocol-00](https://datatracker.ietf.org/doc/html/draft-saihm-memory-protocol-00) (2026-05-18) — sovereign memory, chain anchoring, GDPR erasure. Tracking only.
- [The Agent Record](https://www.ietf.org/archive/id/draft-maintainer-1f916-agent-record-01.html) (-01) — witness-countersigned Merkle event logs including memory integrity; converges with Covenant approach. Tracking.
- [draft-khandelwal-bmwg-agent-memory-integrity](https://datatracker.ietf.org/doc/html/draft-khandelwal-bmwg-agent-memory-integrity-02) — benchmarking method for memory-at-rest integrity (-02). Tracking.
- [draft-gilda-audit-agent-audit-record-03](https://datatracker.ietf.org/doc/draft-gilda-audit-agent-audit-record/) — offered as the data model for a **proposed AUDIT working group**; status signal for the whole lane. → [SZL charter input filed](2026-11-17-audit-wg-note.md).

**Mailing-list debate:** no substantive list discussion of tamper-evidence, DSSE envelopes, hash-chaining, or memory governance on these drafts surfaced this cycle.

## Actions this cycle

1. AAT-09 position filed (support with required changes).
2. infantado-agent-memory-architecture-00 position filed (support with extensions).
3. AUDIT-WG charter-shaping input filed.
4. GAR and SPICE lanes: no filing; unchanged/expired respectively.

## Post-filing correction (2026-11-17, same day)

Full-text review of both drafts (downloaded and grepped locally) corrected
the initial positions before any outbound comment was sent:

- **AAT -09** already contains mandatory tamper-evident chaining (JCS/RFC
  8785 + prev_hash, Section 6), a signature envelope with hybrid PQ mode
  (6.2), optional RFC 6962 Merkle batch anchoring (6.4), graded recording
  independence (Section 5: self-recording only L0/L1), SCITT anchoring
  (MAY), and reference implementations with offline chain verification.
  SZL's earlier "required changes" are retired and the convergence recorded;
  remaining asks are normative offline verification, level-tied anchoring
  strength, an envelope-carriage profile, and the memory-governance
  extension. The IAM Insights self-attestation critique is partially
  addressed by Section 5's graded recording independence.
- **PAMSPEC (infantado) -00** explicitly does NOT mandate a cryptographic
  integrity mechanism (8.7, 15.6: "may be used ... does not mandate"), and
  Section 16.3 already resolves erasure-vs-append-only via content-free
  tombstones. Position retargeted at the PAMSPEC-Ledger conformance profile
  (Section 18) as the vehicle for mandating envelopes, chain digests,
  checkpoints, and offline verification.
