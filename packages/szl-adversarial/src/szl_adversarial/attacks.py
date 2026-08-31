"""The attack battery: nineteen named attacks against the real szl-receipts core.

Every attack below is a real function that takes a freshly built
:class:`AttackContext` — a temp dir holding a real Ed25519 org keypair, a
7-entry hash-chained receipt log written to disk, an in-toto statement, and a
signed DSSE envelope — and attempts to break the documented security
guarantees of ``szl-receipts`` *using only its public API*.

Result semantics:

* ``blocked=True``  — the defense held (the attack was rejected, flagged, or
  refused). Reported as ``BLOCKED``.
* ``blocked=False, limitation=False`` — the attack won. Reported as
  ``BROKEN``; fails the run and exits the CLI with status 2.
* ``blocked=False, limitation=True`` — the attack succeeded against a guard
  that is documented as out of scope for the mechanism itself (today exactly
  one: silent tail truncation with no external anchor, which no
  self-verifying log can detect). Reported as ``WARN``; does not fail the
  run, but is printed loudly.

An attack that makes the *verifier* throw is a finding, not a test bug — the
harness converts uncaught exceptions into ``blocked=False`` results with
detail ``verifier crashed``.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# These names are module attributes deliberately: tests (and future
# researchers) prove the harness is not vacuous by monkeypatching a
# deliberately weak implementation in place of the real one.
from szl_receipts import (
    NamingError,
    Outcome,
    append,
    build_receipt,
    generate_keypair,
    is_passing,
    jcs_canon_bytes,
    jcs_canon_json_text,
    keygen,
    load_private_key,
    number_to_js_str,
    pae,
    promotion_gate,
    sha256_bytes,
    sha256_hex,
    sign_bytes,
    statement,
    verify_chain,
    verify_envelope,
    verify_honest_naming,
    verify_receipt,
    write_envelope,
)
from szl_receipts.receipt import receipt_body_canonical_bytes

__all__ = [
    "ALL_ATTACKS",
    "AttackContext",
    "AttackFn",
    "AttackResult",
    "RECEIPT_PAYLOAD_TYPE",
    "make_context",
]

#: DSSE payloadType under which harness fixture envelopes sign receipts.
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.governed-action+json"

# Zero digest standing in for the harness policy document itself (the harness
# exists to attack receipts, and a self-referential policy digest would be
# circular — a fixed, honest placeholder is the truthful choice here).
_ZERO_DIGEST = "0" * 64

_POLICY: dict[str, Any] = {
    "id": "szl.adversarial-harness",
    "version": "1.0",
    "digest_sha256": _ZERO_DIGEST,
}


@dataclass
class AttackResult:
    """One attack's outcome.

    ``blocked`` is the verdict of the defense; ``limitation`` marks a
    documented out-of-scope gap whose success is a WARN, not a BROKEN.
    ``evidence`` carries the concrete forensic artifacts (finding codes,
    digests, paths) a skeptic needs to re-run the attack by hand.
    """

    name: str
    category: str
    blocked: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)
    limitation: bool = False

    def to_dict(self) -> dict[str, Any]:
        representation = "BLOCKED" if self.blocked else ("WARN" if self.limitation else "BROKEN")
        return {
            "name": self.name,
            "category": self.category,
            "blocked": self.blocked,
            "limitation": self.limitation,
            "result": representation,
            "detail": self.detail,
            "evidence": self.evidence,
        }


AttackFn = Callable[["AttackContext"], AttackResult]


@dataclass
class AttackContext:
    """A fully built, on-disk fixture the attacks get to brutalize.

    Built fresh per attack by :func:`make_context` so no attack's mutations
    leak into the next attack's fixture.
    """

    workdir: Path
    org_private_key: Any
    org_public_key: Any
    private_key_path: Path
    public_key_path: Path
    receipts: list[dict[str, Any]]
    chain: list[dict[str, Any]]
    chain_dir: Path
    receipt_files: list[Path]
    statement: dict[str, Any]
    envelope: dict[str, Any]
    envelope_path: Path


def _build_chain_receipts() -> list[dict[str, Any]]:
    """Seven receipts; the middle one (index 3) is a FAIL decision so the
    tamper attacks have a meaningful FAIL->PASS flip to attempt."""
    receipts: list[dict[str, Any]] = []
    outcomes = [
        Outcome.PASS,
        Outcome.PASS,
        Outcome.PASS,
        Outcome.FAIL,
        Outcome.PASS,
        Outcome.PASS,
        Outcome.PASS,
    ]
    for i, outcome in enumerate(outcomes, start=1):
        artifact = f"harness-fixture-{i:02d}.bin".encode()
        digest = sha256_hex(artifact)
        receipts.append(
            build_receipt(
                actor="szl-adversarial-fixture",
                action=f"fixture-build-{i}",
                policy=_POLICY,
                outcome=outcome,
                rationale=f"fixture receipt {i} for the attack harness",
                subjects=[{"name": f"fixture-{i:02d}.bin", "sha256": digest}],
                evidence=[
                    {
                        "uri": f"file://fixture/{i:02d}",
                        "sha256": digest,
                    }
                ],
            )
        )
    return receipts


def make_context(workdir: Path | None = None) -> AttackContext:
    """Build an isolated fixture: org keypair, 7-entry chain, statement, envelope.

    If *workdir* is None a temporary directory is created (caller owns its
    lifetime).
    """
    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="szl-adversarial-"))
    else:
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)

    private_key_path, public_key_path = keygen(workdir / "harness-org")
    org_private = load_private_key(private_key_path)
    org_public = org_private.public_key()

    receipts = _build_chain_receipts()
    chain: list[dict[str, Any]] = []
    for receipt in receipts:
        append(chain, receipt)

    chain_dir = workdir / "chain"
    chain_dir.mkdir(parents=True, exist_ok=True)
    for entry in chain:
        entry_path = chain_dir / f"entry-{entry['seq']:03d}.json"
        entry_path.write_text(
            json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    receipts_dir = workdir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_files: list[Path] = []
    for i, receipt in enumerate(receipts, start=1):
        path = receipts_dir / f"receipt-{i:02d}.json"
        path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        receipt_files.append(path)

    stmt = statement(
        subjects=[("fixture-chain", sha256_bytes(b"fixture-chain").hex())],
        predicate_type="https://szl.example/adversarial-fixture/v1",
        predicate={"purpose": "attack harness fixture"},
    )

    signed_payload = receipt_body_canonical_bytes(receipts[0])
    envelope = sign_bytes(signed_payload, RECEIPT_PAYLOAD_TYPE, org_private)
    envelope_path = write_envelope(workdir / "receipt-01.envelope", envelope)

    return AttackContext(
        workdir=workdir,
        org_private_key=org_private,
        org_public_key=org_public,
        private_key_path=private_key_path,
        public_key_path=public_key_path,
        receipts=receipts,
        chain=chain,
        chain_dir=chain_dir,
        receipt_files=receipt_files,
        statement=stmt,
        envelope=envelope,
        envelope_path=envelope_path,
    )


def _chain_clone(ctx: AttackContext) -> list[dict[str, Any]]:
    """Deep copy of the fixture chain so an attack can mutilate it freely."""
    return json.loads(json.dumps(ctx.chain))


def _finding_codes(report: Any) -> list[str]:
    return [str(finding.get("code", "")) for finding in report.findings]


# --------------------------------------------------------------------------
# FORGERY
# --------------------------------------------------------------------------


def attack_forge_wrong_key(ctx: AttackContext) -> AttackResult:
    """Sign a receipt with an attacker's key, present it as the org key."""
    attacker_private, _ = generate_keypair()
    payload = receipt_body_canonical_bytes(ctx.receipts[1])
    forged = sign_bytes(payload, RECEIPT_PAYLOAD_TYPE, attacker_private)
    # Presented to a verifier that trusts only the org public key:
    verdict = verify_envelope(forged, ctx.org_public_key)
    ok = verdict is False
    return AttackResult(
        name="forge-wrong-key",
        category="FORGERY",
        blocked=ok,
        detail=(
            "envelope signed with an attacker-controlled Ed25519 key was rejected "
            "when verified against the org public key"
            if ok
            else f"attacker signature VERIFIED under the org key: verify_envelope -> {verdict}"
        ),
        evidence={
            "attacker_sig_keyid": forged["signatures"][0]["keyid"],
            "verify_envelope_returned": verdict,
        },
    )


