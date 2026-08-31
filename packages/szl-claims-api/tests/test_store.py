"""Store: strict validation, honest degradation, stats, verdict vocabulary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from szl_claims_api.store import (
    STORE_STATES,
    VERDICTS,
    ClaimsFileError,
    ClaimStore,
    validate_claim_records,
)


def test_verdict_vocabulary_is_closed() -> None:
    assert VERDICTS == ("PASS", "DRIFT", "UNKNOWN")
    assert STORE_STATES == ("OK", "UNAVAILABLE", "INVALID")


def test_load_sample_claims(sample_claims_path: Path) -> None:
    store = ClaimStore(sample_claims_path)
    assert store.state == "OK"
    assert store.ok
    assert store.note is None
    claims = store.get_all()
    assert [c["claim_id"] for c in claims] == [
        "monorepo_packages",
        "hf_models",
        "lambda_overhead_ms_median",
    ]


def test_get_one(sample_claims_path: Path) -> None:
    store = ClaimStore(sample_claims_path)
    claim = store.get_one("hf_models")
    assert claim is not None
    assert claim["expected"] == 43
    assert claim["observed"] == 41
    assert claim["verdict"] == "DRIFT"
    assert store.get_one("nonexistent") is None


def test_stats_counts_by_verdict(sample_claims_path: Path) -> None:
    stats = ClaimStore(sample_claims_path).stats()
    assert stats.total == 3
    assert stats.passed == 1
    assert stats.drift == 1
    assert stats.unknown == 1
    assert stats.to_dict() == {"total": 3, "PASS": 1, "DRIFT": 1, "UNKNOWN": 1}


def test_missing_file_degrades_to_unavailable_with_seeded_unknowns(
    missing_claims_path: Path,
) -> None:
    store = ClaimStore(missing_claims_path)
    assert store.state == "UNAVAILABLE"
    assert not store.ok
    assert store.note is not None
    assert "missing or unreadable" in store.note
    claims = store.get_all()
    # The seeded registry is served — every claim UNKNOWN, never fabricated.
    assert len(claims) == 10
    assert all(c["verdict"] == "UNKNOWN" for c in claims)
    assert all(c["observed"] is None for c in claims)
    assert all(c["last_run"] is None for c in claims)
    # get_one still resolves seeded claim ids.
    assert store.get_one("org_repos") is not None
    assert store.get_one("org_repos")["expected"] == 100


def test_invalid_file_degrades_to_invalid(sample_claims_path: Path, tmp_path: Path) -> None:
    bad = json.loads(sample_claims_path.read_text(encoding="utf-8"))
    bad[0]["verdict"] = "GREEN"  # outside the closed vocabulary
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    store = ClaimStore(path)
    assert store.state == "INVALID"
    assert "GREEN" in (store.note or "")
    # Seeded fallback is served, not the corrupt data.
    assert {c["claim_id"] for c in store.get_all()} != {"monorepo_packages", "hf_models"}
    assert all(c["verdict"] == "UNKNOWN" for c in store.get_all())


def test_malformed_json_degrades_to_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "claims.json"
    path.write_text("{not json", encoding="utf-8")
    store = ClaimStore(path)
    assert store.state == "UNAVAILABLE"
    assert all(c["verdict"] == "UNKNOWN" for c in store.get_all())


def test_strict_validation_rejects_extra_keys() -> None:
    record = {
        "claim_id": "x",
        "description": "d",
        "source": "s",
        "expected": 1,
        "observed": 1,
        "verdict": "PASS",
        "evidence": "e",
        "last_run": "2026-08-31T00:00:00Z",
        "confidence": "high",  # smuggled key must be refused
    }
    with pytest.raises(ClaimsFileError, match="unexpected key: confidence"):
        validate_claim_records([record])


def test_strict_validation_rejects_pass_without_observed() -> None:
    record = {
        "claim_id": "x",
        "description": "d",
        "source": "s",
        "expected": 1,
        "observed": None,
        "verdict": "PASS",
        "evidence": "e",
        "last_run": "2026-08-31T00:00:00Z",
    }
    with pytest.raises(ClaimsFileError, match="requires a non-null observed"):
        validate_claim_records([record])


def test_strict_validation_rejects_unknown_with_observed() -> None:
    record = {
        "claim_id": "x",
        "description": "d",
        "source": "s",
        "expected": 1,
        "observed": 1,  # UNKNOWN with a number is laundering
        "verdict": "UNKNOWN",
        "evidence": "e",
        "last_run": None,
    }
    with pytest.raises(ClaimsFileError, match="UNKNOWN forbids a non-null observed"):
        validate_claim_records([record])


def test_strict_validation_rejects_duplicate_ids() -> None:
    record = {
        "claim_id": "x",
        "description": "d",
        "source": "s",
        "expected": 1,
        "observed": None,
        "verdict": "UNKNOWN",
        "evidence": "e",
        "last_run": None,
    }
    with pytest.raises(ClaimsFileError, match="duplicate claim_id"):
        validate_claim_records([record, dict(record)])


def test_strict_validation_rejects_naive_timestamp() -> None:
    record = {
        "claim_id": "x",
        "description": "d",
        "source": "s",
        "expected": 1,
        "observed": 1,
        "verdict": "PASS",
        "evidence": "e",
        "last_run": "2026-08-31 07:30:00",  # no timezone — not wire-grammatical
    }
    with pytest.raises(ClaimsFileError, match="last_run"):
        validate_claim_records([record])


def test_top_level_must_be_a_list() -> None:
    with pytest.raises(ClaimsFileError, match="top level must be a list"):
        validate_claim_records({"claims": []})
