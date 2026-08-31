# szl-beacon

**REFERENCE IMPLEMENTATION of the A11oy Beacon REALITY PROTOCOL.**

**Zero physical Beacon units exist.** Per the Minewing RFQ, procurement scope
is *one* engineering prototype, and even that is not yet manufactured. This
package is protocol software: it exists so software and firmware teams can
build against a concrete, testable model of the protocol before hardware
EVT. Nothing in this package, its fleet configuration, or its RC1 module is
a claim of fielded hardware; the RC1 boundary is an executable **simulation**.

Per the Minewing RFQ scope, SZL owns: the A11oy app, the Reality Protocol
state machine + receipt semantics, the policy engine, and the signing
infrastructure. This package is the reference implementation of all four.

## The Reality Transaction

```
INTENT -> EVIDENCE -> PROPOSAL -> SIMULATION -> POLICY -> CONSENT
-> ACTION -> WITNESS -> OUTCOME -> RECONCILIATION -> RECEIPT
```

Core rules (the protocol, not implementation details):

1. **Each transition is a separate signed-style event** on an append-only,
   hash-chained log. No silent multi-state hops.
2. **A requested action, an executed action, and a verified physical outcome
   are NEVER synonyms.** OUTCOME cannot be entered without witness events
   from **>= 2 distinct witness classes** (Independent Sensor / Second Node /
   Recipient Confirmation / Authenticated Witness); same-class duplicates do
   not count; every witness carries its own evidence ref.
3. **CONSEQUENTIAL actions require explicit authorization** to pass
   POLICY -> CONSENT -> ACTION. Without it: refused, and the refusal is
   receipted on the chain.
4. **Reality Debt is never auto-resolved.** Conflicting evidence, missing
   witnesses, and failed verifications open debt items that block OUTCOME
   VERIFIED until closed by an explicit reconciliation event naming the debt.
5. **Fail closed.** Any schema/validation failure: transition refused,
   failure event appended, state unchanged.

## Honesty doctrine (non-negotiable)

- Unknown / unavailable / unverified / failed states stay **explicit**.
  There is no "probably fine" promotion anywhere in this codebase.
- Every event carries exactly one evidence label:
  `VERIFIED_SOURCE | AUTHORIZED_OPERATOR | COMMUNITY_REPORT |
  MACHINE_INFERENCE | CONFLICTING_EVIDENCE | UNVERIFIED | OUTCOME_VERIFIED`.
- Machine-originated content is **hard-typed `MACHINE_INFERENCE`** and is
  never rendered as, or merged into, official authority content
  (`labels.render_labeled` styles it distinctly).

## Modules

| Module | Purpose |
| --- | --- |
| `protocol.py` | Reality Transaction state machine (11 states, guarded transitions) |
| `events.py` | Event model: content-addressed, hash-chained, label enforcement |
| `debt.py` | Reality Debt register — OPEN until explicit reconciliation |
| `witness.py` | Witness Diversity — >= 2 distinct classes gate on OUTCOME VERIFIED |
| `policy.py` | Action classes + Rev A scope enforcement (refusals are receipted) |
| `rc1_sim.py` | **SIMULATION** of the RC1 hardware governance boundary; RC1-01..04 fixtures |
| `log.py` | Append-only JSONL hash-chained log; `verify()` detects truncation/reorder/replay/fork/prev-break and never raises |
| `sync.py` | Offline-first file-based peer sync; conflicts -> CONFLICTING_EVIDENCE debt, both copies retained |
| `fleet.py` | Fleet config schema + validator (50-unit REFERENCE fleet) |
| `labels.py` | Evidence label enum + rendering |
| `cli.py` | `python -m szl_beacon demo / verify / fleet validate / rc1-test / sync` |

## Canonical form and signatures — reference vs production

- **This package (reference, stdlib-only):** canonical JSON = sorted keys,
  no whitespace, UTF-8. Events are content-addressed (sha256 over the
  canonical body) and hash-chained. This is *not* RFC 8785 — do not claim
  JCS conformance for these digests. Non-integer floats are rejected from
  canonical bodies to avoid cross-canonicalizer divergence.
- **Production (szl-receipts):** canonicalization is RFC 8785 (JCS);
  signatures are per-device Ed25519 in DSSE envelopes; receipt predicates
  follow the GovernedAction format. The event identity model here
  (one event per transition, digest-linked, label-typed) carries over
  unchanged.

## CLI

```bash
python -m szl_beacon demo                     # full transaction, prints digests
python -m szl_beacon demo --json              # machine-readable
python -m szl_beacon verify <logdir>          # chain verification report
python -m szl_beacon fleet validate fleet/fleet.yaml
python -m szl_beacon rc1-test                 # RC1-01..04 fixtures (SIMULATION)
python -m szl_beacon sync <dir_a> <dir_b> <out_dir>
```

Every command supports `--help` and `--json`. The demo writes its verifiable
chain to a printed temp directory and exits 0.

## Testing

```bash
pip install -q pytest
cd /home/user/workspace/szl-platform
python3 -m pytest packages/szl-beacon -q
```

The suite covers: full happy-path transaction (11 transitions, chain
verifies); outcome-without-witness refusal; consequential-without-authorization
refusal (refusal event present); debt blocking OUTCOME VERIFIED until
reconciled; witness same-class duplicate rejection; Rev A refusals
(diagnosis/prescription refused and receipted); RC1-01..04 fixtures; log
tamper classes (truncation/reorder/replay/fork/prev-break); sync conflicts
producing CONFLICTING_EVIDENCE debt with both copies retained; fleet
validation (50-node reference passes, broken witness group fails); label
enforcement (machine event without MACHINE_INFERENCE rejected); CLI demo via
subprocess.

## Layout

```
packages/szl-beacon/
  pyproject.toml
  README.md
  schema/reality_event.schema.json
  fleet/fleet.yaml            # REFERENCE — NOT DEPLOYED. Zero units fielded.
  src/szl_beacon/{__init__,protocol,events,debt,witness,policy,rc1_sim,
                  log,sync,fleet,labels,cli}.py
  tests/test_{protocol,debt,witness,policy,rc1_sim,log,sync,fleet,labels,cli}.py
```
