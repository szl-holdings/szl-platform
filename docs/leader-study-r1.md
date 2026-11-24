# szl-platform domain leader study r1 (propose-only)

Date: 2026-11-24. Method: web-verified leader landscape + governing-seat ratification (Kimi nonce T11-RULING-20261124-K1). Study pinned to szl-platform HEAD 770bbf5bf84849edf102410a95157d0b539f4a32, fetched 2026-11-24. This card is documentation only; it changes no code, CI, config, or existing PR status. All absorb actions are FUTURE PROPOSALS (non-authorizing); implementation and merges remain separately reviewed and gated. L Conjecture 1: OPEN (advisory, never a closed theorem). No speedup, energy, or proven-trust claims; upstream performance claims are labeled as upstream claims only.

## Domain: Governed-AI engineering monorepo centered on receipt-first packages, estate audit control-plane work, a KIDS simulator, and an adversarial harness, with evidence and explicit review boundaries rather than asserted trust.

## Leaders studied (web-verified 2026-11-24)
1. Nx (https://github.com/nrwl/nx) - moat: Its project graph and task orchestration make dependencies and affected work explicit across a monorepo.
2. Turborepo (https://github.com/vercel/turborepo) - moat: Its task pipeline and content-addressed caching model provide a clear vocabulary for reproducible build inputs and outputs.
3. Pants (https://github.com/pantsbuild/pants) - moat: Its fine-grained dependency inference and hermetic execution model support precise, cacheable build reasoning.

## Absorb actions (FUTURE PROPOSALS, non-authorizing)
1. (Nx) Propose a documentation-only design note comparing explicit project-graph and affected-work concepts with receipt-first package boundaries and estate audit scoping, without adopting Nx or asserting equivalent behavior. Cost: doc-only, approximately 2-4 maintainer hours; limit: note only, no code, no infra changes.
2. (Turborepo) Propose a documentation-only review of task-input, output, and cache-key terminology as a prompt for clarifying provenance and replay expectations in receipts, while recording that caching is not evidence of correctness or trust. Cost: doc-only, approximately 2-3 maintainer hours; limit: note only, no code, no infra changes.
3. (Pants) Propose a documentation-only design note examining dependency-inference and hermetic-execution concepts as possible review questions for reproducibility claims in the simulator and adversarial harness, with no claim that those properties already hold here. Cost: doc-only, approximately 3-4 maintainer hours; limit: note only, no code, no infra changes.
4. Baseline preserve honestly: Preserve prove-don't-assert discipline, receipt-first evidence boundaries, append-only receipts, head-SHA pinning, and explicit separation among upstream claims, conjecture, proposals, and verified repository behavior; no leader terminology may be relabeled as a measured benefit, closed theorem, or authorization.

## Do not do (per governing seat)

Do not merge, bypass the signature wall, or claim implementation beyond this card.
