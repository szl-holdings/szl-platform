# kids-sim — KIDS v0.1 Golden Simulator

The **executable specification** for the KHIPU-X1 governance-first LLM
accelerator ISA. The golden simulator comes **before any RTL**;
differential tests against NumPy references are the only correctness
proof.

KIDS v0.1 freezes four ISA primitives no shipping accelerator has:

1. **LGATE** — a single-cycle policy gate in the datapath.
2. **SHA3-256 receipt engine** — monotonic counter, anti-replay,
   explicit domain separation (`SZL-KIDS-RECEIPT-V1`).
3. **RC1 mailbox** — a hard-partitioned control region the application
   processor **cannot** write (the "Linux bypass" property).
4. **KV-cache per-block Merkle commitment** — verifiable inference: the
   model proves it attended to the right tokens.

## Install & run

```bash
pip install -e packages/kids-sim[dev]
python3 -m pytest packages/kids-sim -q                              # 90 tests
python -m kids_sim.conformance run --vectors packages/kids-sim/vectors/ [--json]
python -m kids_sim.demo [--json]                                    # 2-layer transformer block
python -m kids_sim.cli run-program prog.json --json
python -m kids_sim.cli verify-receipts receipts.json
python -m kids_sim.cli perf prog.json
```

Exit codes (conformance): `0` all pass, `1` a vector FAILs, `2` a vector
is corrupt/invalid. UNKNOWN is never coerced to PASS.

## Honesty doctrine

- Every cycle number from `perf.py` is labeled **ESTIMATE** with its
  formula. `measured_wall_clock()` returns **UNAVAILABLE** — the
  simulator has no wall clock and never fabricates benchmarks.
- `hardware_timestamp` is a **cycle count**, never wall time.
- LGATE's single cycle is a **spec target to be proven in RTL**
  (documented in `lgate.py`); the perf model charges exactly 1 cycle.

## Design decisions

### bf16
NumPy has no bf16 dtype, so bf16 is implemented as **RNE truncation of
fp32 via bit manipulation** (`numeric.py`): drop the low 16 bits with a
round-to-nearest-even bias (`0x7FFF + ((u>>16)&1)`), NaN guarded so it
can never degenerate to Inf. Tests pin RNE at exact .5 boundaries
(rounds to even kept-LSB) and round-trip idempotence.

**bf16 GEMM is TPU-style**: operands rounded to bf16, products and
accumulation in fp64 (tile-order independent), output is the **fp32
accumulator** — bf16 store rounding is an explicit separate conversion.
Tolerances: bit-exact vs the golden reference at any tile size;
≤1e-3 rtol vs the fp32 reference on the same bf16-rounded operands (in
practice ~1e-6). Operand rounding itself contributes up to 2⁻⁹ relative
vs an unrounded fp32 GEMM — a property of the 8-bit bf16 significand,
documented rather than hidden.

**int8**: symmetric per-tensor scale, saturating quantize, **int32
accumulate** — exact integer arithmetic, exactly equal to the NumPy
int32 reference at any tile size.

### YARQA_COMPARTMENT semantics (frozen v0.1: "canal semantics")
The descriptor is a list of compartments, each a set of token indices
(canals). Query row `i` attends to key `j` iff **j ≤ i** (causality)
**and** `i`, `j` share at least one compartment. Tokens in no
compartment attend only to themselves. Information can never flow
across canals — that isolation is the governance property YARQA exists
to provide, and the tests prove canal isolation and intra-canal
causality by perturbation.

### RC1 mailbox & anti-replay
Privileged commands (`DMA_STORE`, `KV_APPEND`, `KV_COMMIT`) execute only
with a one-time authorization token: an envelope delivered via
`RC1_SEND` carrying `schema_version, target_id, command_type, bounds,
nonce, expiry_cycle, policy_digest, auth_tag` (HMAC-SHA3-256 in the sim;
hardware key in RTL). Validation rejects malformed / expired / replayed
/ unauthorized envelopes; the accepted nonce must be strictly greater
than every previously accepted nonce (monotonic counter in protected
NV). One token authorizes exactly one command. Any AP-context write to
the mailbox region raises `HardPartitionFault` and is logged as
`BYPASS_ATTEMPT` (RC1-04 analogue). DENY leaves architectural state
unchanged — fail closed.

### Receipt engine
`receipt = sha3_256(DOMAIN || prev_digest || canonical_event_bytes)`,
`DOMAIN = b"SZL-KIDS-RECEIPT-V1"`. The domain constant is **mandatory**
and resolves the estate SHA-256-vs-SHA3-256 cross-domain concern
(fork_findings §3): `vectors/receipt_domain_vector.json` pins one fixed
event with an independently computed digest plus a shell one-liner
cross-check. `verify_chain` detects truncation, reorder, replay, and
tampering; every receipt carries a gapless monotonic counter.

### KV commitment
Each 16-token × head_dim block page (zero-padded) gets
`sha3_256(DOMAIN_KV || block_bytes)`; blocks form a binary Merkle tree
(odd leaves promoted unchanged — frozen v0.1 rule). `KV_COMMIT` returns
the root; inclusion proofs generate/verify; one flipped token bit fails
the proof and changes the root.

## Layout

```
src/kids_sim/{numeric,isa,memory,engine,lgate,rc1,receipts,kvcommit,perf,conformance,cli,demo}.py
schema/kids.schema.json            # draft 2020-12, $id https://schemas.szlholdings.com/kids/v0.1
schema/khipu_package.schema.json   # .khipu package: specVersion string, byte digests,
                                   #   manifestJcsSha256 (real RFC 8785), signatures [] => *.unsigned.json
vectors/                           # checked-in golden vectors + deterministic generate_vectors.py
tests/                             # 90 tests, differential vs NumPy
```

Vector provenance note: expected values are generated **by the golden
simulator itself** (checked in, seed `0xBEE5`) and pin the executable
spec against regressions; the independent correctness proof is the
differential test suite against NumPy references, per KIDS doctrine.

Opcodes carry stable numeric codes (`isa.Opcode`); renumbering is an
ISA break.
