# Weekly Standards Watch Record — 2026-11-23

Watcher scope: draft-sato-soos-gar, draft-piehl-agent-rule-provenance,
draft-sharif-agent-audit-trail, draft-mw-spice-inference-chain; new drafts
covering agent memory provenance or agent audit (Memory Covenant gap).

## Findings

**Tracked drafts**

- [draft-sharif-agent-audit-trail](https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/) — **TWO new revisions this week**: -10 (2026-11-17, recording/authority independence hardened to MUST at L2+, "an agent cannot attest to its own authority") and -11 (2026-11-21, new §8.5 Completeness Statements + §14.7 False Completeness Claims — falsifiable absence semantics). Full diffs verified from downloaded texts. Still individual, no WG. SZL's four asks all remain open. → [SZL position updated against -11](2026-11-23-aat-11.md).
- [draft-sato-soos-gar](https://datatracker.ietf.org/doc/draft-sato-soos-gar/) — **unchanged at -08** (2026-09-07, verified via datatracker API). Expires 2027-03-07. No filing.
- [draft-piehl-agent-rule-provenance](https://datatracker.ietf.org/doc/html/draft-piehl-agent-rule-provenance-00) — **unchanged at -00** (2026-10-11). SZL position already filed (2026-11-17). Standing observation: it profiles sharif-06 while AAT is now at -11; watch for a piehl -01 rebaseline.
- [draft-mw-spice-inference-chain](https://datatracker.ietf.org/doc/draft-mw-spice-inference-chain/) — **still -00, expired** (2026-09-19; no -01 posted; verified via datatracker API). AFiR TEE-free profile also unchanged. Disposition unchanged: track for revival; the RATS lane is picking up the inference-receipt idea separately (see adjacent drafts).

**AUDIT WG / BoF — material status changes**

- **The AUDIT BoF was held at IETF 127.** Post-BoF, the chairs (Yaroslav Rosomakho, Orie) **closed audit@ietf.org until December 3** ("the mailing list will be closed to messages for the next two weeks"), after which it reopens "focused specifically on issues raised during the BoF, with the goal of preparing for a potential **second BoF, subject to IESG approval**" ([closure message](https://mailarchive.ietf.org/arch/msg/audit/ISQ2xryc--mkqotIhif4aJN1c8o), 2026-11-19). **SZL engagement window = Dec 3; position material is ready.**
- Pre-closure list activity this cycle: "Before a second BoF: what's left for a protocol" thread (2026-11-17+), draft-ehstand-oversight-acts-00 (kinds of human act in audit records), draft-stafordtituss-agentic-mandate-evidence-00 (revocation between invocation and effect — revocation-race convergence with the Covenant's deny-dominance). No DSSE/tamper-evidence/membership debate targeting SZL's four asks this cycle.
- **[draft-gilda-audit-agent-audit-record](https://datatracker.ietf.org/doc/draft-gilda-audit-agent-audit-record/) — NEW -04 (2026-11-19), a major revision** (198,134 → 270,006 bytes; sha256 c5d0b746… → 55929943…). The AUDIT-WG data-model candidate now defines each record **normatively as an in-toto Statement inside a DSSE envelope**: byte-for-byte `_type` check against `https://in-toto.io/Statement/v1` (§4.8, X4/X5 vetest vectors), DSSE PAE over RFC 8785 canonical bytes, **offline** verification of the envelope signature and each anchor (§4.6/4.7), and new §4.9 "Sets of records" (a JSON `records` array of DSSE envelopes carried exactly as signed; fail-closed malformed-set rules; the set itself "adds no signature and asserts nothing of its own"). **This adopts SZL standing positions #1 (envelopes) and #3 (offline verification) at the format level** — the first tracked draft to do so normatively. Open gaps SZL should raise at the second BoF: no set-level chain digest / signed Merkle checkpoint / completeness statement over a set (§4.9 is deliberately unsigned), and no memory-governance event class. [SZL position filed on -04](2026-11-23-gilda-04.md). The end-to-end full-text read was completed before filing, per standing doctrine: §1–§10, Appendix A and Appendix C in full, Appendix B read as the vector index checked against the §4–§6 rules that define its rows; diff reviewed in full (4,098 changed lines); Document History and the author’s address (sankalp.gilda@gmail.com) captured for the outbound comment, which is drafted and send-gated on owner go. **Filed before Dec 3.**
- **Correction of the 2026-11-17 record:** that record said draft-kuehlewind-audit-architecture was at -00 expiring 2026-11-19. The datatracker API shows it **at -01 (2026-09-07)** — the prior record was stale. -01 verified current this cycle; still the BoF-proponents' architecture draft (Kühlewind/Ericsson lane).

**Memory-governance gap (Memory Covenant lane)** — no new positions to file this cycle; landscape unchanged since 2026-11-17 except above. khandelwal -02 (2026-10-17), infantado -00 (2026-07-19, expires 2027-01-19), saihm -00, maintainer-1f916 -01 all unchanged (API-verified). The gap remains: **no draft yet makes memory writes/recalls first-class auditable, envelope-carried events.**

**New adjacent drafts tracked this cycle** (datatracker API-verified):
- [draft-noa-scitt-ai-agent-receipt](https://datatracker.ietf.org/doc/html/draft-noa-scitt-ai-agent-receipt) (-01) — AI-agent receipts in SCITT; directly in SZL's envelope+transparency lane.
- [draft-tsyrulnikov-rats-attested-inference-receipt](https://datatracker.ietf.org/doc/draft-tsyrulnikov-rats-attested-inference-receipt/) (-02) — inference receipts in RATS; the non-OAuth lane to what SPICE inference-chain wanted, worth a position if revived.
- [draft-ehstand-oversight-acts](https://datatracker.ietf.org/doc/html/draft-ehstand-oversight-acts-00) (-00) and [draft-stafordtituss-agentic-mandate-evidence](https://datatracker.ietf.org/doc/html/draft-stafordtituss-agentic-mandate-evidence-00) (-00) — discussed on audit@ pre-closure.

**Honest correction — SZL's own draft.** `draft-lutar-governed-action-receipt-00` is **not registered with the IETF datatracker** (verified 2026-11-23: no hit by name, by `name__contains=governed|receipt|lutar`, or by title; no person record for "Lutar"). It exists as a Zenodo publication ([DOI 10.5281/zenodo.22217725](https://doi.org/10.5281/zenodo.22217725), "Governed Action Receipt (GAR): A Canonical, Verifiable Record of Policy-Governed Actions"). The positions README said "individual I-D" — it has been corrected here and in the README. Two owner actions follow:
1. **Submit the draft through datatracker's I-D submission tool** (with the required boilerplate) if SZL wants it citable to WG discussion before the second BoF.
2. **Rename or de-collide the acronym**: both `draft-sato-soos-gar` (Governance Audit Record) and SZL's Governed Action Receipt abbreviate to "GAR" in the same agent-audit space; SZL should adopt a disambiguating short name (e.g., "GARd" or "action receipt") in filings and, on datatracker submission, expect the RFC Editor to require it.

## Actions this cycle

1. AAT position updated against -11 (full-diff verification; support reaffirmed; four asks tracked open). Filed with this record.
2. Watch record refreshed with two-revision AAT analysis, gilda-04 analysis, AUDIT BoF/list-closure status, new adjacent drafts, and the kuehlewind -01 correction.
3. Outbound comments: the AAT-11 comment was sent to its author (owner-approved, 2026-11-23, direct mail; audit@ietf.org closed until 2026-12-03). The gilda-04 author comment (R1–R3) is drafted and send-gated on owner go for the same window or earlier.
4. SZL position on gilda-04 filed after the end-to-end read of the full 270,006-byte text: [2026-11-23-gilda-04.md](2026-11-23-gilda-04.md).

## Byte evidence (downloaded this cycle)

- `aat-09.txt` 151,557 B sha256 4728ea78883abcf8c50629acd58f737e614d0a821e6516cbb1651d3b26532dd1
- `aat-10.txt` 152,956 B sha256 f7e67601b29ffd42194e0aa4b955e09b1255df5010238d32ac03a25cda67e7d1
- `aat-11.txt` 157,323 B sha256 377ed33392a8657f936a9bf13dbaaa5efb6bacbabcd8a0d62600248210d5e902
- `gilda-03.txt` 198,134 B sha256 c5d0b74686b62b5d1fd954b2dae0cf02b402c87a06efa6fc82abf8fa847ed786
- `gilda-04.txt` 270,006 B sha256 5592994311a3db303405eacebcb203f589b7aa083d81bcdb291a3a78d4adbde6
