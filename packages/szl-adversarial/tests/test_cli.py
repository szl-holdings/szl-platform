"""CLI contract: exit 0 when the claim holds, exit 2 when an attack wins.

The exit-2 path is proven with a deliberately weak toy verifier
(monkeypatched into the attacks module): if the CLI can be made to report
failure by weakening the library it attacks, its success exit *means* the
library actually held.
"""

from __future__ import annotations

import io
import json

import szl_adversarial.attacks as attacks_module
from szl_adversarial.cli import main


def test_cli_run_exit_0_on_real_library(tmp_path):
    out = tmp_path / "attack_out"
    stdout = io.StringIO()
    exit_code = main(["run", "--out", str(out)], stdout=stdout)
    assert exit_code == 0

    printed = stdout.getvalue()
    assert "receipt chain resisted 19/19 non-limitation attacks" in printed
    assert "WARN: chain-truncate-tail-no-anchor" in printed

    report = out / "ATTACK_REPORT.md"
    assert report.is_file()
    assert "receipt chain resisted 19/19 non-limitation attacks" in report.read_text(
        encoding="utf-8"
    )
    # Unsigned by default -> honest unsigned naming.
    assert (out / "attack-report.unsigned.json").is_file()
    assert not (out / "attack-report.json").exists()


def test_cli_run_json_flag_writes_results_and_prints_json(tmp_path):
    out = tmp_path / "attack_out"
    stdout = io.StringIO()
    exit_code = main(["run", "--out", str(out), "--json"], stdout=stdout)
    assert exit_code == 0
    results_file = out / "results.json"
    assert results_file.is_file()
    on_disk = json.loads(results_file.read_text(encoding="utf-8"))
    assert on_disk["passed"] is True
    assert on_disk["total"] == 20
    assert len(on_disk["results"]) == 20
    # The first stdout line is machine-readable JSON with the same verdict.
    printed_json = json.loads(stdout.getvalue().splitlines()[0])
    assert printed_json["verdict"] == on_disk["verdict"]


def test_cli_run_signed_self_receipt(tmp_path, tmp_path_factory):
    from szl_receipts import keygen, load_public_key, verify_envelope, verify_honest_naming

    keys_dir = tmp_path_factory.mktemp("keys")
    priv, pub = keygen(keys_dir / "operator")
    out = tmp_path / "attack_out"
    stdout = io.StringIO()
    exit_code = main(["run", "--out", str(out), "--sign-with", str(priv)], stdout=stdout)
    assert exit_code == 0
    receipt_path = out / "attack-report.json"
    assert receipt_path.is_file()
    verify_honest_naming(receipt_path)
    envelope = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert verify_envelope(envelope, load_public_key(pub)) is True


def test_cli_missing_key_is_usage_error(tmp_path):
    exit_code = main(
        ["run", "--out", str(tmp_path / "out"), "--sign-with", "/no/such/key.pem"],
        stdout=io.StringIO(),
    )
    assert exit_code == 3


def test_cli_exit_2_when_an_attack_wins(monkeypatch, tmp_path):
    """Deliberately weak toy verifier: the harness MUST exit 2 and the report
    MUST name the winning attack. This is the harness's non-vacuity proof."""
    monkeypatch.setattr(attacks_module, "verify_envelope", lambda envelope, pubkey: True)
    out = tmp_path / "attack_out"
    stdout = io.StringIO()
    exit_code = main(["run", "--out", str(out), "--json"], stdout=stdout)
    assert exit_code == 2

    printed = stdout.getvalue()
    assert "receipt chain FAILED" in printed
    assert "forge-wrong-key" in printed  # the report must say exactly which won

    report_text = (out / "ATTACK_REPORT.md").read_text(encoding="utf-8")
    assert "receipt chain FAILED" in report_text
    assert "**BROKEN**" in report_text
    assert "forge-wrong-key" in report_text

    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["passed"] is False
    broken_names = {r["name"] for r in results["results"] if r["result"] == "BROKEN"}
    assert {"forge-wrong-key", "forge-fabricated-signature"} <= broken_names


def test_cli_no_subcommand_is_usage_error():
    import pytest

    with pytest.raises(SystemExit):
        main([], stdout=io.StringIO())