def attack_forge_fabricated_signature(ctx: AttackContext) -> AttackResult:
    """Fabricate a signature blob with no key at all."""
    import base64

    payload = receipt_body_canonical_bytes(ctx.receipts[1])
    fabricated = {
        "payload": base64.b64encode(payload).decode("ascii"),
        "payloadType": RECEIPT_PAYLOAD_TYPE,
        "signatures": [
            {
                "keyid": sha256_hex(b"harness-org"),  # claims to be the org
                "sig": base64.b64encode(os.urandom(64)).decode("ascii"),
            }
        ],
    }
    verdict = verify_envelope(fabricated, ctx.org_public_key)
    ok = verdict is False
    return AttackResult(
        name="forge-fabricated-signature",
        category="FORGERY",
        blocked=ok,
        detail=(
            "a purely fabricated 64-byte signature blob failed verification"
            if ok
            else f"random bytes VERIFIED as a signature: verify_envelope -> {verdict}"
        ),
        evidence={"verify_envelope_returned": verdict},
    )


# --------------------------------------------------------------------------
# TAMPER
# --------------------------------------------------------------------------


def _bitflip_stored_receipt(path: Path, needle_key: str) -> tuple[dict[str, Any], str]:
    """Flip one hex character of a stored receipt's *needle_key* value in the
    file bytes, keeping the JSON valid, then reload."""
    raw = path.read_bytes()
    needle = b'"%s": "' % needle_key.encode("ascii")
    start = raw.index(needle) + len(needle)
    # flip the first hex char of the digest value: 0<->1, else ->0
    original_char = raw[start : start + 1].decode("ascii")
    replacement_char = "1" if original_char == "0" else ("0" if original_char != "1" else "2")
    mutated = raw[:start] + replacement_char.encode("ascii") + raw[start + 1 :]
    return json.loads(mutated.decode("utf-8")), f"{original_char}->{replacement_char} @byte {start}"


