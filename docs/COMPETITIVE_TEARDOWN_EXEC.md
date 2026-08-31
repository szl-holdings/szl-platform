# SZL Holdings — Competitive Teardown: Executive Summary

*2026-08-31. Full version: `COMPETITIVE_TEARDOWN.md`. Every number below is sourced inline there.*

**Verdict.** In all four surfaces scanned, tamper-evident per-decision receipts are unoccupied — simultaneously, by everyone, with dated evidence:

1. **AI governance** (Credo AI, OneTrust, Trustible, Saidot, Holistic AI, IBM, ServiceNow, ModelOp,
   ValidMind, Fairly/Asenion): none ships hash-chained/signed decision records. Closest: ServiceNow's
   containment-scope "immutable audit trail" and Credo's per-use-case audit log — operational logs,
   not receipts ([takeaway](../../research/governance_landscape.md), [ServiceNow](https://www.servicenow.com/docs/r/intelligent-experiences/gov-sec-exploring-ai-agent-containment.html?contentId=jzxBt0lbrJ5IwyZqoErLyA), [Credo](https://www.credo.ai/glossary/credo-ai-audit-trail)).
2. **LLM gateways/observability** (LiteLLM, Kong AI, Envoy AI GW, Portkey, OpenRouter, Helicone,
   Langfuse, Braintrust, OpenLLMetry, Phoenix): none of the ten documents a tamper-evident request
   log ([takeaway](../../research/gateway_landscape.md)).
3. **AI silicon + HRoT** (Tenstorrent, Groq, Cerebras, Etched, d-Matrix, Positron, FuriosaAI, NVIDIA
   CC, Intel TDX, AMD SEV-SNP, Caliptra, OpenTitan): no shipping accelerator has per-inference receipts
   or a datapath policy gate; attestation is boot/session-scope; Caliptra's mailbox is control-plane-only
   by spec; the IETF AIR draft is application-layer TEE software, not silicon ([takeaway](../../research/silicon_landscape.md), [Caliptra spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/), [Datatracker](https://datatracker.ietf.org/doc/draft-tsyrulnikov-rats-attested-inference-receipt/)).
4. **C-UAS + maritime** (Anduril, Dedrone/Axon, Fortem, Epirus, Shield AI, AeroVironment, Saildrone,
   Windward, HawkEye 360, Darkhive): nobody publishes tamper-evident engagement logging; Dedrone's
   forensic exports are closest ([takeaway](../../research/cuas_maritime_landscape.md), [brochure](https://sandstormdefence.com/wp-content/uploads/2024/03/Dedrone-DroneTracker-Software-EN.pdf)).

**What we adopt.** Credo's policy-pack UX → `szl-iso42001`; ServiceNow's CMDB-tied inventory → `szl-estate`;
IBM's auto-factsheets → `szl-receipts`; ModelOp's system of record → `szl-claims-api`. Five gateway patterns
(async queue-mediated evidence; explicit fail-open/fail-closed; per-attempt lifecycle hooks; OTel-native
GenAI semconv; canonical payload + correlation ID + object-storage offload) → `szl-evidence-litellm`, a
plugin *into* LiteLLM's ecosystem (57,629 stars, MIT, [repo](https://github.com/BerriAI/litellm)), not an eleventh gateway. Tenstorrent's open-stack GTM,
Caliptra's DICE identity + anti-rollback counters, and OpenTitan as RC1 silicon reference (all Apache-2.0)
→ KIDS v0.1: LGATE policy gate, SHA3-256 receipt engine with domain separation, RC1 hard-partition mailbox,
KV Merkle commitment — golden simulator (`kids-sim`) before RTL.

**Open windows.** JIATF-401 CSO: fixed-price, awards through end of 2028, forensics mandate in the
establishing memo ([DefenseScoop](https://defensescoop.com/2026/02/27/jiatf-401-commercial-solutions-opening-cso-counter-uas/), [memo](https://media.defense.gov/2025/Aug/28/2003790021/-1/-1/0/ESTABLISHMENT-OF-JOINT-INTERAGENCY-TASK-FORCE-401.PDF)). FY26 Release 5 SBIR closes 2026-09-23 12:00 ET; no open topic funds C-UAS assurance — the gap is the signal ([DARPA](https://www.darpa.mil/work-with-us/communities/small-business/sbir-sttr-topics)). CyLab Partners Conference Oct 20–21, 2026 ([CyLab](https://www.cylab.cmu.edu/events/partners_conference/2026/index.html)). EU AI Act Art. 50 is in force; Annex III high-risk lands 2 Dec 2027 ([White & Case](https://www.whitecase.com/insight-alert/eu-ai-omnibus-enters-force-amending-ai-act)).

**What we refuse.** Dashboard-trust governance, "auditable" as an unbacked adjective, closed ISA/compiler
stacks, and conflating boot-scope attestation with inference assurance.

**Honest weaknesses.** Leaders beat us on distribution (Langfuse: 50,000+ companies, [pricing](https://langfuse.com/pricing)), certifications
(Portkey/Braintrust/Traceloop: SOC 2 et al.; SZL: none), deployed fleet (AeroVironment: 1,000+ Titan
units; SZL: zero), and capital (Anduril $11.4B at $61B, [Reuters](https://www.reuters.com/legal/transactional/us-defense-firm-anduril-raises-5-billion-doubling-its-valuation-61-billion-2026-05-13/); SZL unfunded, solo-founder, no price). Receipts
do not fix model quality, latency, legal liability, or the raise — and "receipt cannot lie" stays banned
until the public attack harness survives. Incumbents can close the gap; the defense is speed plus
claiming the receipt-format standard while the IETF draft has no standing.
