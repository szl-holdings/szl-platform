"""The ATTACK_REPORT and the harness's self-receipt.

The report is a public document: it must carry the verdict line, name every
attack with a BLOCKED/BROKEN/WARN mark, and its self-receipt must be a real
GovernedAction/v1 receipt binding the report's sha256 — honestly named
unsigned by default, honestly signed when a key is supplied.
"""

from __future__ import annotations

import base64
import json

from szl_adversarial.attacks import AttackResult
from szl_adversarial.harness import HarnessResult, run_all
from szl_adversarial.report import render_markdown, verdict_outcome, write_report
from szl_receipts import (
    keygen,
    load_public_key,
    sha256_file,
    unwrap_envelope,
    verify_envelope,
    verify_honest_naming,
    verify_receipt,
)


def _tiny_harness() -> HarnessResult:
    results = [
        AttackResult(
            name="forge-wrong-key",
            category="FORGERY",
            blocked=True,
            detail="rejected by the real verifier",
            evidence={"verify_envelope_returned": False},
        ),
        AttackResult(
            name="chain-truncate-tail-no-anchor",
            category="CHAIN",
            blocked=False,
            limitation=True,
            detail="LIMITATION DOCUMENTED: needs an external anchor",
        ),
        AttackResult(
            name="canon-number-format",
            category="CANONICALIZATION",
            blocked=True,
            detail="1 == 1.0 == 1e0 canonical form",
        ),
    ]
    return HarnessResult(
        results=results,
        passed=True,
        total=3,
        warnings=["WARN chain-truncate-tail-no-anchor: ..."],
    )


def test_markdown_contains_verdict_table_and_marks():
    md = render_markdown(_tiny_harness())
    assert md.startswith("# SZL Receipt Chain — ATTACK REPORT")
    assert "receipt chain resisted 2/2 non-limitation attacks" in md
    assert "**BLOCKED**" in md and "**WARN**" in md
    assert "forge-wrong-key" in md
    assert "chain-truncate-tail-no-anchor" in md
    assert "Documented limitations (WARN)" in md
    # A pipe in a detail string must not break the table.
    nasty = AttackResult(name="nasty", category="PAE", blocked=True, detail="a | b | c")
    md2 = render_markdown(HarnessResult(results=[nasty], passed=True, total=1))
    assert "a \\| b \\| c" in md2


def test_markdown_names_the_winning_attack_on_failure():
    broken = AttackResult(
        name="forge-wrong-key",
        category="FORGERY",
        blocked=False,
        detail="the toy verifier said yes",
    )
    md = render_markdown(HarnessResult(results=[broken], passed=False, total=1))
    assert "receipt chain FAILED" in md
    assert "**BROKEN**" in md
    assert "forge-wrong-key" in md and "the toy verifier said yes" in md


def test_verdict_outcome_maps_pass_and_fail():
    assert verdict_outcome(_tiny_harness()).value == "PASS"
    broken = AttackResult(name="x", category="PAE", blocked=False, detail="won")
    assert verdict_outcome(HarnessResult(results=[broken], passed=False, total=1)).value == "FAIL"


def test_write_report_produces_unsigned_honest_receipt(tmp_path):
    paths = write_report(_tiny_harness(), tmp_path / "out")
    assert paths["report"].name == "ATTACK_REPORT.md"
    assert paths["report"].is_file()
    # No key provided -> the receipt MUST be honestly named unsigned.
    assert paths["receipt"].name == "attack-report.unsigned.json"
    verify_honest_naming(paths["receipt"])  # must not raise

    envelope = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    payload, payload_type, signatures = unwrap_envelope(envelope)
    assert signatures == []
    assert payload_type == "application/vnd.szl.governed-action+json"
    receipt = json.loads(payload)
    assert verify_receipt(receipt) == []
    assert receipt["decision"]["outcome"] == "PASS"
    assert receipt["subjects"][0]["name"] == "ATTACK_REPORT.md"
    # The receipt binds the report's BYTES:
    assert receipt["subjects"][0]["sha256"] == sha256_file(paths["report"])


def test_write_report_signed_variant_verifies(tmp_path):
    key_priv, key_pub = keygen(tmp_path / "operator")
    paths = write_report(_tiny_harness(), tmp_path / "out", sign_with=key_priv)
    assert paths["receipt"].name == "attack-report.json"
    verify_honest_naming(paths["receipt"])
    envelope = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    assert verify_envelope(envelope, load_public_key(key_pub)) is True
    payload, _, _ = unwrap_envelope(envelope)
    receipt = json.loads(payload)
    assert verify_receipt(receipt) == []


def test_write_report_failure_run_records_fail_outcome(tmp_path):
    broken = AttackResult(
        name="forge-wrong-key",
        category="FORGERY",
        blocked=False,
        detail="attack won in this fixture",
    )
    harness = HarnessResult(results=[broken], passed=False, total=1)
    paths = write_report(harness, tmp_path / "out")
    envelope = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    payload = base64.b64decode(envelope["payload"])
    receipt = json.loads(payload)
    assert receipt["decision"]["outcome"] == "FAIL"
    assert "forge-wrong-key" in receipt["decision"]["rationale"]
    assert "receipt chain FAILED" in paths["report"].read_text(encoding="utf-8")


def test_full_run_report_mentions_every_attack(tmp_path):
    """End-to-end: the real battery's report lists all 20 attack names."""
    result = run_all()
    md = render_markdown(result)
    for attack in result.results:
        assert attack.name in md
    assert "receipt chain resisted 19/19 non-limitation attacks" in md