def attack_tamper_bitflip(ctx: AttackContext) -> AttackResult:
    """Flip one byte inside a stored signed receipt payload."""
    mutated, flip_note = _bitflip_stored_receipt(ctx.receipt_files[0], "receipt_id")
    findings = verify_receipt(mutated)
    ok = len(findings) > 0
    return AttackResult(
        name="tamper-bitflip",
        category="TAMPER",
        blocked=ok,
        detail=(
            "one flipped byte in the stored receipt produced verification findings"
            if ok
            else "a bit-flipped receipt verified clean — receipt_id does not actually bind the body"
        ),
        evidence={"flip": flip_note, "findings": findings},
    )


def attack_tamper_decision_no_digest_fix(ctx: AttackContext) -> AttackResult:
    """Edit the middle entry's decision FAIL->PASS, leave digests stale."""
    chain = _chain_clone(ctx)
    entry = chain[3]  # seq 4 holds the FAIL decision
    if entry["receipt"]["decision"]["outcome"] != "FAIL":  # harness bug guard
        raise RuntimeError("fixture drifted: middle entry is no longer a FAIL decision")
    entry["receipt"]["decision"]["outcome"] = "PASS"
    report = verify_chain(chain)
    codes = _finding_codes(report)
    ok = (not report.ok) and "digest-mismatch" in codes
    return AttackResult(
        name="tamper-decision-no-digest-fix",
        category="TAMPER",
        blocked=ok,
        detail=(
            "a silent FAIL->PASS edit was caught: the entry no longer hashes to "
            "its recorded entry_digest"
            if ok
            else f"the FAIL->PASS edit went undetected by verify_chain: {codes}"
        ),
        evidence={"chain_ok": report.ok, "finding_codes": codes},
    )


