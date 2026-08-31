# szl-adversarial

**The public attack harness for the SZL receipt chain.**

A security claim that has never been attacked is not a claim — it is a hope.
`szl-receipts` ships with a receipt schema, a hash-chained audit log, DSSE
signatures over RFC 8785 canonical JSON, honest-naming enforcement, and a
closed outcome vocabulary, and it *asserts* that these mechanisms resist
forgery, tampering, canonicalization drift, chain surgery, downgrade renames,
type confusion, and gate bypass. This package is where that assertion gets
hurt, in public, against the **real installed library** — no mocks, no
re-implementations, no participation trophies.

## The claim under attack

> Given only the public API of `szl-receipts` and an attacker who can
> generate their own keys, fabricate arbitrary bytes, rewrite any stored
> file, reorder/duplicate/truncate/fork the chain, rename artifacts, and
> craft malicious JSON — but who does **not** possess the org's Ed25519
> private key and cannot break sha256 or Ed25519 — the attacker cannot:
>
> 1. make a forged or tampered artifact verify as authentic,
> 2. mutate a receipt or chain entry without detection,
> 3. smear two different logical JSON documents into one canonical byte
>    string (or vice versa),
> 4. truncate, reorder, replay, or fork the chain silently,
> 5. rename their way around the unsigned-artifact convention,
> 6. confuse one DSSE `(payloadType, payload)` pair for another, or
> 7. promote an artifact whose outcome is `UNKNOWN` (or garbage).

Nineteen attacks, each a named function in `src/szl_adversarial/attacks.py`,
probe exactly these seven guarantees. The harness executes every attack in an
isolated, freshly generated fixture (new keypair, new 7-entry signed chain,
new in-toto statement, new DSSE envelope per run, all in a temp dir) and
publishes the outcome **either way**.

## How to run

```bash
pip install -e packages/szl-receipts -e packages/szl-adversarial

# Full run: writes ATTACK_REPORT.md + attack-report envelope + results JSON.
python -m szl_adversarial run --out /tmp/attack_out

# Machine-readable to stdout; still writes the report to --out.
python -m szl_adversarial run --out /tmp/attack_out --json

# Sign the harness's self-receipt with an operator key (honest name
# becomes attack-report.json instead of attack-report.unsigned.json).
python -m szl_adversarial run --out /tmp/attack_out --sign-with keys/operator.pem
```

Exit codes: **0** iff every non-limitation attack was blocked, **2** if any
attack succeeded (or crashed the verifier — a crash *is* a successful
attack). The report names exactly which attack won.

## Results table semantics

| Result    | Meaning |
|-----------|---------|
| `BLOCKED` | The defense held: the verifier rejected, flagged, or refused the attack. Counts toward the pass. |
| `BROKEN`  | The attack won: forged bytes verified, a mutation went undetected, a gate opened, **or the verifier crashed**. Counts against the claim; the run exits 2. |
| `WARN`    | A documented limitation of the security model itself (e.g. silent tail truncation without an external anchor — detectable *only* against an out-of-band head digest). Does not fail the run; printed loudly. |

A run **passes** iff every non-limitation attack is `BLOCKED`. The verdict
line reads either

> receipt chain resisted N/N non-limitation attacks

or the honest list of which attacks succeeded. The harness then **receipts
its own result**: `ATTACK_REPORT.md` is hashed (sha256 over its bytes) into a
`GovernedAction/v1` receipt bound to the attacking library version, written
through `szl_receipts.write_envelope` — honestly named
`attack-report.unsigned.json` unless `--sign-with` provides a key. A harness
that will not attest to its own output has no business auditing anyone
else's.

## If you break this, we publish the break

The report is generated from live results and is publishable *as produced*
in both directions. If the table shows a `BROKEN` row, the correct response
is not to edit the table — it is to fix `szl-receipts`, bump its version, and
re-run. The self-receipt binds the exact `szl-receipts` version under test,
so a fixed core and a broken core can never share an attestation.

## Responsible disclosure

This harness attacks the estate's **own** receipt core in an isolated
sandbox. It exists so weaknesses are found here, on the record, before an
adversary finds them in production. If you find a *new* break the harness
misses — a twentieth attack — report it privately to the SZL Holdings
security contact first; we will reproduce it, add it to `attacks.py` as a
named function, fix the core, and credit the reporter (or their anonymity,
at their choice) in the published report. Do not open a public issue with an
exploitable proof before the fix lands.
