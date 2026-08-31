"""The harness against the real library — and the non-vacuity proof.

The second half is the important part: a security harness whose pass verdict
cannot be made to fail is decor, not defense. We prove the harness is honest
by swapping the real ``verify_envelope`` import in the attacks module for a
deliberately weak toy verifier ("everything verifies") and showing the run
then reports the forgery attacks as BROKEN and fails.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import szl_adversarial.attacks as attacks_module
from szl_adversarial.attacks import AttackResult, make_context
from szl_adversarial.harness import run_all


def test_run_all_passes_on_real_library():
    result = run_all()
    assert result.passed is True
    assert result.total == 20
    assert result.blocked_count == 19
    assert result.limitation_count == 1
    assert result.broken == []
    assert len(result.warnings) == 1
    assert result.verdict_line() == "receipt chain resisted 19/19 non-limitation attacks"


def test_run_all_isolates_fixtures():
    """Each attack must get a fresh fixture workdir — no cross-contamination."""
    seen_dirs: list[Path] = []
    seen_pubkeys: set[bytes] = set()

    def recording_factory():
        ctx = make_context()
        seen_dirs.append(ctx.workdir)
        seen_pubkeys.add(ctx.public_key_path.read_bytes())
        return ctx

    try:
        result = run_all(ctx_factory=recording_factory, cleanup=False)
        assert result.passed is True
        assert len(seen_dirs) == result.total
        assert len(set(seen_dirs)) == result.total, "workdirs must be distinct"
        assert len(seen_pubkeys) == result.total, "fresh org keypair per attack"
        for workdir in seen_dirs:
            assert (workdir / "chain" / "entry-001.json").is_file()
            assert (workdir / "receipt-01.envelope.json").is_file()
    finally:
        for workdir in seen_dirs:
            shutil.rmtree(workdir, ignore_errors=True)


def test_crashed_verifier_is_a_finding_not_a_crash():
    """An attack that makes the 'verifier' throw must surface as BROKEN."""

    def explosive_attack(ctx):  # pragma: no cover - body runs inside harness
        raise RuntimeError("simulated verifier explosion")

    def honing_attack(ctx):
        return AttackResult(name="honing", category="OUTCOME", blocked=True, detail="held")

    result = run_all(attacks=[explosive_attack, honing_attack])
    assert result.passed is False
    assert result.total == 2
    crash = result.results[0]
    assert crash.blocked is False
    assert crash.limitation is False
    assert "verifier crashed" in crash.detail
    assert crash.evidence["exception"] == "RuntimeError"
    assert "RuntimeError: simulated verifier explosion" in crash.evidence["traceback"]
    assert result.results[1].blocked is True


def test_weak_toy_verifier_makes_harness_fail(monkeypatch):
    """THE non-vacuity proof: replace the real verify_envelope with a toy
    verifier that rubber-stamps everything, and the forgery attacks must WIN.
    If this test passes, the harness's pass verdict on the real library means
    something."""
    monkeypatch.setattr(attacks_module, "verify_envelope", lambda envelope, pubkey: True)
    result = run_all(
        attacks=[
            attacks_module.attack_forge_wrong_key,
            attacks_module.attack_forge_fabricated_signature,
        ]
    )
    assert result.passed is False
    assert len(result.broken) == 2
    assert {r.name for r in result.broken} == {
        "forge-wrong-key",
        "forge-fabricated-signature",
    }
    assert "receipt chain FAILED" in result.verdict_line()
    assert "forge-wrong-key" in result.verdict_line()


def test_all_blocked_registry_passes_and_counts():
    """Sanity: an all-blocked registry passes with correct counts."""

    def attack_a(ctx):
        return AttackResult(name="a", category="FORGERY", blocked=True, detail="held")

    def attack_b(ctx):
        return AttackResult(
            name="b", category="CHAIN", blocked=False, limitation=True, detail="warn"
        )

    result = run_all(attacks=[attack_a, attack_b])
    assert result.passed is True
    assert result.total == 2
    assert result.blocked_count == 1
    assert result.limitation_count == 1
    assert result.warnings and result.warnings[0].startswith("WARN: b")