def attack_tamper_recompute_digest(ctx: AttackContext) -> AttackResult:
    """Edit the middle entry AND recompute its own receipt_id + entry_digest —
    but not the successor's prev pointer."""
    import copy

    from szl_receipts import compute_receipt_id, entry_digest_for

    chain = _chain_clone(ctx)
    entry = copy.deepcopy(chain[3])
    entry["receipt"]["decision"]["outcome"] = "PASS"
    entry["receipt"]["receipt_id"] = compute_receipt_id(entry["receipt"])
    entry["entry_digest"] = entry_digest_for(entry["seq"], entry["receipt"], entry["prev"])
    chain[3] = entry
    report = verify_chain(chain)
    codes = _finding_codes(report)
    ok = (not report.ok) and "broken-prev-link" in codes
    return AttackResult(
        name="tamper-recompute-digest",
        category="TAMPER",
        blocked=ok,
        detail=(
            "even with the edited entry's own digests correctly recomputed, the "
            "successor's prev pointer no longer matches — the link break is flagged"
            if ok
            else f"re-digested tampered entry went undetected: {codes}"
        ),
        evidence={"chain_ok": report.ok, "finding_codes": codes},
    )


# --------------------------------------------------------------------------
# CANONICALIZATION
# --------------------------------------------------------------------------


def attack_canon_key_reorder(ctx: AttackContext) -> AttackResult:
    """Reorder JSON keys of a signed payload and try to (a) change what the
    signature binds, or (b) break a legitimately signed envelope in transit.

    Library contract under test: JCS makes key order semantically void, so a
    reordering cannot change the signed digest — and reserialization cannot
    invalidate a real signature. Both directions must hold consistently.
    """
    receipt = ctx.receipts[0]
    canon = receipt_body_canonical_bytes(receipt)

    shuffled = json.loads(json.dumps(receipt))
    reversed_keys: dict[str, Any] = {}
    for key in reversed(list(shuffled.keys())):
        reversed_keys[key] = shuffled[key]
    canon_shuffled = jcs_canon_bytes(reversed_keys)
    digest_same = canon_shuffled == canon

    # Sign, then rewrite the envelope's embedded payload with reordered keys
    # (as if a middlebox reserialized the JSON) and re-canonicalize: the
    # signature over canonical bytes must still verify.
    import base64

    envelope = json.loads(json.dumps(ctx.envelope))
    decoded_payload = json.loads(base64.b64decode(envelope["payload"]).decode("utf-8"))
    reordered_payload_text = json.dumps(
        {k: decoded_payload[k] for k in reversed(list(decoded_payload.keys()))},
        separators=(",", ":"),
        ensure_ascii=False,
        sort_keys=False,
    )
    envelope["payload"] = base64.b64encode(
        jcs_canon_json_text(reordered_payload_text).encode("utf-8", "surrogatepass")
    ).decode("ascii")
    still_verifies = verify_envelope(envelope, ctx.org_public_key)

    ok = digest_same and still_verifies
    return AttackResult(
        name="canon-key-reorder",
        category="CANONICALIZATION",
        blocked=ok,
        detail=(
            "JCS canonical equivalence holds in both directions: reordering keys "
            "changes neither the canonical bytes nor signature validity — the "
            "library's contract is 'key order is semantically void'"
            if ok
            else f"canonical equivalence broken: digest_same={digest_same} "
            f"still_verifies={still_verifies}"
        ),
        evidence={
            "canonical_bytes_after_reorder_identical": digest_same,
            "signature_survives_reserialization": bool(still_verifies),
        },
    )


