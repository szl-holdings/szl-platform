"""Each attack, asserted individually against the real szl-receipts core.

These tests are the fine-grained contract: every attack in the battery must
be BLOCKED by the real library, except the single documented limitation
(silent tail truncation without an external anchor), which must surface as a
limitation WARN — never as a silent pass, never as a failure of the run.
"""

from __future__ import annotations

import pytest
from szl_adversarial import attacks
from szl_adversarial.attacks import ALL_ATTACKS, make_context


@pytest.fixture()
def ctx(tmp_path):
    return make_context(tmp_path / "fixture")


# -- FORGERY ---------------------------------------------------------------


def test_forge_wrong_key_blocked(ctx):
    result = attacks.attack_forge_wrong_key(ctx)
    assert result.blocked is True
    assert result.evidence["verify_envelope_returned"] is False


def test_forge_fabricated_signature_blocked(ctx):
    result = attacks.attack_forge_fabricated_signature(ctx)
    assert result.blocked is True
    assert result.evidence["verify_envelope_returned"] is False


# -- TAMPER ----------------------------------------------------------------


def test_tamper_bitflip_blocked(ctx):
    result = attacks.attack_tamper_bitflip(ctx)
    assert result.blocked is True
    assert result.evidence["findings"], "bitflip must produce findings"


def test_tamper_decision_no_digest_fix_blocked(ctx):
    result = attacks.attack_tamper_decision_no_digest_fix(ctx)
    assert result.blocked is True
    assert result.evidence["chain_ok"] is False
    assert "digest-mismatch" in result.evidence["finding_codes"]


def test_tamper_recompute_digest_blocked(ctx):
    result = attacks.attack_tamper_recompute_digest(ctx)
    assert result.blocked is True
    assert result.evidence["chain_ok"] is False
    assert "broken-prev-link" in result.evidence["finding_codes"]


# -- CANONICALIZATION ------------------------------------------------------


def test_canon_key_reorder_blocked(ctx):
    """Library contract: key order is semantically void — reorder changes
    neither canonical bytes nor signature validity."""
    result = attacks.attack_canon_key_reorder(ctx)
    assert result.blocked is True
    assert result.evidence["canonical_bytes_after_reorder_identical"] is True
    assert result.evidence["signature_survives_reserialization"] is True


def test_canon_whitespace_drift_blocked(ctx):
    result = attacks.attack_canon_whitespace_drift(ctx)
    assert result.blocked is True
    assert result.evidence["compact_canonical"] == result.evidence["spaced_canonical"]


def test_canon_unicode_equivalence_blocked(ctx):
    """NFC é and NFD e+combining-acute must NOT silently normalize together."""
    result = attacks.attack_canon_unicode_equivalence(ctx)
    assert result.blocked is True
    assert result.evidence["nfc_bytes_hex"] != result.evidence["nfd_bytes_hex"]


def test_canon_number_format_blocked(ctx):
    result = attacks.attack_canon_number_format(ctx)
    assert result.blocked is True
    assert result.evidence["int 1"] == "1"
    assert result.evidence["float 1.0"] == "1"
    assert result.evidence["text 1e0"] == '{"v":1}'
    assert result.evidence["text 1.00"] == '{"v":1}'


# -- CHAIN -----------------------------------------------------------------


def test_chain_truncate_tail_anchored_blocked(ctx):
    result = attacks.attack_chain_truncate_tail_anchored(ctx)
    assert result.blocked is True
    codes = result.evidence["finding_codes"]
    assert "truncated" in codes
    assert "head-mismatch" in codes


def test_chain_truncate_tail_no_anchor_is_documented_limitation(ctx):
    """Without an external anchor, silent tail truncation succeeds — that is
    the documented limitation of every self-verifying log, reported WARN."""
    result = attacks.attack_chain_truncate_tail_no_anchor(ctx)
    assert result.blocked is False
    assert result.limitation is True
    assert result.evidence["chain_ok_without_anchor"] is True
    assert "LIMITATION DOCUMENTED" in result.detail


def test_chain_reorder_blocked(ctx):
    result = attacks.attack_chain_reorder(ctx)
    assert result.blocked is True
    assert "reorder" in result.evidence["finding_codes"]


def test_chain_replay_blocked(ctx):
    result = attacks.attack_chain_replay(ctx)
    assert result.blocked is True
    assert "replay" in result.evidence["finding_codes"]


def test_chain_fork_blocked(ctx):
    result = attacks.attack_chain_fork(ctx)
    assert result.blocked is True
    assert "fork" in result.evidence["finding_codes"]


# -- NAMING / DOWNGRADE ----------------------------------------------------


def test_naming_rename_unsigned_blocked(ctx):
    result = attacks.attack_naming_rename_unsigned(ctx)
    assert result.blocked is True
    assert result.evidence["naming_error"] is not None


def test_naming_strip_signatures_blocked(ctx):
    result = attacks.attack_naming_strip_signatures(ctx)
    assert result.blocked is True
    assert result.evidence["empty_array_error"] is not None
    assert result.evidence["missing_key_error"] is not None


def test_naming_cross_envelope_confusion_blocked(ctx):
    result = attacks.attack_naming_cross_envelope_confusion(ctx)
    assert result.blocked is True
    assert result.evidence["swap_ab_verified"] is False
    assert result.evidence["swap_ba_verified"] is False


# -- PAE -------------------------------------------------------------------


def test_pae_prefix_confusion_blocked(ctx):
    result = attacks.attack_pae_prefix_confusion(ctx)
    assert result.blocked is True
    assert result.evidence["collisions_found"] == []
    assert result.evidence["example_pae_a"] != result.evidence["example_pae_b"]


# -- OUTCOME ---------------------------------------------------------------


def test_outcome_promote_unknown_blocked(ctx):
    result = attacks.attack_outcome_promote_unknown(ctx)
    assert result.blocked is True
    assert result.evidence["is_passing"] is False
    assert result.evidence["gate_allowed"] is False


def test_outcome_garbage_schema_blocked(ctx):
    result = attacks.attack_outcome_garbage_schema(ctx)
    assert result.blocked is True
    assert all(result.evidence.values()), "every garbage outcome must produce findings"


# -- BATTERY SHAPE ----------------------------------------------------------


def test_battery_has_unique_names_and_real_categories():
    names = [fn.__name__ for fn in ALL_ATTACKS]
    assert len(names) == len(set(names)) == 20
    assert all(name.startswith("attack_") for name in names)


def test_battery_covers_all_seven_categories(ctx):
    categories = {fn(ctx).category for fn in ALL_ATTACKS}
    assert categories == {
        "FORGERY",
        "TAMPER",
        "CANONICALIZATION",
        "CHAIN",
        "NAMING/DOWNGRADE",
        "PAE",
        "OUTCOME",
    }
