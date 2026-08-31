# SZL Holdings — Competitive Teardown: Four Surfaces

*Compiled 2026-08-31. Every competitor fact, funding figure, star count, contract value, and
standards status below comes from the four evidence files in `../../research/`
(`governance_landscape.md`, `gateway_landscape.md`, `silicon_landscape.md`,
`cuas_maritime_landscape.md`), each of which records only values read off pages fetched the
same day; SZL-internal context comes from `../../discovery/fork_findings.md` (§3 KIDS/KHIPU,
§5 estate state, §7 prior art & market) and `../../discovery/brain_digest.md` (project
inventory). Inline URLs are preserved verbatim from those files. `n.a.` = not confirmed from
a fetched source.*

*Written for two readers at once: an investor doing diligence (is the wedge real and
unoccupied?) and an engineer deciding what to build (what do we adopt, what do we refuse,
and where does each pattern land in the `szl-platform` monorepo?).*

---

## 1. TL;DR — the verdict in one paragraph

Across **all four surfaces** we scanned, one capability is uniformly absent: **tamper-evident,
cryptographically verifiable, per-decision receipts**. In AI governance platforms, no vendor
ships hash-chained or signed decision records — the strongest adjacents are ServiceNow's
immutable *containment* audit log and Credo AI's structured per-use-case audit trail, both
operational logs, not cryptographic receipts ([research/governance_landscape.md](../../research/governance_landscape.md)).
In LLM gateways/observability, **none of the ten projects documents a tamper-evident or
immutable request log**; Portkey's enterprise audit logs and Langfuse's S3-first persistence
come closest and neither is tamper-evident ([research/gateway_landscape.md](../../research/gateway_landscape.md)).
In AI silicon, **no shipping accelerator offers per-inference cryptographic receipts or a
policy gate in the compute datapath** — attestation everywhere is boot/session-scope, and the
only per-inference receipt proposal (IETF AIR draft) is application-layer TEE software, not
silicon ([research/silicon_landscape.md](../../research/silicon_landscape.md)).
In C-UAS/maritime, **no entity publishes tamper-evident logging of autonomous engagements** —
Dedrone's forensic-evidence exports are the nearest artifact and are not tamper-evident
([research/cuas_maritime_landscape.md](../../research/cuas_maritime_landscape.md)).
The wedge is unoccupied in four adjacent markets simultaneously. The sections below show the
evidence, what we copy, what we refuse, and what the wedge does *not* fix.

---

## 2. Surface: AI governance platforms

### 2.1 Leaders table (condensed)