def attack_canon_whitespace_drift(ctx: AttackContext) -> AttackResult:
    """Whitespace-only changes inside JSON text must not move canonical bytes."""
    compact = '{"a":1,"b":{"c":[2,3],"d":"x"},"e":true}'
    spaced = '{\n    "a" :  1 ,\n\t"b":\t{ "c" : [ 2 ,  3 ],\n "d" : "x" },\n   "e" : true\n}'
    canon_a = jcs_canon_json_text(compact)
    canon_b = jcs_canon_json_text(spaced)
    ok = canon_a.encode("utf-8") == canon_b.encode("utf-8") and canon_a == compact
    return AttackResult(
        name="canon-whitespace-drift",
        category="CANONICALIZATION",
        blocked=ok,
        detail=(
            f"whitespace-only edits canonicalize to byte-identical output ({canon_a!r}); no drift"
            if ok
            else f"whitespace-only edits produced different canonical bytes: "
            f"{canon_a!r} vs {canon_b!r}"
        ),
        evidence={"compact_canonical": canon_a, "spaced_canonical": canon_b},
    )


def attack_canon_unicode_equivalence(ctx: AttackContext) -> AttackResult:
    """NFC 'é' vs NFD 'e'+combining-acute must NOT silently normalize together."""
    nfc = jcs_canon_bytes({"v": "é"})
    nfd = jcs_canon_bytes({"v": "é"})
    ok = nfc != nfd
    return AttackResult(
        name="canon-unicode-equivalence",
        category="CANONICALIZATION",
        blocked=ok,
        detail=(
            "no silent unicode normalization: é (U+00E9) and e+◌́ (U+0065 U+0301) "
            "canonicalize to DISTINCT bytes, so visually identical but distinct "
            "documents cannot collide"
            if ok
            else f"silent normalization detected — NFC/NFD collide: {nfc!r} == {nfd!r}"
        ),
        evidence={
            "nfc_bytes_hex": nfc.hex(),
            "nfd_bytes_hex": nfd.hex(),
        },
    )


def attack_canon_number_format(ctx: AttackContext) -> AttackResult:
    """1 vs 1.0 vs 1e0 must canonicalize to the single fixed string '1'."""
    forms = {
        "int 1": number_to_js_str(1),
        "float 1.0": number_to_js_str(1.0),
        "text 1e0": jcs_canon_json_text('{"v": 1e0}'),
        "text 1.00": jcs_canon_json_text('{"v": 1.00}'),
    }
    expected_texts = {"text 1e0": '{"v":1}', "text 1.00": '{"v":1}'}
    ok = (
        forms["int 1"] == "1"
        and forms["float 1.0"] == "1"
        and all(forms[k] == v for k, v in expected_texts.items())
    )
    return AttackResult(
        name="canon-number-format",
        category="CANONICALIZATION",
        blocked=ok,
        detail=(
            "all spelling variants of the value 1 canonicalize to the single "
            "fixed string '1' (object form {\"v\":1}); no number-format tunnel "
            "exists"
            if ok
            else f"number canonicalization is ambiguous: {forms}"
        ),
        evidence=forms,
    )


# --------------------------------------------------------------------------
# CHAIN
# --------------------------------------------------------------------------


def attack_chain_truncate_tail_anchored(ctx: AttackContext) -> AttackResult:
    """Drop the tail; verify with the estate's published anchors present."""
    truncated = _chain_clone(ctx)[:-2]
    head = ctx.chain[-1]["entry_digest"]
    report = verify_chain(truncated, expected_entries=len(ctx.chain), expected_head=head)
    codes = _finding_codes(report)
    ok = (not report.ok) and "truncated" in codes and "head-mismatch" in codes
    return AttackResult(
        name="chain-truncate-tail-anchored",
        category="CHAIN",
        blocked=ok,
        detail=(
            "with expected_entries/expected_head anchors supplied, tail "
            "truncation raises both 'truncated' and 'head-mismatch'"
            if ok
            else f"anchored truncation went undetected: {codes}"
        ),
        evidence={"chain_ok": report.ok, "finding_codes": codes},
    )


