"""CLI: seed writes the honest initial state; print renders the served view."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from szl_claims_api.cli import main
from szl_claims_api.store import ClaimStore, refresh_from_estate

_SHA256_HEX_RE = re.compile(r"\A[0-9a-f]{64}\Z")


def test_help_everywhere(capsys: pytest.CaptureFixture[str]) -> None:
    for argv in (["--help"], ["serve", "--help"], ["seed", "--help"], ["print", "--help"]):
        with pytest.raises(SystemExit) as excinfo:
            main(argv)
        assert excinfo.value.code == 0
        assert "usage:" in capsys.readouterr().out


def test_seed_writes_valid_all_unknown_claims_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["seed", "--out", str(tmp_path / "claims")]) == 0
    out = capsys.readouterr().out
    assert "10 UNKNOWN" in out
    path = tmp_path / "claims" / "claims.json"
    assert path.exists()
    store = ClaimStore(path)
    assert store.state == "OK"
    stats = store.stats()
    assert stats.total == 10
    assert stats.unknown == 10
    claims = {c["claim_id"]: c for c in store.get_all()}
    # The org's real public claims are all in the seed.
    assert claims["ouroboros_tests"]["expected"] == "218/218"
    assert claims["platform_tests"]["expected"] == "1220/1220 across 76 packages"
    assert claims["mcp_e2e"]["expected"] == "27/27"
    assert claims["db_tables"]["expected"] == 848
    assert claims["api_endpoints"]["expected"] == 5524
    assert claims["monorepo_packages"]["expected"] == 126
    assert claims["lambda_overhead_ms_median"]["expected"] == "<= 0.59 ms"
    assert claims["hf_models"]["expected"] == 44
    assert claims["hf_datasets"]["expected"] == 30
    assert claims["hf_datasets"]["source"] == (
        "SZLHOLDINGS/model-bom DATASET_LICENSE_REGISTER.csv "
        "refresh 2026-08-31 (30 rows)"
    )
    assert claims["org_repos"]["expected"] == 100
    assert claims["org_repos"]["source"] == "GitHub enumeration 2026-08-31"


def test_print_json_matches_served_view(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["seed", "--out", str(tmp_path)])
    capsys.readouterr()
    assert main(["print", "--claims-file", str(tmp_path / "claims.json"), "--json"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["store_state"] == "OK"
    assert body["stats"]["UNKNOWN"] == 10
    for claim in body["claims"]:
        assert _SHA256_HEX_RE.match(claim["receipt_id"])
        assert claim["verdict"] == "UNKNOWN"
        assert claim["actual"] is None


def test_print_text_missing_file_is_honest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope" / "claims.json"
    assert main(["print", "--claims-file", str(missing)]) == 0
    out = capsys.readouterr().out
    assert "store state: UNAVAILABLE" in out
    assert "UNKNOWN" in out
    assert "0 PASS, 0 DRIFT, 10 UNKNOWN" in out


def test_seed_is_idempotent(tmp_path: Path) -> None:
    main(["seed", "--out", str(tmp_path)])
    first = (tmp_path / "claims.json").read_bytes()
    main(["seed", "--out", str(tmp_path)])
    second = (tmp_path / "claims.json").read_bytes()
    assert first == second


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "szl-claims-api" in capsys.readouterr().out


def test_refresh_from_estate_boundary(tmp_path: Path) -> None:
    """The optional szl-estate boundary: recomputes when importable, else a
    clean (False, note) — never an exception leaking into serving."""
    ok, note = refresh_from_estate(tmp_path / "claims-out")
    assert isinstance(ok, bool)
    assert isinstance(note, str) and note
    if ok:
        # szl-estate ran; the rewritten file must load strictly OK.
        store = ClaimStore(tmp_path / "claims-out" / "claims.json")
        assert store.state == "OK"
        claims = {c["claim_id"]: c for c in store.get_all()}
        # Seed coverage is total: refresh can never drop a public claim.
        assert "org_repos" in claims
        # A refresh is a run, so refreshed UNKNOWNs carry the run's timestamp
        # and observed stays null — you cannot know a number you did not compute.
        assert all(c["observed"] is None or c["verdict"] != "UNKNOWN" for c in claims.values())