| Vendor | Total funding / latest round | Receipts capability | Standards involvement |
|---|---|---|---|
| **Credo AI** | $41.3M per [company blog](https://www.credo.ai/blog/accelerating-global-growth-and-innovation-in-ai-governance-with-21-million-in-new-capital) / $46.8M per [Caplight](https://www.caplight.com/company/credo-ai); latest $21M Series B, 30 Jul 2024 | **Partial** — Audit Trail = "a clear, structured record of every action taken around a specific AI use case"; no signing, hash-chaining, tamper-evidence ([credo.ai glossary](https://www.credo.ai/glossary/credo-ai-audit-trail)) | Participating member, NIST AISIC ([credo.ai](https://www.credo.ai/blog/credo-ai-joins-new-nist-ai-safety-institute-consortium-dedicated-to-trustworthy-ai)) |
| **OneTrust** | $1.144B total; $150M Jul 2023 at $4.5B valuation ([cybercompanyprofiles.com](https://cybercompanyprofiles.com/companies/onetrust)) | **Partial** — "automated evidence and audit outputs"; no cryptographic receipt claims ([onetrust.com](https://www.onetrust.com/solutions/ai-governance/)) | Foundational supporter, IAPP AI Governance Center ([onetrust.com](https://www.onetrust.com/news/onetrust-joins-iapp-ai-governance-center/)) |
| **Trustible** | ~$6.2M; $4.6M seed 10 Jun 2025 ([technical.ly](https://technical.ly/entrepreneurship/trustible-seed-raise-ai-governance-rosslyn/)) | **No** — none found ([technical.ly](https://technical.ly/entrepreneurship/trustible-seed-raise-ai-governance-rosslyn/)) | NIST collaboration per interview ([technical.ly](https://technical.ly/entrepreneurship/trustible-seed-raise-ai-governance-rosslyn/)) |
| **Saidot** | ~$1.84M; €1.75M seed 5 Oct 2023 ([CB Insights](https://www.cbinsights.com/company/saidot), [arcticstartup.com](https://arcticstartup.com/saidot-raises-e1-75m-seed/)) | **No** ([saidot.ai](https://www.saidot.ai/insights/saidot-raises-seed-round-to-grow-its-ai-governance-platform)) | CEO chaired IEEE responsible-AI initiatives ([arcticstartup.com](https://arcticstartup.com/saidot-raises-e1-75m-seed/)) |
| **Holistic AI** | ~$10M; VC round 18 Mar 2024 ([Caplight](https://www.caplight.com/company/holisticai)) | **No** ([mozilla.vc](https://mozilla.vc/mozilla-ventures-invests-in-leading-ai-governance-platform-holistic-ai/)) | Inaugural member, NIST AISIC ([holisticai.com](https://www.holisticai.com/news/holistic-ai-joins-nist-aisic)) |
| **IBM watsonx.governance** | Public (NYSE: IBM) | **Partial** — lifecycle "Factsheets" auto-capture metadata; no tamper-evidence ([ibm.com docs](https://www.ibm.com/docs/en/watsonx/saas?topic=cloud-watsonxgovernance-plans)) | Named AI Alliance partner ([servicenow.com](https://www.servicenow.com/standard/resource-center/white-paper/wp-sn-responsible-genai.html)) |
| **ServiceNow AI Control Tower** | Public (NYSE: NOW); launched 6 May 2025 ([newsroom](https://newsroom.servicenow.com/press-releases/details/2025/ServiceNow-Launches-AI-Control-Tower-a-Centralized-Command-Center-to-Govern-Manage-Secure-and-Realize-Value-From-Any-AI-Agent-Model-and-Workflow/default.aspx)) | **Partial** — kill-switch containment yields "a complete, immutable audit trail" per containment action; not described as cryptographic; scoped to containment, not every decision ([servicenow.com docs](https://www.servicenow.com/docs/r/intelligent-experiences/gov-sec-exploring-ai-agent-containment.html?contentId=jzxBt0lbrJ5IwyZqoErLyA)) | Founding member, AI Alliance with IBM, Meta ([servicenow.com](https://www.servicenow.com/standard/resource-center/white-paper/wp-sn-responsible-genai.html)) |
| **ModelOp** | $16M total; $10M Series B 13 Aug 2024, Baird Capital ([modelop.com](https://www.modelop.com/blog/press-release-modelop-raises-10-million-to-accelerate-innovation-of-its-leading-ai-governance-software)) | **No** ([modelop.com](https://www.modelop.com/blog/press-release-modelop-raises-10-million-to-accelerate-innovation-of-its-leading-ai-governance-software)) | n.a. |
| **ValidMind** | $11.1M total; $8.1M seed 27 Mar 2024, Point72 Ventures ([finsmes.com](https://www.finsmes.com/2024/03/validmind-raises-8-1m-in-seed-funding.html)) | **No** ([validmind.com](https://validmind.com/news/validmind-secures-8-1-million-in-seed-round-funding/)) | n.a. |
| **Fairly AI (now Asenion)** | CAD 1.1M pre-seed + $600K + $1.7M (Apr 2023) + ~$727K (Jun 2026); acquired anch.AI, rebranded Asenion Jun 2025 ([fintech.global](https://fintech.global/2023/04/20/fairly-ai-nets-1-7m-for-risk-management-platform-for-ai/), [asenion.ai](https://asenion.ai/blog/fairly-ai-acquires-anch-ai-to-create-asenion)) | **No** — claims "auditable" governance, no tamper-evident receipts ([fairly.ai](https://www.fairly.ai/about-us)) | *Aligns to* EU AI Act / ISO 42001 / NIST AI RMF / OWASP ([fairly.ai](https://www.fairly.ai/about-us)) |

### 2.2 The gap, stated precisely

The research verdict: *"no vendor in this set ships cryptographic, tamper-evident,
per-decision receipts (hash-chained or signed decision records)"* — the strongest adjacent
capabilities are ServiceNow's containment log and Credo's audit trail, "both operational
logs, not cryptographic receipts" ([governance_landscape.md, Table 1 takeaway](../../research/governance_landscape.md)).
The one standards effort aimed at agent audit trails, IETF `draft-sharif-agent-audit-trail`,
is an individual Internet-Draft at version -01 (19 Aug 2026) that the datatracker states
verbatim is "**not endorsed by the IETF** and has **no formal standing**" and is adopted by no
working group ([IETF Datatracker](https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/)).
The format layer is genuinely unowned.

### 2.3 What we adopt (license-clean), and where it lands

| Pattern we adopt | Source | SZL destination repo/package |
|---|---|---|
| **Policy packs as reviewable data, not code.** Credo's policy packs map EU AI Act / ISO 42001 to controls ([credo.ai](https://www.credo.ai/blog/accelerating-global-growth-and-innovation-in-ai-governance-with-21-million-in-new-capital)); we implement the *idea* as an embedded YAML control corpus — unique IDs, weights, validated at load, diffable line-by-line by a non-programmer. We write our own questionnaire content; nothing is copied. | Credo AI policy-pack UX | **`szl-iso42001`** (free offline ISO/IEC 42001 + EU AI Act Art-50 readiness checker that emits a signed receipt of its own findings; `DISCLAIMER` string ships in every report) |
| **Inventory tied to a system of record.** ServiceNow auto-inventories agents/models/MCP servers tied to the CMDB ([servicenow.com](https://www.servicenow.com/products/ai-control-tower.html)); our analog is two-source enumeration of the GitHub + HF estate that *refuses to say "COMPLETE" unless the two sources agree*, plus per-repo audit files. | ServiceNow AI Control Tower | **`szl-estate`** (`enumerate`, `audit`, `doctor`) |
| **Automatic lifecycle documentation.** IBM's Factsheets capture model metadata automatically across the lifecycle ([ibm.com docs](https://www.ibm.com/docs/en/watsonx/saas?topic=cloud-watsonxgovernance-plans)); we adopt the *automation* but the artifact is a signed, hash-chained `GovernedAction/v1` receipt (RFC 8785 canonical body, DSSE/Ed25519 envelope, in-toto Statement wrap) instead of a database row. | IBM watsonx.governance Factsheets | **`szl-receipts`** (receipt core), surfaced through **`szl-claims-api`** (live claim state) |
| **A "system of record" whose numbers re-compute.** ModelOp sells the governance system of record ([modelop.com](https://www.modelop.com/blog/press-release-modelop-raises-10-million-to-accelerate-innovation-of-its-leading-ai-governance-software)); we adopt the posture but make every published numeric claim re-runnable: `verify-claims` recomputes each claim and opens a `CLAIM_DRIFT` finding on mismatch, exposed live at `GET /api/cps/claims`. | ModelOp | **`szl-claims-api`** (live claims endpoint) backed by **`szl-estate`** (`verify-claims`) |

### 2.4 What we refuse to copy

- **The dashboard-trust model.** Every vendor above ultimately asks the buyer to trust a
  hosted dashboard reading a mutable operational log. Credo prices enterprise-only, RFP
  benchmarks in the low six figures ([aicompliancevendors.com](https://aicompliancevendors.com/blog/onetrust-vs-credo-ai-vs-fairly-ai-vs-saidot));
  OneTrust's AI Governance is a custom quote on top of a $10K minimum annual deal
  ([aicompliancevendors.com](https://aicompliancevendors.com/blog/onetrust-vs-credo-ai-vs-fairly-ai-vs-saidot)).
  The buyer cannot independently verify any row. We refuse this: `szl-receipts` is a few
  hundred lines, offline-verifiable, and the attack harness (`szl-adversarial`) is public.
  If the verifier fails on the auditor's machine, that failure is the output.
- **"Auditable" as an adjective.** Fairly/Asenion claims "auditable" governance with no
  tamper-evidence mechanism behind it ([fairly.ai](https://www.fairly.ai/about-us)).
  We ban the equivalent adjectives in our own copy (`lint/banned_claims.txt` in
  `szl-payload`).

### 2.5 Regulatory clock (why the gap matters now)

- **EU AI Act Article 50 (transparency) applies from 2 Aug 2026** — unchanged by the omnibus
  ([Tempreon](https://tempreon.com/blog/eu-ai-act-high-risk-deadline-moved), [Cooley](https://www.cooley.com/news/insight/2026/2026-08-03-eu-ai-act-transparency-obligations-take-effect-2-august-2026), [EC](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)); machine-readable marking for pre-market GenAI gets relief to 2 Dec 2026 ([Morgan Lewis](https://www.morganlewis.com/pubs/2026/06/eu-approves-delays-and-other-amendments-to-certain-eu-ai-act-obligations-what-businesses-should-know)).
- **Annex III high-risk obligations moved to 2 Dec 2027** and Annex I embedded to 2 Aug 2028
  under Regulation (EU) 2026/1744, in force 27 Jul 2026 ([White & Case](https://www.whitecase.com/insight-alert/eu-ai-omnibus-enters-force-amending-ai-act), [Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/)). Demand for evidence tooling is live now; the conformity-assessment wave is late 2027 — runway, not reprieve.
- **ISO/IEC 42001 certification costs price out most orgs:** audit fees $7K–20K with
  $3.5K–9K/yr surveillance ([Vanta](https://www.vanta.com/collection/iso-42001/iso-42001-certification-cost)); certification-body fees €15K–60K plus €60K–300K internal effort, 3–6 months typical ([Modulos](https://www.modulos.ai/blog/iso-42001-certification-guide/)). This is exactly the gap `szl-iso42001` attacks: a free, offline readiness checker whose output is itself a signed receipt — the checker dogfoods the claim.

---

## 3. Surface: LLM gateways & inference observability

### 3.1 Leaders table (condensed)

| Project | License | GitHub stars (live, 2026-08-31) | Hook architecture | Tamper-evident log? |
|---|---|---|---|---|
| **LiteLLM** (BerriAI) | MIT; `enterprise/` dir separate ([LICENSE](https://raw.githubusercontent.com/BerriAI/litellm/main/LICENSE)) | 57,629 ([repo](https://github.com/BerriAI/litellm)) | `CustomLogger` hooks incl. per-attempt deployment hooks firing once per real call incl. retries/fallbacks ([docs](https://docs.litellm.ai/docs/observability/custom_callback)) | **No** — `StandardLoggingPayload` to S3/GCS/SQS/OTel; no tamper-evidence documented ([docs](https://docs.litellm.ai/docs/proxy/logging)) |
| **Kong AI Gateway** | Apache-2.0 ([LICENSE](https://raw.githubusercontent.com/Kong/kong/master/LICENSE)) | 44,060 ([repo](https://github.com/Kong/kong)) | Standard Kong plugin chain; dedicated AI guardrail plugins ([docs](https://docs.konghq.com/gateway/latest/ai-gateway/)) | **No** — standard logging plugin ecosystem only ([plugin hub](https://developer.konghq.com/plugins/)) |
| **Envoy AI Gateway** | Apache-2.0 ([LICENSE](https://raw.githubusercontent.com/envoyproxy/ai-gateway/main/LICENSE)) | 1,978 ([repo](https://github.com/envoyproxy/ai-gateway)) | Ext-proc data plane; K8s CRDs ([architecture](https://aigateway.envoyproxy.io/docs/concepts/architecture/)) | **No** — OTel GenAI semconv tracing only ([docs](https://aigateway.envoyproxy.io/docs/capabilities/observability/)) |
| **Portkey** | MIT ([repo](https://github.com/Portkey-AI/gateway)) | 12,859 | `before_request_hooks`/`after_request_hooks`; explicit `async` + `deny` flags ([docs](https://portkey.ai/docs/product/guardrails)) | **No** — records all requests; enterprise adds audit logs, KMS/BYO keys; not tamper-evident ([enterprise docs](https://portkey.ai/docs/product/enterprise-offering)) |
| **OpenRouter** | Closed | n.a. | SDKs + MCP server; routing/privacy-level policy ([quickstart](https://openrouter.ai/docs/quickstart)) | **No** — unified reporting/export; traces broadcast to third parties ([enterprise](https://openrouter.ai/enterprise)) |
| **Helicone** | Apache-2.0 ([LICENSE](https://raw.githubusercontent.com/Helicone/helicone/main/LICENSE)) | 6,116 ([repo](https://github.com/Helicone/helicone)) | Base-URL-change edge proxy on Cloudflare Workers ([quickstart](https://docs.helicone.ai/getting-started/quick-start)) | **No** — Kafka→Postgres/ClickHouse async pipeline, bodies in S3 ([architecture post](https://upstash.com/blog/implementing-upstash-kafka-with-cloudflare-workers)) |
| **Langfuse** | MIT core; `ee/` dirs separate ([LICENSE](https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE)) | 33,955 ([repo](https://github.com/langfuse/langfuse)) | OTel-native SDK v4; OTLP ingestion ([OTel docs](https://langfuse.com/docs/opentelemetry/get-started)) | **No** — S3-first queued ingestion, not tamper-evident ([self-hosting](https://langfuse.com/self-hosting)) |
| **Braintrust** | Proxy MIT; core closed ([repo](https://github.com/braintrustdata/braintrust-proxy)) | 410 | OpenAI-compatible proxy on Cloudflare Workers ([proxy docs](https://www.braintrust.dev/docs/guides/proxy)) | **No** — "Brainstore" trace store, no tamper-evidence ([braintrust.dev](https://www.braintrust.dev/)) |
| **OpenLLMetry** (Traceloop) | Apache-2.0 ([repo](https://github.com/traceloop/openllmetry)) | 7,409 | OTel extensions; semconv contributed upstream into OTel ([README](https://raw.githubusercontent.com/traceloop/openllmetry/main/README.md)) | **No** |
| **Arize Phoenix** (OpenInference) | Elastic License 2.0 ([LICENSE](https://raw.githubusercontent.com/Arize-ai/phoenix/main/LICENSE)) | 11,252 ([repo](https://github.com/Arize-ai/phoenix)) | OTel/OpenInference auto-instrumentation ([docs](https://arize.com/docs/phoenix)) | **No** |

### 3.2 The five architectural patterns we adopt (from the report's pattern list)

1. **Async, batched, queue-mediated evidence capture, decoupled from the request path.**
   Helicone returns the provider response first, then publishes to Kafka; consumers insert
   batches in single DB transactions with at-least-once semantics — a deliberate rebuild
   after "synchronous log processing overwhelmed our database" ([Upstash/Helicone](https://upstash.com/blog/implementing-upstash-kafka-with-cloudflare-workers), [Helicone V2](https://www.helicone.ai/blog/introducing-helicone-v2)). Langfuse persists all events to S3 first, queues a reference in Redis, ingests to ClickHouse later, so spikes cause neither timeouts nor loss ([Langfuse self-hosting](https://langfuse.com/self-hosting)). **Our version:** sign and enqueue the receipt synchronously; assemble/persist proof material asynchronously. → `szl-evidence-litellm`.
2. **Explicit, per-policy fail-open / fail-closed matrix.** Portkey's `async` flag (true =
   zero-added-latency log-only; false = blocking) and `deny` flag (true = kill with HTTP 446;
   false = pass annotated with HTTP 246) is the cleanest reference ([Portkey guardrails](https://portkey.ai/docs/product/guardrails)); LiteLLM mirrors with `pre_call` / `post_call` / `during_call` / `logging_only` modes ([LiteLLM guardrails](https://docs.litellm.ai/docs/proxy/guardrails/quick_start)). **Our version:** receipt-issuance failure either blocks the LLM call (fail-closed, audit-grade) or degrades to best-effort logging (fail-open, latency-grade) — chosen per policy, never silently. → `szl-evidence-litellm`.
3. **Lifecycle hooks including per-attempt capture.** LiteLLM's `CustomLogger` defines
   `log_pre_api_call`, `log_post_api_call`, `log_success_event`, `log_failure_event` plus
   per-attempt deployment hooks (`async_pre_call_deployment_hook`,
   `async_post_call_success_deployment_hook`, `async_post_call_failure_deployment_hook`) that
   fire once per real deployment call *including retries and fallbacks* ([LiteLLM custom callbacks](https://docs.litellm.ai/docs/observability/custom_callback)). Per-attempt matters: retries and fallbacks must not silently escape the evidence trail. **Our version:** the receipt chain binds every real upstream attempt, not just the logical request. → `szl-evidence-litellm`.
4. **OTel-native emission using GenAI semantic conventions.** Langfuse SDK v4 is "a thin
   layer on top of the official OpenTelemetry client" ([Langfuse OTel](https://langfuse.com/docs/opentelemetry/get-started)); OpenLLMetry's conventions were contributed into OTel itself ([README](https://raw.githubusercontent.com/traceloop/openllmetry/main/README.md)); Phoenix is OTel-based ([docs](https://arize.com/docs/phoenix)); Envoy AI Gateway emits GenAI tracing per OTel semconv ([docs](https://aigateway.envoyproxy.io/docs/capabilities/observability/)). **Our version:** receipts ride OTLP and `gen_ai.*` attributes, slotting into all of these stacks without a custom transport. → `szl-evidence-litellm`.
5. **One canonical payload + correlation ID + object-storage offload.** LiteLLM's single
   `StandardLoggingPayload` goes to every sink with a unique `call_id` echoed in the
   `x-litellm-call-id` response header ([LiteLLM logging](https://docs.litellm.ai/docs/proxy/logging)); Helicone stores bodies in S3 and puts only references in Kafka because bodies "can be several megabytes" ([Upstash/Helicone](https://upstash.com/blog/implementing-upstash-kafka-with-cloudflare-workers)). **Our version:** one canonical receipt schema, a request-ID header clients can use to challenge the log, and hash-references to bodies in object storage — keeping the receipt small enough to sign and chain per request. → `szl-evidence-litellm` + `szl-receipts`.

### 3.3 The gap and our posture toward LiteLLM

Stated plainly: **none of the ten projects has tamper-evident logs.** The fetched pages for
LiteLLM, Langfuse, Portkey, Helicone, Phoenix, and OpenRouter show no hash-chaining, signing,
or append-only guarantee for request records; the only cryptographic-integrity mention found
in the whole scan was LiteLLM cosign-signing its *Docker releases*, unrelated to request logs
([LiteLLM README](https://raw.githubusercontent.com/BerriAI/litellm/main/README.md)).
Portkey's enterprise audit logs + KMS ([enterprise offering](https://portkey.ai/docs/product/enterprise-offering)) and Langfuse's S3-first persistence ([self-hosting](https://langfuse.com/self-hosting)) are the nearest misses.

Our move is **not** to build an eleventh gateway. `szl-evidence-litellm` is a LiteLLM
`CustomLogger` plugin that adds exactly the missing layer — a tamper-evident DSSE receipt per
inference request, fail-closed policy mode, async batched sink — **into LiteLLM's ecosystem**
(57,629 stars, MIT, adopted by Stripe/Netflix/Google ADK per its [README](https://raw.githubusercontent.com/BerriAI/litellm/main/README.md)).
LiteLLM keeps the routing, budget, and guardrail market; we own the evidence plane beneath
whoever wins it. Because Langfuse, Phoenix, and OpenLLMetry all ingest OTLP, the same receipt
stream lands in the buyer's existing observability stack unmodified.

---

## 4. Surface: AI silicon + hardware roots of trust

### 4.1 Leaders table (condensed)

| Entity | Flagship | Openness | Funding / scale | Attestation & governance features |
|---|---|---|---|---|
| **Tenstorrent** | Blackhole p150a/p100a; QuietBox | Fully open stack: TT-Metalium + TT-NN and TT-Forge compiler under Apache-2.0 ([tt-metal](https://github.com/tenstorrent/tt-metal), [TT-Forge](https://docs.tenstorrent.com/tt-awesome/entry/tt-forge/)) | Series D $693M Dec 2024 ~$2.6B post ([TechCrunch](https://techcrunch.com/2024/12/02/jeff-bezos-backs-ai-chipmaker-tenstorrent/)); reported $800M Series E Nov 2025 ([TechStartups](https://techstartups.com/2025/11/18/ai-chip-startup-tenstorrent-in-talks-to-raise-800m-in-funding-at-a-3-2b-valuation-led-by-fidelity/)) | **None found** — no secure boot, RoT, TEE, or attestation on product pages or repo ([cards](https://tenstorrent.com/en/hardware/cards)) |
| **Groq** | LPU; GroqCloud | Closed ISA/compiler ([Future of Computing](https://news.future-of-computing.com/p/from-gpus-to-lpus-where-groq-fits-among-nvidia-amd-and-cerebras)) | >$3B raised; $750M at $6.9B Sep 2025 ([Reuters](https://www.reuters.com/business/groq-more-than-doubles-valuation-69-billion-investors-bet-ai-chips-2025-09-17/)); NVIDIA ~$20B license/asset deal Dec 2025 ([CNBC](https://www.cnbc.com/2025/12/24/nvidia-buying-ai-chip-startup-groq-for-about-20-billion-biggest-deal.html)) | **None at hardware level** — enterprise compliance (SOC 2, GDPR, HIPAA) only ([groq.com](https://groq.com/technology/)) |
| **Cerebras** | WSE-3 / CS-3, CS-4 | Closed wafer-scale ([cerebras.ai](https://www.cerebras.ai/chip)) | IPO raised $5.55B at ~$56.4B fully diluted, May 2026 ([TechCrunch](https://techcrunch.com/2026/05/14/cerebras-raises-5-5b-kicking-off-2026s-ipo-season-with-a-bang/)); 2025 revenue $510M, +76% YoY | **None found** ([cerebras.ai](https://www.cerebras.ai/chip)) |
| **Etched** | Sohu transformer ASIC | Closed — transformer graph hard-wired in silicon ([Awesome Agents](https://awesomeagents.ai/hardware/etched-sohu/)) | >$1.1B total incl. $500M Series B at $5B and $300M Series C at $10.3B Jul 2026 ([Enera](https://www.eneralabs.com/blog/etched-sohu-300m-transformer-asic-enterprise-inference-2026/)) | **None found in any fetched source** |
| **d-Matrix** | Corsair (DIMC) | Stack "built with open-source software" (MLIR/PyTorch/OpenBMC); no open ISA ([d-matrix.ai](https://www.d-matrix.ai/product/)) | $450M total; $275M Series C Nov 2025 at $2B ([d-Matrix press](https://www.d-matrix.ai/announcements/d-matrix-raises-275-million-to-power-the-age-of-ai-inference/)) | **None found** ([d-matrix.ai](https://www.d-matrix.ai/product/)) |
| **Positron AI** | Atlas server | Closed ([positron.ai](https://www.positron.ai/atlas)) | ~$305M total; $230M Series B Feb 2026 at >$1B ([Business Wire](https://www.businesswire.com/news/home/20260204250472/en/Positron-AI-Raises-$230-Million-Series-B-at-Over-$1-Billion-Valuation-to-Scale-Energy-Efficient-AI-Inference)) | **None found** ([positron.ai](https://www.positron.ai/atlas)) |
| **FuriosaAI** | RNGD NPU | Closed; native PyTorch 2.x ([Furiosa blog](https://furiosa.ai/blog/rngd-preview-furiosa-ai)) | $246M total after $125M Series C bridge Jul 2025 ([Forbes](https://www.forbes.com/sites/johnkang/2025/07/31/south-korean-ai-chip-startup-furiosaai-raises-125-million/)); rejected Meta's $800M offer ([TechCrunch](https://techcrunch.com/2025/03/24/ai-chip-startup-furiosaai-reportedly-turns-down-800m-acquisition-offer-from-meta/)) | **None found** ([Furiosa blog](https://furiosa.ai/blog/rngd-preview-furiosa-ai)) |
| **NVIDIA CC** (H100/H200/B200) | GPU CC mode | Closed HW/FW; CUDA support since 12.2 ([Edgeless wiki](https://www.edgeless.systems/wiki/hardware/nvidia-hopper-h100)) | Product line | On-die RoT, secure+measured boot, ECC-384 device identity, SPDM remote attestation verified via NRAS — **session-setup scope; no per-inference receipts** ([NVIDIA developer blog](https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/)) |
| **Intel TDX** | Trust Domains on Xeon | Closed ISA extension; public module spec ([spec PDF](https://cdrdv2-public.intel.com/853286/intel-tdx-module-base-spec-348549006.pdf)) | Product line; shipping in Alibaba Cloud, Azure, Google Cloud ([Intel](https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/overview.html)) | VM-scope remote attestation of platform configuration; **no per-inference or per-request receipts** ([Intel](https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/overview.html)) |
| **AMD SEV-SNP** | EPYC 7003+ TEE | Closed HW; public specs, open guest tooling ([arXiv](https://arxiv.org/html/2406.01186v1)) | Product line; in AWS EC2 ([AWS docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/sev-snp.html)) | VCEK-signed guest attestation report, launch-time measurement; **no per-inference receipts** ([AMD](https://www.amd.com/en/developer/sev.html)) |
| **Caliptra** (MSFT/Google/AMD/NVIDIA) | Open silicon RoT, v2.1 Oct 2025 | Open RTL + firmware Apache-2.0 ([spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/)) | Consortium project; committed intercept for Google/Microsoft first-party silicon and AMD EPYC 9006 ([spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/), [AMD](https://www.amd.com/en/developer/sev.html)) | Measured boot, TCG DICE identity (UDS→IDevID→LDevID→DPE), dual ECDSA P-384 + MLDSA-87 signed attestation, fuse-based anti-rollback monotonic counters (min 64) — **boot/firmware scope; mailbox explicitly "not high-performance line-rate data-path cryptography"** ([spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/)) |
| **OpenTitan** (Google/lowRISC) | "Earl Grey" discrete RoT; "Darjeeling" SoC subsystem | HW + SW + tooling all Apache-2.0 ([FAQ](https://opentitan.org/faq/)) | Project; shipping in commercial Chromebooks as of Mar 2026, fabbed by Nuvoton ([Google blog](https://opensource.googleblog.com/2026/03/opentitan-shipping-in-production.html)) | PQC secure boot (SLH-DSA), code-integrity, side-channel/fault-injection countermeasures — **boot/code-integrity scope; no per-inference receipts** ([Google blog](https://opensource.googleblog.com/2026/03/opentitan-shipping-in-production.html)) |

### 4.2 The finding

After searching all twelve entities: **no shipping AI accelerator offers per-inference
cryptographic receipts or policy gating in the compute datapath.** The state of the art is
boot-time and session-time attestation — NVIDIA CC authenticates device/firmware at session
setup and its own documentation describes no per-request receipt mechanism ([NVIDIA developer blog](https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/), [Edgeless wiki](https://www.edgeless.systems/wiki/hardware/nvidia-hopper-h100)); TDX and SEV-SNP attest VM/platform configuration, not individual inferences ([Intel](https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/overview.html), [AMD](https://www.amd.com/en/developer/sev.html)). Caliptra's mailbox is control-plane-only by explicit spec scoping ([Caliptra 2.0 spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/)). The only per-inference
receipt construct found, the IETF individual draft "Attested Inference Receipt (AIR)"
(draft-tsyrulnikov-rats-attested-inference-receipt-02, July 2026, no formal IETF standing),
is a COSE_Sign1/Ed25519 receipt emitted by **software inside a TEE** — its GPU variant
verifies H100 CC attestation out-of-band rather than embedding it, and its only implementation
is a demo reference stack on AWS Nitro/TDX/GCP ([IETF Datatracker](https://datatracker.ietf.org/doc/draft-tsyrulnikov-rats-attested-inference-receipt/)).
Attestation proves *what booted*; nothing shipping proves *what each inference did*.

### 4.3 What we adopt

- **Tenstorrent's open-stack GTM.** The compiler and op library (Apache-2.0 TT-Metalium /
  TT-Forge), not the accelerator ISA, are the openness lever; cards actually ship and are
  buyable at $999 ([Tenstorrent cards](https://tenstorrent.com/en/hardware/cards), [The Register](https://www.theregister.com/on-prem/2025/11/27/blackhole-quietbox-tenstorrents-ai-workstation-reviewed/2113269)). This is the proof that open-stack silicon is a viable
  go-to-market. Our mirror: `kids-sim` and (planned) `khipu-conformance` ship Apache-2.0 so
  third parties can run the golden vectors; the RTL repos stay proprietary until KIDS v0.1
  freezes (build order in `discovery/fork_findings.md` §3).
- **Caliptra's DICE identity + anti-rollback monotonic counters as design references for
  RC1.** UDS-in-fuses → IDevID → LDevID → DPE identity derivation and fuse-based monotonic
  counters (minimum 64) are the published, battle-reviewed shape of the properties RC1 must
  have (signed firmware with anti-rollback, per-device identity) ([Caliptra spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/)). We reference the design; we do not copy RTL blindly — Caliptra is explicitly not datapath crypto, which is precisely the layer KIDS adds.
- **OpenTitan as the RC1 silicon reference.** All-Apache-2.0 hardware/software/tooling,
  first open RoT in high-volume production (Chromebooks, Mar 2026), SHA-3/KMAC accelerator,
  ownership transfer, side-channel + fault-injection countermeasures ([OpenTitan FAQ](https://opentitan.org/faq/), [Google blog](https://opensource.googleblog.com/2026/03/opentitan-shipping-in-production.html)). RC1 — the Beacon manual's independent MCU governing privileged I/O — inherits its threat model and countermeasure checklist from OpenTitan rather than from a closed datasheet.

### 4.4 The wedge: KIDS v0.1, four primitives, simulator first

Per the KHIPU appendix (`discovery/fork_findings.md` §3): if KIDS is GEMM + attention only,
it is "a slower H100" and loses to 43 startups holding $17.7B and to Tenstorrent's open
stack. The four primitives that make it a different *kind* of chip:

1. **LGATE (Λ-gate):** a single-cycle policy gate in the datapath. No shipping part has any
   equivalent (§4.2). In `kids-sim` it exists as opcode `LGATE_CHECK` (0x09); privileged
   opcodes (`DMA_STORE`, `KV_APPEND`, `KV_COMMIT`, `RC1_RECV`) require RC1-mailbox
   authorization before execution.
2. **SHA3-256 receipt engine** with monotonic counter + anti-replay — and **explicit domain
   separation** (`SZL-KIDS-RECEIPT-V1` in `kids-sim/isa.py`), because the fork analysis
   flagged that running SHA3-256 in hardware receipts while the rest of the estate uses
   SHA-256 is a cross-domain preimage risk unless domain separation is specified with a
   cross-language test vector before any RTL (`discovery/fork_findings.md` §3).
3. **RC1 mailbox as a hard partition.** The "Linux cannot bypass" property becomes physics,
   not policy — the same boundary the Beacon EVT acceptance tests RC1-01…RC1-04 probe,
   with RC1-04 (Linux bypass attempt) as "the test that proves the claim"
   (`discovery/fork_findings.md` §3). Caliptra's 256 KiB mailbox is the contrast: control-plane
   only ([Caliptra spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/)).
4. **KV-cache per-block Merkle commitment:** the model *proves it attended to the right
   tokens* — verifiable inference at the datapath, the layer the AIR draft can only reach
   from TEE software ([IETF Datatracker](https://datatracker.ietf.org/doc/draft-tsyrulnikov-rats-attested-inference-receipt/)).

Build order is fixed and not reordered: freeze KIDS v0.1 → **golden simulator + conformance
vectors first** (`kids-sim` is the executable specification; differential tests against
NumPy are the only correctness proof) → GEMM/RMSNorm/DMA FPGA path → attention/YARQA + KV
engine → receipt engine + RC1 → compiler → PyTorch integration → benchmark and attack-test,
and only then an ASIC decision (`discovery/fork_findings.md` §3).

---

## 5. Surface: C-UAS + maritime autonomy

### 5.1 Leaders table (condensed)

| Entity | Flagship | Funding | Contracts (value · date) | Evidence / audit-trail story |
|---|---|---|---|---|
| **Anduril** | Lattice C2; Anvil/Roadrunner-M | $11.4B total; $5B Series H May 2026 at $61B ([Reuters](https://www.reuters.com/legal/transactional/us-defense-firm-anduril-raises-5-billion-doubling-its-valuation-61-billion-2026-05-13/)) | $20B/10-yr Army FFP vehicle + $87M first task order as JIATF-401 C-UAS C2 backbone, Mar 2026 ([Breaking Defense](https://breakingdefense.com/2026/03/army-awards-anduril-counter-drone-task-order-as-first-in-new-20b-contract-vehicle/)) | **n.a.** — no published tamper-evident engagement logging |
| **Dedrone** (Axon) | DedroneTracker.AI | ~$88.5M pre-acquisition; acquired by Axon, completed Oct 2024 ([Drone Intelligence](https://droneintelligence.ai/companies/dedrone)) | n.a. published | **Strongest in set, not tamper-evident:** "Forensic Evidence for Law Enforcement" — CSV export, GPX track download, alert video, replay-on-map ([DroneTracker brochure](https://sandstormdefence.com/wp-content/uploads/2024/03/Dedrone-DroneTracker-Software-EN.pdf)) |
| **Fortem** | DroneHunter F700; SkyDome | ~$104M ($79.3M + $25M Lockheed-led Series B tranche Apr 2026) ([Drone Intelligence](https://droneintelligence.ai/companies/fortem-technologies)) | $1.011B-ceiling DHS C-UAS IDIQ prime, Aug 4 2026 ([Fortem](https://www.fortemtech.com/press-releases/2026-08-04-fortem-technologies-selected-as-prime-contractor-on-5-year-dhs-counter-drone-idiq-worth-more-than-1b/)); first Replicator 2 purchase, 2 F700s, Jan 11 2026 ([War.gov](https://www.war.gov/News/News-Stories/Article/Article/4377021/joint-interagency-task-force-announces-first-replicator-2-purchase-to-counter-h/)) | **n.a.** |
| **Epirus** | Leonidas HPM | >$550M; $250M Series D Mar 2025 ([PR Newswire](https://www.prnewswire.com/news-releases/epirus-closes-250m-series-d-to-hyperscale-leonidas-production-capability-for-critical-asset-protection-302392509.html)) | $43.5M IFPC-HPM Gen II Jul 2025; $66.1M Jan 2023; $17M Oct 2024; $11M HAVOC 2026 ([Epirus](https://www.epirusinc.com/press-releases/epirus-receives-43-million-contract-from-u-s-army-for-ifpc-hpm-generation-ii-systems)) | **n.a.** |
| **Shield AI** | Hivemind Enterprise; V-BAT | >$3.5B; $1.5B Series G + $500M preferred Mar 2026 at $12.7B ([Shield AI](https://shield.ai/shield-ai-to-acquire-software-simulation-company-aechelon-and-raise-2b-at-12-7b-valuation/)) | USAF CCA mission-autonomy provider, value undisclosed | **Partial — assurance, not receipts:** sim V&V, test orchestration, config management; no tamper-evident engagement logging ([Hivemind SDK](https://shield.ai/from-concept-to-combat-how-hivemind-sdk-powers-next-gen-autonomy/)) |
| **AeroVironment** | Switchblade; LOCUST; Titan C-UAS; AV_Halo | Public (NASDAQ: AVAV) | $500M/3-yr Army C-UAS IDIQ Jul 1 2026 under JIATF-401 "Domestic Shield" + $80.5M Titan-MS ([DefenseScoop](https://defensescoop.com/2026/07/02/pentagon-awards-500m-contract-aerovironment-counter-drone-technology/), [Wikipedia](https://en.wikipedia.org/wiki/AeroVironment)); $874.26M 5-yr FMS IDIQ Dec 2025 ([AV](https://www.avinc.com/2025/12/08/aerovironment-awarded-874m-foreign-military-sales-idiq-to-deliver-uas-and-c-uas-systems-to-allied-partner-forces/)); 1,000+ Titan units deployed | **n.a.** |
| **Saildrone** | Surveyor 65-ft USV | >$345M total incl. $50M Lockheed strategic Oct 2025 ([Sacra](https://sacra.com/c/saildrone/)) | $15.5M for 16 Voyager USVs, US Coast Guard ([Sacra](https://sacra.com/c/saildrone/)) | **n.a. for receipts** — nearest assurance artifact: full ABS classification with AUTONOMOUS notation, first ocean-going USV to achieve it ([Sacra](https://sacra.com/c/saildrone/)) |
| **Windward** (FTV) | Maritime AI platform | $32.3M VC pre-IPO; acquired by FTV Capital for $270M ([Tracxn](https://tracxn.com/d/companies/windward/__AeHlNZYbTmpTG_dAyy1v8rwqywUixxIeuk2JTw_4nU8), [Jewish Business News](https://jewishbusinessnews.com/2024/12/24/ftv-capital-acquires-israeli-maritime-ai-leader-windward-for-270-million-in-cross-border-deal/)) | n.a. published; acquired Prominent Edge Apr 2026 ([Windward](https://windward.ai/news/windward-acquires-prominent-edge/)) | **Closest maritime analog by marketing:** "explainable" intelligence and "evidence-based targeting," nothing on tamper-evident logging ([windward.ai](https://windward.ai/)) |
| **HawkEye 360** | Space-based RF geolocation | $561.53M total; Series E $150M + $23M ext.; $1.82B post-money ([Forge Global](https://forgeglobal.com/hawkeye-360_ipo/), [Satellite Today](https://www.satellitetoday.com/finance/2026/03/04/hawkeye-360-adds-23m-to-series-e-funding/)) | European MoD EW program up to $75M, Mar 2026 ([Satellite Today](https://www.satellitetoday.com/finance/2026/03/04/hawkeye-360-adds-23m-to-series-e-funding/)) | **n.a.** |
| **Darkhive** | Open-architecture sUAS + accredited software delivery (FLEETFORGE) | $55M total; $30M Series B May 2026, RTX Ventures ([Tectonic Defense](https://www.tectonicdefense.com/darkhive-secures-30m-in-series-b-funding/)) | $49.7M APFIT (largest single award), public Mar 2026; $100M-ceiling AFWERX Autonomy Prime Phase III SBIR ([Tectonic Defense](https://www.tectonicdefense.com/darkhive-secures-30m-in-series-b-funding/), [DroneXL](https://dronexl.co/2024/01/07/darkhive-100-million-federal-contract-drone/)) | **n.a. for decision evidence** — but the secure, DoD-accredited software-supply-chain pipeline is the closest governance-adjacent story among small-UAS players ([Darkhive](https://www.darkhive.com/post/defense-tech-startup-darkhive-secures-21-million-series-a-investment-led-by-ten-eleven-ventures)) |

### 5.2 The finding

**No entity in this set publishes tamper-evident logging of autonomous engagements.** The
nearest artifacts are Dedrone's forensic-evidence exports (law-enforcement oriented, plain
files, not tamper-evident), Shield AI's V&V/runtime-assurance investment, Windward's
"explainable, evidence-based" marketing, and Darkhive's accredited software delivery
([cuas_maritime_landscape.md, Section 1 takeaway](../../research/cuas_maritime_landscape.md)).
The differentiator is genuinely unoccupied — and the buyer is newly organized to want it.

### 5.3 The open windows (dated)

- **JIATF-401 Commercial Solutions Opening (CSO — open).** Issued late February 2026; areas of
  interest include mobile C-UxS, fixed-site C-UAS, and C2; fixed-price contracts; **awards may
  be issued through end of 2028** ([DefenseScoop](https://defensescoop.com/2026/02/27/jiatf-401-commercial-solutions-opening-cso-counter-uas/)). The establishing memo (Aug 27, 2025) makes JIATF-401 the supported organization for C-sUAS **forensics, exploitation, and replication** — a forensics mandate written into the charter, with a 36-month sunset review ([memo PDF](https://media.defense.gov/2025/Aug/28/2003790021/-1/-1/0/ESTABLISHMENT-OF-JOINT-INTERAGENCY-TASK-FORCE-401.PDF)). A receipts capability answers the charter text directly.
- **DoW FY26 Release 5 SBIR topics (open now).** Opened Aug 26, 2026, **close Sept 23, 2026
  12:00 ET** ([DARPA SBIR/STTR topics](https://www.darpa.mil/work-with-us/communities/small-business/sbir-sttr-topics)). Closest topic: OSD "Collaborative Distributed Swarm Radar" (OSW26BZ05-DV019, closes Sept 23) ([SBIR.gov topic 12846](https://www.sbir.gov/topics/12846)). **No open topic specifically on C-UAS assurance or autonomy-evidence/tamper-evident logging exists** — per the research, "the theme is unfunded and uncontested in the current solicitation set" ([cuas_maritime_landscape.md](../../research/cuas_maritime_landscape.md)). (The Navy C-UAS CSO closed Jul 22, 2026 and the Release-4 swarm topics closed Aug 19, 2026 — those windows are gone; the swarm-defense topic was Army, not MDA: [Army SBIR topic](https://armysbir.army.mil/topics/asymmetric-collaborative-counter-swarm/).)
- **CyLab Partners Conference, Oct 20–21, 2026**, Rangos Ballroom, CMU; invited guests/partners
  ([CyLab 2026](https://www.cylab.cmu.edu/events/partners_conference/2026/index.html)).
  CyLab's Cyber Autonomy Initiative (announced Mar 23, 2026 at RSAC, co-director Vyas Sekar)
  is the thematically adjacent research program ([CyLab news](https://www.cylab.cmu.edu/news/2026/03/23-cyber-autonomy-initiative.html)).
- **Market anchor:** the AI slice of maritime domain awareness was valued at **$3.8B in 2025,
  projected ~$10.2B by 2034, 11.6% CAGR 2026–2034** ([DataIntelo](https://dataintelo.com/report/maritime-domain-awareness-ai-market)); the broader C-UAS market estimate carried in our discovery notes is $9.17B in 2026 → $29.7B by 2031 at 26.5% CAGR (`discovery/fork_findings.md` §7, uncorroborated there by a fetched URL).

### 5.4 What we adopt (each upgraded with receipts)

- **Anduril's open-architecture C2 posture.** Lattice integrates varied sensors/effectors
  through an open architecture ([Breaking Defense](https://breakingdefense.com/2026/03/army-awards-anduril-counter-drone-task-order-as-first-in-new-20b-contract-vehicle/)). `killinchu` (our governed counter-UAS/maritime app, per `discovery/brain_digest.md`) adopts the same integrate-anything posture — but every governed ALLOW/HALT decision emits a tamper-evident receipt to the unified ledger, which Lattice does not publish.
- **Darkhive's accredited-software-delivery story.** Darkhive's pipeline builds/scans/tests
  and securely deploys DoD-accredited software to fleets ([Darkhive](https://www.darkhive.com/post/defense-tech-startup-darkhive-secures-21-million-series-a-investment-led-by-ten-eleven-ventures)). We adopt the *accredited delivery* motion via `szl-uds-deployment` (Zarf/UDS, cosign-verified, air-gap installable per `discovery/brain_digest.md`) — and extend it from "accredited software" to "accredited software whose every field decision is receipted."
- **Dedrone's evidence-export UX.** Filterable alert lists, CSV export, GPX track download,
  alert video, replay-on-map ([DroneTracker brochure](https://sandstormdefence.com/wp-content/uploads/2024/03/Dedrone-DroneTracker-Software-EN.pdf)) — the best export UX in the set. We adopt the export shapes verbatim in spirit; each export row carries its receipt so the prosecutor's exhibit is verifiable, not just readable. The `szl-beacon` reference package is the receipt-emitting field unit for the maritime/disaster/legal fleet concept (`discovery/fork_findings.md` §1: 50–100-unit Beacon fleet spec, maritime as strongest vertical for receipt density).

---

## 6. Cross-surface Adopt / Build / Refuse matrix

| Pattern | Source project | License | SZL destination repo | Adopt-as-is or reimplement |
|---|---|---|---|---|
| Policy packs as reviewable data (YAML corpus, validated at load) | Credo AI policy packs ([credo.ai](https://www.credo.ai/blog/accelerating-global-growth-and-innovation-in-ai-governance-with-21-million-in-new-capital)) | Proprietary concept — content is ours | `szl-iso42001` | **Reimplement** (license-clean: our own questionnaire) |
| Inventory tied to a system of record | ServiceNow AI Control Tower / CMDB ([servicenow.com](https://www.servicenow.com/products/ai-control-tower.html)) | Proprietary | `szl-estate` | **Reimplement** (two-source enumeration) |
| Automatic lifecycle documentation | IBM Factsheets ([ibm.com](https://www.ibm.com/docs/en/watsonx/saas?topic=cloud-watsonxgovernance-plans)) | Proprietary | `szl-receipts` | **Reimplement** as signed receipts |
| Re-computable claims ("system of record" you can re-run) | ModelOp ([modelop.com](https://www.modelop.com/blog/press-release-modelop-raises-10-million-to-accelerate-innovation-of-its-leading-ai-governance-software)) | Proprietary | `szl-claims-api` (+ `szl-estate verify-claims`) | **Reimplement** |
| Async batched queue-mediated evidence capture | Helicone / Langfuse ([Upstash/Helicone](https://upstash.com/blog/implementing-upstash-kafka-with-cloudflare-workers), [Langfuse](https://langfuse.com/self-hosting)) | Apache-2.0 / MIT | `szl-evidence-litellm` | **Reimplement** the pattern (sign-sync, persist-async) |
| Explicit fail-open / fail-closed matrix | Portkey `async`+`deny` ([docs](https://portkey.ai/docs/product/guardrails)) | MIT | `szl-evidence-litellm` | **Reimplement** (config semantics, not code) |
| Lifecycle hooks incl. per-attempt | LiteLLM `CustomLogger` ([docs](https://docs.litellm.ai/docs/observability/custom_callback)) | MIT | `szl-evidence-litellm` | **Adopt-as-is** — we build *into* the interface, not around it |
| OTel-native GenAI semconv emission | OpenLLMetry / Langfuse / Envoy AI GW ([README](https://raw.githubusercontent.com/traceloop/openllmetry/main/README.md), [docs](https://aigateway.envoyproxy.io/docs/capabilities/observability/)) | Apache-2.0 / MIT | `szl-evidence-litellm` | **Adopt-as-is** (emit OTLP, `gen_ai.*`) |
| Canonical payload + correlation ID + object-storage offload | LiteLLM `StandardLoggingPayload` + Helicone S3 refs ([docs](https://docs.litellm.ai/docs/proxy/logging), [Upstash/Helicone](https://upstash.com/blog/implementing-upstash-kafka-with-cloudflare-workers)) | MIT / Apache-2.0 | `szl-evidence-litellm` + `szl-receipts` | **Reimplement** the pattern with receipt schema |
| RFC 8785 JCS, DSSE, in-toto, Ed25519 | IETF/W3C standards (locked estate decision per `discovery/brain_digest.md`) | Open standards | `szl-receipts` | **Adopt-as-is** |
| Open compiler/stack as GTM lever | Tenstorrent TT-Metalium/TT-Forge ([tt-metal](https://github.com/tenstorrent/tt-metal)) | Apache-2.0 | `kids-sim`, planned `khipu-conformance` | **Adopt pattern** (sim + conformance Apache-2.0; RTL proprietary) |
| DICE identity + anti-rollback monotonic counters | Caliptra v2.x ([spec](https://chipsalliance.github.io/Caliptra/2.0/specification/HEAD/)) | Apache-2.0 RTL; spec OWFa | RC1 design (planned `khipu-x1-hw`) | **Design reference; reimplement** |
| Silicon RoT threat model + countermeasures | OpenTitan ([FAQ](https://opentitan.org/faq/)) | Apache-2.0 | RC1 silicon reference | **Adopt-as-is** as reference IP/checklist |
| Accredited software delivery to fleets | Darkhive ([post](https://www.darkhive.com/post/defense-tech-startup-darkhive-secures-21-million-series-a-investment-led-by-ten-eleven-ventures)) | Proprietary | `szl-uds-deployment` + `killinchu` | **Reimplement** with receipts added |
| Forensic export UX (CSV/GPX/video/replay) | Dedrone DroneTracker ([brochure](https://sandstormdefence.com/wp-content/uploads/2024/03/Dedrone-DroneTracker-Software-EN.pdf)) | Proprietary | `killinchu` + `szl-beacon` | **Reimplement**, each row receipted |
| Dashboard-trust model (verify-by-login) | All ten governance vendors | — | **REFUSE** | Refused: offline verifier instead |
| "Auditable/explainable" as unbacked adjective | Fairly/Asenion, Windward ([fairly.ai](https://www.fairly.ai/about-us), [windward.ai](https://windward.ai/)) | — | **REFUSE** | Refused; banned-claims lint enforces |
| Closed ISA + closed compiler | Groq, Cerebras, Etched, FuriosaAI | — | **REFUSE** | Refused for the sim/conformance surface |
| Boot-scope attestation sold as inference assurance | NVIDIA CC / TDX / SEV-SNP scope | — | **REFUSE to conflate** | KIDS keeps the two layers explicit and separate |

---

## 7. Honest weaknesses — where the leaders beat us today

1. **Distribution.** Langfuse claims "50,000+ companies" ([pricing](https://langfuse.com/pricing));
   LiteLLM lists Stripe, Netflix, Google ADK as adopters with 57,629 stars ([README](https://raw.githubusercontent.com/BerriAI/litellm/main/README.md)); ServiceNow and IBM own the
   enterprise channel outright. SZL's only measured demand signal is 81.3K downloads on one
   OSINT dataset, and it is `license:other` — not even trainable (`discovery/fork_findings.md`
   §5). Receipts do not create a sales motion.
2. **Certifications.** Portkey lists SOC 2 / GDPR / ISO 27001 / HIPAA ([enterprise docs](https://portkey.ai/docs/product/enterprise-offering)); Braintrust lists SOC 2 Type II, HIPAA, GDPR ([braintrust.dev](https://www.braintrust.dev/)); Traceloop lists SOC 2 & HIPAA ([traceloop.com](https://www.traceloop.com/)). SZL holds none, and real ISO 42001 certification runs
   $7K–20K in audit fees plus €60K–300K internal effort over 3–6 months ([Vanta](https://www.vanta.com/collection/iso-42001/iso-42001-certification-cost), [Modulos](https://www.modulos.ai/blog/iso-42001-certification-guide/)). Our readiness checker explicitly is **not** certification — the `DISCLAIMER` string in `szl-iso42001` says so in every report.
3. **Deployed fleet and contract gravity.** AeroVironment has 1,000+ Titan units deployed and
   a $500M JIATF-401 "Domestic Shield" IDIQ ([AV](https://www.avinc.com/2025/12/08/aerovironment-awarded-874m-foreign-military-sales-idiq-to-deliver-uas-and-c-uas-systems-to-allied-partner-forces/), [DefenseScoop](https://defensescoop.com/2026/07/02/pentagon-awards-500m-contract-aerovironment-counter-drone-technology/)); Anduril holds the $20B Army vehicle and the JIATF-401 C2 backbone task order ([Breaking Defense](https://breakingdefense.com/2026/03/army-awards-anduril-counter-drone-task-order-as-first-in-new-20b-contract-vehicle/)); Saildrone holds the only ABS AUTONOMOUS-classified ocean USV ([Sacra](https://sacra.com/c/saildrone/)). SZL has zero deployed units; Beacon is a one-prototype EVT authorization (`discovery/fork_findings.md` §1). Our C-UAS posture must be *component/vendor to the primes* (receipts layer for their forensics mandate), not prime.
4. **Capital.** Anduril: $11.4B raised at a $61B valuation ([Reuters](https://www.reuters.com/legal/transactional/us-defense-firm-anduril-raises-5-billion-doubling-its-valuation-61-billion-2026-05-13/)); Cerebras: $5.55B IPO ([TechCrunch](https://techcrunch.com/2026/05/14/cerebras-raises-5-5b-kicking-off-2026s-ipo-season-with-a-bang/)); Groq: >$3B ([TechCrunch](https://techcrunch.com/2025/09/17/nvidia-ai-chip-challenger-groq-raises-even-more-than-expected-hits-6-9b-valuation/)); even ValidMind, the smallest governance player profiled, has $11.1M ([finsmes.com](https://www.finsmes.com/2024/03/validmind-raises-8-1m-in-seed-funding.html)). SZL is unfunded, solo-founder, and its own commercial ledger records all 24 rows as `UNKNOWN / blocks_raise:true` — no price, no second named owner (`discovery/brain_digest.md`). The receipts wedge does not solve the raise; it only gives the raise a defensible subject.
5. **What the wedge does NOT solve, technically.** (a) A receipt proves integrity and signer
   identity, **not that the model was right** — model quality, bias, and latency are
   untouched by tamper-evidence. (b) KIDS receipt overhead (tokens/s penalty, joules/token)
   is **unmeasured** until the FPGA path exists; the golden simulator proves correctness, not
   performance (`discovery/fork_findings.md` §3). (c) Vendor perf claims we compete near
   (Groq ~150 tokens/W claimed, Etched ~500K tok/s claimed, d-Matrix 20× power-efficiency
   claims) are unvalidated by third parties — but so is everything of ours until benchmarked
   ([Spheron](https://www.spheron.network/blog/nvidia-groq-3-lpu-explained/), [Enera](https://www.eneralabs.com/blog/etched-sohu-300m-transformer-asic-enterprise-inference-2026/), [d-Matrix](https://www.d-matrix.ai/product/)). (d) The "receipt cannot lie" claim stays banned until the public attack harness has actually been run and survived — V11 explicitly did not prove this (`discovery/brain_digest.md`, standing blockers). (e) Receipts do not discharge legal liability, ITAR/export constraints, or ROE judgment; they make the record of *who authorized what, when, under which policy* non-repudiable — which is the specific thing none of the 40+ entities profiled here currently sells.
6. **The incumbents can close the gap.** Nothing structural stops LiteLLM (MIT, huge
   community), ServiceNow (channel), or NVIDIA (silicon) from shipping hash-chained logs.
   The defense is speed plus the standards position: the agent-audit-trail IETF draft has no
   formal standing and no working group ([IETF Datatracker](https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/)), so the receipt format is still claimable — but that window is a fact about *now*, not a moat.

---

*End of teardown. Companion 40-line executive summary: `COMPETITIVE_TEARDOWN_EXEC.md`.
Evidence base: the four files in `../../research/`; SZL estate context:
`../../discovery/fork_findings.md` §§3, 5, 7 and `../../discovery/brain_digest.md`.*