def attack_chain_truncate_tail_no_anchor(ctx: AttackContext) -> AttackResult:
    """Drop the tail; verify with NO external anchor.

    This is the documented limitation of every self-verifying log: a shorter
    but internally consistent chain verifies cleanly. NOT counted against the
    run — reported as WARN so the estate's anchoring requirement stays loud.
    """
    truncated = _chain_clone(ctx)[:-2]
    report = verify_chain(truncated)
    limitation_visible = report.ok is True  # the honest, expected behavior
    return AttackResult(
        name="chain-truncate-tail-no-anchor",
        category="CHAIN",
        blocked=False,
        limitation=True,
        detail=(
            "LIMITATION DOCUMENTED: without an external anchor (expected_entries/"
            "expected_head), silently dropping the newest entries yields a "
            "shorter chain that verify_chain accepts — this is inherent to any "
            "self-verifying log. The estate mitigates by publishing its head "
            "digest out-of-band; always pass anchors."
            if limitation_visible
            else "unexpected: unanchored truncation was flagged as a finding — "
            "the limitation note needs updating"
        ),
        evidence={
            "chain_ok_without_anchor": report.ok,
            "truncated_length": len(truncated),
            "original_length": len(ctx.chain),
        },
    )


def attack_chain_reorder(ctx: AttackContext) -> AttackResult:
    """Swap two adjacent chain entries."""
    chain = _chain_clone(ctx)
    chain[2], chain[3] = chain[3], chain[2]
    report = verify_chain(chain)
    codes = _finding_codes(report)
    ok = (not report.ok) and "reorder" in codes
    return AttackResult(
        name="chain-reorder",
        category="CHAIN",
        blocked=ok,
        detail=(
            "swapping two entries fires the 'reorder' finding (plus broken links)"
            if ok
            else f"reordered chain verified clean: ok={report.ok}, codes={codes}"
        ),
        evidence={"chain_ok": report.ok, "finding_codes": codes},
    )


def attack_chain_replay(ctx: AttackContext) -> AttackResult:
    """Duplicate one entry verbatim inside the chain."""
    chain = _chain_clone(ctx)
    duplicate = json.loads(json.dumps(chain[4]))
    chain.insert(5, duplicate)
    report = verify_chain(chain)
    codes = _finding_codes(report)
    ok = (not report.ok) and "replay" in codes
    return AttackResult(
        name="chain-replay",
        category="CHAIN",
        blocked=ok,
        detail=(
            "a duplicated entry fires the 'replay' finding"
            if ok
            else f"replayed entry went undetected: ok={report.ok}, codes={codes}"
        ),
        evidence={"chain_ok": report.ok, "finding_codes": codes},
    )


def attack_chain_fork(ctx: AttackContext) -> AttackResult:
    """Two entries with the same seq but different digests (a forked history)."""
    import copy

    from szl_receipts import compute_receipt_id, entry_digest_for

    chain = _chain_clone(ctx)
    forked = copy.deepcopy(chain[4])
    forked["receipt"]["actor"] = "mallory-the-forker"
    forked["receipt"]["receipt_id"] = compute_receipt_id(forked["receipt"])
    forked["entry_digest"] = entry_digest_for(forked["seq"], forked["receipt"], forked["prev"])
    chain.insert(5, forked)
    report = verify_chain(chain)
    codes = _finding_codes(report)
    ok = (not report.ok) and "fork" in codes
    return AttackResult(
        name="chain-fork",
        category="CHAIN",
        blocked=ok,
        detail=(
            "a same-seq different-digest entry fires the 'fork' finding"
            if ok
            else f"forked sequence number went undetected: ok={report.ok}, codes={codes}"
        ),
        evidence={"chain_ok": report.ok, "finding_codes": codes},
    )


# --------------------------------------------------------------------------
# NAMING / DOWNGRADE
# --------------------------------------------------------------------------


def attack_naming_rename_unsigned(ctx: AttackContext) -> AttackResult:
    """Rename a SIGNED envelope to *.unsigned.json and hope it slips through."""
    target = ctx.workdir / "stolen.unsigned.json"
    shutil.copyfile(ctx.envelope_path, target)
    caught: str | None = None
    try:
        verify_honest_naming(target)
    except NamingError as exc:
        caught = str(exc)
    ok = caught is not None
    return AttackResult(
        name="naming-rename-unsigned",
        category="NAMING/DOWNGRADE",
        blocked=ok,
        detail=(
            "a signed envelope renamed to *.unsigned.json raises NamingError — "
            "the name cannot lie about the signature state"
            if ok
            else "signed envelope under an unsigned name passed naming verification"
        ),
        evidence={"naming_error": caught},
    )


