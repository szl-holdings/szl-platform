# SZL Position - draft-piehl-agent-rule-provenance-00

**Date:** 2026-11-17 (filed after full-text verification of -00)
**Draft:** [Rule Provenance for Autonomous AI Agent Audit Records](https://datatracker.ietf.org/doc/draft-piehl-agent-rule-provenance/) — P. Piehl, individual submission, revision -00 (2026-10-11), Experimental; profiles [SHARIF] (Agent Audit Trail) revision -06.
**Position:** SUPPORT — the strongest convergence in the current watch set; extensions requested.

## Convergence with SZL's standing positions

The profile adopts, in normative language, nearly every mechanism SZL
advocates for audit formats — and applies them to *rules*, the layer no
other draft in the watch set covers:

- **Chain digests, JCS end-to-end** — all JSON is I-JSON and JCS
  (RFC 8785)-canonical; `rule_hash`, `snapshot_hash`, `request_digest`,
  salted `parameters_hash`, receipts and record hashes are specified
  byte-exactly (Sections 2, 4.1, 5, 6.2, 7.2).
- **Signed Merkle receipts + REQUIRED anchoring** — recorder receipts carry
  RFC 9162 tree positions with inclusion/consistency proofs (7.2), and
  external anchoring of every consequential and policy record within 24 h
  is REQUIRED (9), with `recorder_equivocation` detection — stronger than
  AAT -09's optional anchoring.
- **Fail-closed posture** — for consequential actions `unavailable` is a
  denial whatever the default posture (6.1); degraded mode is opt-in,
  daily-capped, and money-moving actions (`rp_synchronous`) never run
  without a receipt (3.1, 7.4); the execution gate re-checks validity,
  snapshot and single-use before any side effect (7.3).
- **Denial-dominant precedence** — deny > require_approval > limit >
  allow (4.5): an approval can never lift an active deny; only a
  separately recorded human override can, visibly, naming the entries it
  overrode (6.3). This is the operational form of SZL's machine-checked
  deny-by-default monotonicity lemma.
- **Anti-retroaction** — rule versions must be receipted before reliance,
  with `retroactive_rule` and void-version checks (4.2, 7.1); policy
  sessions reject second chains (3.2); snapshots are recomputable by
  anyone from recorder-held rule records (5).
- **Erasure reconciled with append-only, honestly** — keyed-hash personal
  data references, recorded pseudonym-mapping erasure, and
  `evidence_deleted` vs `tombstoned` verdicts preserve evidence (3.4, 13).
- **Honest verification taxonomy** — named four-class results, an explicit
  `unverifiable` outcome, and a MUST-NOT-overclaim rule ("even a
  'verified' session is not proof that the agent obeyed every rule")
  (10, 11). This matches SZL's honesty doctrine better than any draft we
  have reviewed.

## Requested extensions

1. **Normative offline verification.** Section 10 works from artifacts
   (records, receipts, anchors, policy-head statements, recorder
   statements/keys); say so normatively — verification MUST NOT require
   live access to the operator's or the recorder's systems.
2. **Base-revision alignment.** The profile pins `rp_base "sharif-06"`
   while AAT is at -09 (mandatory JCS/prev_hash chaining, hybrid-PQ
   envelope, 6.2). Ask: a timeline for an rp-01 against sharif-09, and
   that the evaluator-signature path carry the same hybrid-PQ option so
   the profile is not stranded on classical-only algorithms.
3. **Anchoring cadence tied to criticality.** 24 h is a coarse ceiling for
   money-moving actions; signed tree heads for `rp_synchronous` classes
   SHOULD be published at sub-hourly or per-epoch cadence.
4. **Memory-governance extension.** Rules are governed end-to-end; agent
   *memory* is untouched. The same machinery — versions, receipts,
   recomputable snapshots, anchoring, tombstone discipline — extends to
   memory writes/recalls as first-class audit events (the Memory
   Covenant position).

## Realizing SZL artifacts + implementation offer

The draft reports no known implementations and, as an Experimental
submission, explicitly invites deployment reports (Sections 1, 12). SZL
offers to be a first implementer and testbed: a governed-AI estate with
`szl-receipt-dsse` envelopes, khipu-consensus BFT witness countersigning
(3-of-4), szl-eclipse mutation-tested verifiers, and Lean-verified policy
monotonicity — able to report receipt latency, timing-check false
positives, degraded-mode behavior, and recorder-independence experience
against Section 8.1's criteria.

- `draft-lutar-governed-action-receipt-00` — SZL's individual I-D
  ([DOI 10.5281/zenodo.22217725](https://doi.org/10.5281/zenodo.22217725))
- [Memory Covenant spec](https://github.com/szl-holdings/szl-frontier/tree/main/covenant-spec)
- governed-receipt-spec + `szl-receipt-dsse` reference implementation
