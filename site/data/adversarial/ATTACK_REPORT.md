# SZL Receipt Chain — ATTACK REPORT

- **Generated at (UTC):** 2026-08-31T18:58:38.089836Z
- **szl-receipts version under attack:** 14.0.0
- **Run duration:** 0.08s across 20 attacks, each against an isolated fresh fixture
- **Harness self-assessment:** PASS

## Verdict

**receipt chain resisted 19/19 non-limitation attacks.**

Every non-limitation attack was blocked by the real `szl-receipts` 14.0.0 library — no mocks, no toy verifiers, no fixture reuse between attacks.

## Results

| # | Attack | Category | Result | Detail |
|---|--------|----------|--------|--------|
| 1 | `forge-wrong-key` | FORGERY | **BLOCKED** | envelope signed with an attacker-controlled Ed25519 key was rejected when verified against the org public key |
| 2 | `forge-fabricated-signature` | FORGERY | **BLOCKED** | a purely fabricated 64-byte signature blob failed verification |
| 3 | `tamper-bitflip` | TAMPER | **BLOCKED** | one flipped byte in the stored receipt produced verification findings |
| 4 | `tamper-decision-no-digest-fix` | TAMPER | **BLOCKED** | a silent FAIL->PASS edit was caught: the entry no longer hashes to its recorded entry_digest |
| 5 | `tamper-recompute-digest` | TAMPER | **BLOCKED** | even with the edited entry's own digests correctly recomputed, the successor's prev pointer no longer matches — the link break is flagged |
| 6 | `canon-key-reorder` | CANONICALIZATION | **BLOCKED** | JCS canonical equivalence holds in both directions: reordering keys changes neither the canonical bytes nor signature validity — the library's contract is 'key order is semantically void' |
| 7 | `canon-whitespace-drift` | CANONICALIZATION | **BLOCKED** | whitespace-only edits canonicalize to byte-identical output ('{"a":1,"b":{"c":[2,3],"d":"x"},"e":true}'); no drift |
| 8 | `canon-unicode-equivalence` | CANONICALIZATION | **BLOCKED** | no silent unicode normalization: é (U+00E9) and e+◌́ (U+0065 U+0301) canonicalize to DISTINCT bytes, so visually identical but distinct documents cannot collide |
| 9 | `canon-number-format` | CANONICALIZATION | **BLOCKED** | all spelling variants of the value 1 canonicalize to the single fixed string '1' (object form {"v":1}); no number-format tunnel exists |
| 10 | `chain-truncate-tail-anchored` | CHAIN | **BLOCKED** | with expected_entries/expected_head anchors supplied, tail truncation raises both 'truncated' and 'head-mismatch' |
| 11 | `chain-truncate-tail-no-anchor` | CHAIN | **WARN** | LIMITATION DOCUMENTED: without an external anchor (expected_entries/expected_head), silently dropping the newest entries yields a shorter chain that verify_chain accepts — this is inherent to any self-verifying log. The estate mitigates by publishing its head digest out-of-band; always pass anchors. |
| 12 | `chain-reorder` | CHAIN | **BLOCKED** | swapping two entries fires the 'reorder' finding (plus broken links) |
| 13 | `chain-replay` | CHAIN | **BLOCKED** | a duplicated entry fires the 'replay' finding |
| 14 | `chain-fork` | CHAIN | **BLOCKED** | a same-seq different-digest entry fires the 'fork' finding |
| 15 | `naming-rename-unsigned` | NAMING/DOWNGRADE | **BLOCKED** | a signed envelope renamed to *.unsigned.json raises NamingError — the name cannot lie about the signature state |
| 16 | `naming-strip-signatures` | NAMING/DOWNGRADE | **BLOCKED** | both downgrade shapes are rejected: an empty signatures array under a signed name, and a signatures-less file under any name, raise NamingError ('an empty signatures array is not a signature') |
| 17 | `naming-cross-envelope-confusion` | NAMING/DOWNGRADE | **BLOCKED** | both grafted envelopes fail verification — a signature cannot be transplanted onto a different payload |
| 18 | `pae-prefix-confusion` | PAE | **BLOCKED** | every tested (payloadType, payload) pair whose raw concatenation collides encodes to DISTINCT PAE bytes — length prefixes fix the field boundaries, so no type/payload smear exists |
| 19 | `outcome-promote-unknown` | OUTCOME | **BLOCKED** | is_passing(UNKNOWN) is False and promotion_gate refuses: 'UNKNOWN: no verdict recorded; UNKNOWN is never promotable' |
| 20 | `outcome-garbage-schema` | OUTCOME | **BLOCKED** | every off-vocabulary outcome string (lowercase, whitespace-padded, garbage, empty) is rejected by verify_receipt findings |

### Result semantics

- **BLOCKED** — the defense held; counts toward the pass.
- **BROKEN** — the attack won (or the verifier crashed, which *is* a successful attack); fails the run.
- **WARN** — a documented limitation of the security model itself; does not fail the run, and must never silently disappear from this table.

## Documented limitations (WARN)

- WARN: chain-truncate-tail-no-anchor: LIMITATION DOCUMENTED: without an external anchor (expected_entries/expected_head), silently dropping the newest entries yields a shorter chain that verify_chain accepts — this is inherent to any self-verifying log. The estate mitigates by publishing its head digest out-of-band; always pass anchors.

## Self-receipt

This file's bytes are hashed (sha256) and bound as the subject of a `GovernedAction/v1` receipt written by the harness itself via `szl_receipts.write_envelope`, honestly named `attack-report.unsigned.json` (or signed when the run is given an operator key via `--sign-with`). The receipt records the verdict outcome (PASS) and pins the `szl-receipts` version under attack, so this report can itself be verified with the same library it attacks.