def attack_naming_strip_signatures(ctx: AttackContext) -> AttackResult:
    """Strip the signatures from a signed envelope and present it as signed
    (empty array / missing key) or falsely-unsigned."""
    envelope = json.loads(json.dumps(ctx.envelope))
    downgraded = {**envelope, "signatures": []}
    signed_name_path = ctx.workdir / "downgraded.json"
    signed_name_path.write_text(json.dumps(downgraded, indent=2), encoding="utf-8")

    caught_empty: str | None = None
    try:
        verify_honest_naming(signed_name_path)
    except NamingError as exc:
        caught_empty = str(exc)

    keyless = {k: v for k, v in envelope.items() if k != "signatures"}
    keyless_path = ctx.workdir / "keyless.unsigned.json"
    keyless_path.write_text(json.dumps(keyless, indent=2), encoding="utf-8")
    caught_keyless: str | None = None
    try:
        verify_honest_naming(keyless_path)
    except NamingError as exc:
        caught_keyless = str(exc)

    ok = caught_empty is not None and caught_keyless is not None
    return AttackResult(
        name="naming-strip-signatures",
        category="NAMING/DOWNGRADE",
        blocked=ok,
        detail=(
            "both downgrade shapes are rejected: an empty signatures array under "
            "a signed name, and a signatures-less file under any name, raise "
            "NamingError ('an empty signatures array is not a signature')"
            if ok
            else f"downgrade slipped through: empty={caught_empty!r} keyless={caught_keyless!r}"
        ),
        evidence={
            "empty_array_error": caught_empty,
            "missing_key_error": caught_keyless,
        },
    )


def attack_naming_cross_envelope_confusion(ctx: AttackContext) -> AttackResult:
    """Swap the payload of one signed envelope with another signed receipt's
    payload — cross-envelope confusion."""
    import base64

    other_payload = receipt_body_canonical_bytes(ctx.receipts[1])
    other_envelope = sign_bytes(other_payload, RECEIPT_PAYLOAD_TYPE, ctx.org_private_key)

    confused = json.loads(json.dumps(ctx.envelope))
    confused["payload"] = other_envelope["payload"]  # payload from envelope B
    verdict = verify_envelope(confused, ctx.org_public_key)

    reverse_confused = json.loads(json.dumps(other_envelope))
    reverse_confused["payload"] = ctx.envelope["payload"]
    reverse_verdict = verify_envelope(reverse_confused, ctx.org_public_key)

    ok = verdict is False and reverse_verdict is False
    return AttackResult(
        name="naming-cross-envelope-confusion",
        category="NAMING/DOWNGRADE",
        blocked=ok,
        detail=(
            "both grafted envelopes fail verification — a signature cannot be "
            "transplanted onto a different payload"
            if ok
            else f"cross-envelope payload swap VERIFIED: ({verdict!r}, {reverse_verdict!r})"
        ),
        evidence={
            "swap_ab_verified": verdict,
            "swap_ba_verified": reverse_verdict,
            "payload_b_prefix_b64": base64.b64encode(other_payload[:16]).decode("ascii"),
        },
    )


# --------------------------------------------------------------------------
# PAE
# --------------------------------------------------------------------------


def attack_pae_prefix_confusion(ctx: AttackContext) -> AttackResult:
    """Craft (payloadType, payload) pairs whose naive concatenation collides;
    PAE must keep them distinct via length prefixes."""
    pairs_colliding_naively = [
        ((b"ab", b"c"), (b"a", b"bc")),
        ((b"DSSEv1 ", b"payload"), (b"DSSEv1", b" payload")),
        ((b"statement", b"{}"), (b"statement{", b"}")),
    ]
    collisions: list[dict[str, str]] = []
    for (t1, p1), (t2, p2) in pairs_colliding_naively:
        if t1 + p1 != t2 + p2:  # harness bug guard: pairs must collide naively
            raise RuntimeError(f"test pairs do not collide naively: {(t1, p1, t2, p2)!r}")
        if pae(t1, p1) == pae(t2, p2):
            collisions.append({"pair_a": repr((t1, p1)), "pair_b": repr((t2, p2))})
    ok = not collisions
    return AttackResult(
        name="pae-prefix-confusion",
        category="PAE",
        blocked=ok,
        detail=(
            "every tested (payloadType, payload) pair whose raw concatenation "
            "collides encodes to DISTINCT PAE bytes — length prefixes fix the "
            "field boundaries, so no type/payload smear exists"
            if ok
            else f"PAE ambiguity found — distinct logical pairs encode identically: {collisions}"
        ),
        evidence={
            "example_pae_a": repr(pae(b"ab", b"c")),
            "example_pae_b": repr(pae(b"a", b"bc")),
            "collisions_found": collisions,
        },
        # ctx unused beyond signature uniformity; keep one evidence tie to the
        # org payload type for the report reader.
    )


# --------------------------------------------------------------------------
# OUTCOME
# --------------------------------------------------------------------------


def attack_outcome_promote_unknown(ctx: AttackContext) -> AttackResult:
    """Attempt to promote with outcome UNKNOWN."""
    passing = is_passing(Outcome.UNKNOWN)
    allowed, rationale = promotion_gate(Outcome.UNKNOWN)
    ok = passing is False and allowed is False
    return AttackResult(
        name="outcome-promote-unknown",
        category="OUTCOME",
        blocked=ok,
        detail=(
            f"is_passing(UNKNOWN) is False and promotion_gate refuses: {rationale!r}"
            if ok
            else f"UNKNOWN was treated as promotable: is_passing={passing}, "
            f"gate=({allowed}, {rationale!r})"
        ),
        evidence={"is_passing": passing, "gate_allowed": allowed, "gate_reason": rationale},
    )


def attack_outcome_garbage_schema(ctx: AttackContext) -> AttackResult:
    """Smuggle 'unknown' lowercase / garbage outcomes past the receipt schema."""
    cases: dict[str, list[str]] = {}
    for bad in ("unknown", "green", "PASS ", "Pass", " PASS", ""):
        mutated = json.loads(json.dumps(ctx.receipts[0]))
        mutated["decision"]["outcome"] = bad
        cases[repr(bad)] = verify_receipt(mutated)
    ok = all(findings for findings in cases.values())
    return AttackResult(
        name="outcome-garbage-schema",
        category="OUTCOME",
        blocked=ok,
        detail=(
            "every off-vocabulary outcome string (lowercase, whitespace-padded, "
            "garbage, empty) is rejected by verify_receipt findings"
            if ok
            else f"off-vocabulary outcomes accepted: {[k for k, v in cases.items() if not v]}"
        ),
        evidence=cases,
    )


#: The full attack battery, in execution order. Order is semantic: forgery
#: first (the crown jewels), outcome last (the gate everything feeds).
ALL_ATTACKS: list[AttackFn] = [
    attack_forge_wrong_key,
    attack_forge_fabricated_signature,
    attack_tamper_bitflip,
    attack_tamper_decision_no_digest_fix,
    attack_tamper_recompute_digest,
    attack_canon_key_reorder,
    attack_canon_whitespace_drift,
    attack_canon_unicode_equivalence,
    attack_canon_number_format,
    attack_chain_truncate_tail_anchored,
    attack_chain_truncate_tail_no_anchor,
    attack_chain_reorder,
    attack_chain_replay,
    attack_chain_fork,
    attack_naming_rename_unsigned,
    attack_naming_strip_signatures,
    attack_naming_cross_envelope_confusion,
    attack_pae_prefix_confusion,
    attack_outcome_promote_unknown,
    attack_outcome_garbage_schema,
]
