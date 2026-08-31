"""HTTP surface: the Covenant Proof Standard endpoints over TestClient."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from szl_claims_api.app import create_app
from szl_claims_api.seed import seed_claims
from szl_claims_api.store import BLOCKERS_HEADER, validate_claim_records
from szl_receipts import verify_receipt


@pytest.fixture
def client(sample_claims_path: Path) -> TestClient:
    return TestClient(create_app(sample_claims_path))


@pytest.fixture
def seeded_client(tmp_path: Path) -> TestClient:
    seed_claims(tmp_path / "claims")
    return TestClient(create_app(tmp_path / "claims" / "claims.json"))


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["store_state"] == "OK"
    assert body["server_time"].endswith("Z")


def test_list_claims_wire_shape(client: TestClient) -> None:
    resp = client.get("/api/cps/claims")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"generated_at", "store_state", "stats", "claims"}
    assert body["store_state"] == "OK"
    assert body["stats"] == {"total": 3, "PASS": 1, "DRIFT": 1, "UNKNOWN": 1}
    by_id = {c["claim_id"]: c for c in body["claims"]}
    passed = by_id["monorepo_packages"]
    assert passed["claimed"] == 126
    assert passed["actual"] == 126
    assert passed["verdict"] == "PASS"
    assert passed["drift"] is False
    assert passed["receipt_url"] == "/api/cps/claims/monorepo_packages/receipt"
    drifted = by_id["hf_models"]
    assert drifted["claimed"] == 43
    assert drifted["actual"] == 41
    assert drifted["drift"] is True
    unknown = by_id["lambda_overhead_ms_median"]
    assert unknown["actual"] is None
    assert unknown["last_run"] is None
    assert unknown["verdict"] == "UNKNOWN"


def test_numbers_come_verbatim_from_the_file(client: TestClient) -> None:
    """The service computes no numbers: `claimed`/`actual` equal file values."""
    body = client.get("/api/cps/claims").json()
    for claim in body["claims"]:
        assert isinstance(claim["claimed"], (int, str))
        # actual is either the file's observed value or null — never computed.
        assert claim["actual"] in (41, 126, None)


def test_seed_serve_flow_is_all_unknown_honestly(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/cps/claims").json()
    assert body["store_state"] == "OK"
    assert body["stats"] == {"total": 10, "PASS": 0, "DRIFT": 0, "UNKNOWN": 10}
    assert all(c["verdict"] == "UNKNOWN" for c in body["claims"])
    assert all(c["actual"] is None for c in body["claims"])
    assert all(c["drift"] is False for c in body["claims"])
    # But the quoted claims themselves are present, attributed to sources.
    by_id = {c["claim_id"]: c for c in body["claims"]}
    assert by_id["ouroboros_tests"]["claimed"] == "218/218"
    assert by_id["db_tables"]["claimed"] == 848
    assert by_id["org_repos"]["claimed"] == 100


def test_get_one_claim(client: TestClient) -> None:
    resp = client.get("/api/cps/claims/hf_models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["claim_id"] == "hf_models"
    assert body["description"].startswith("Public models")
    assert body["source"] == "org README verified 2026-05-12"
    assert body["drift"] is True


def test_get_one_claim_404(client: TestClient) -> None:
    resp = client.get("/api/cps/claims/no_such_claim")
    assert resp.status_code == 404
    assert "no_such_claim" in resp.json()["detail"]


def test_receipt_endpoint_returns_verifying_receipt(client: TestClient) -> None:
    resp = client.get("/api/cps/claims/monorepo_packages/receipt")
    assert resp.status_code == 200
    receipt = resp.json()
    assert verify_receipt(receipt) == []
    assert receipt["action"] == "claim.verify"
    assert receipt["decision"]["outcome"] == "PASS"
    # The receipt_id served in the listing matches the full receipt endpoint.
    listing = client.get("/api/cps/claims").json()
    by_id = {c["claim_id"]: c for c in listing["claims"]}
    assert by_id["monorepo_packages"]["receipt_id"] == receipt["receipt_id"]


def test_receipt_endpoint_404_on_unknown_claim(client: TestClient) -> None:
    assert client.get("/api/cps/claims/nope/receipt").status_code == 404


def test_report_md_blockers_header_when_drift(client: TestClient) -> None:
    resp = client.get("/api/cps/report.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    lines = resp.text.splitlines()
    assert lines[0].startswith("# ")
    # Top line after the title is exactly the blockers header.
    assert lines[1] == BLOCKERS_HEADER
    # The drifting claim is listed first, before the table.
    table_header = "| Claim | Claimed | Actual | Last run | Verdict | Drift | Receipt |"
    blocker_section_end = lines.index(table_header)
    blockers = "\n".join(lines[:blocker_section_end])
    assert "CLAIM_DRIFT" in blockers
    assert "hf_models" in blockers
    assert "monorepo_packages" not in blockers
    # Full table is still present below.
    assert "| monorepo_packages | 126 | 126 |" in resp.text
    assert "| hf_models | 43 | 41 |" in resp.text
    # Honest server-time note, and no invented numbers.
    assert "server_time" in resp.text
    assert "computes no claim values itself" in resp.text


def test_report_md_no_drift_shows_table_without_blockers(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/cps/report.md")
    assert resp.status_code == 200
    lines = resp.text.splitlines()
    assert lines[0].startswith("# ")
    assert BLOCKERS_HEADER not in resp.text
    # With no DRIFT, the claims table directly follows the title.
    assert lines[1] == "| Claim | Claimed | Actual | Last run | Verdict | Drift | Receipt |"
    # UNKNOWN claims render an em-dash for actual, never a remembered number.
    assert "| ouroboros_tests | 218/218 | — | — | UNKNOWN | no |" in resp.text


def test_missing_file_serves_unavailable_with_unknowns(
    missing_claims_path: Path,
) -> None:
    client = TestClient(create_app(missing_claims_path))
    body = client.get("/api/cps/claims").json()
    assert body["store_state"] == "UNAVAILABLE"
    assert body["note"]  # the degradation is explained, not silent
    assert body["stats"] == {"total": 10, "PASS": 0, "DRIFT": 0, "UNKNOWN": 10}
    assert all(c["verdict"] == "UNKNOWN" for c in body["claims"])
    # Receipts still mint and verify for UNKNOWN claims.
    receipt = client.get("/api/cps/claims/org_repos/receipt").json()
    assert verify_receipt(receipt) == []
    assert receipt["decision"]["outcome"] == "UNKNOWN"


def test_receipt_caching_across_requests(client: TestClient) -> None:
    first = client.get("/api/cps/claims").json()
    second = client.get("/api/cps/claims").json()
    ids_first = {c["claim_id"]: c["receipt_id"] for c in first["claims"]}
    ids_second = {c["claim_id"]: c["receipt_id"] for c in second["claims"]}
    assert ids_first == ids_second


def test_cors_is_open_read_only(client: TestClient) -> None:
    resp = client.get("/api/cps/claims", headers={"Origin": "https://diligence.example.com"})
    assert resp.headers["access-control-allow-origin"] == "*"
    # Write methods are simply not routed.
    assert client.post("/api/cps/claims", json={}).status_code == 405


def test_fixture_round_trips_through_store(client: TestClient, sample_claims_path: Path) -> None:
    """Belt-and-braces: the fixture itself strictly validates."""
    del client  # fixture keeps the app-construction path warm
    raw = json.loads(sample_claims_path.read_text(encoding="utf-8"))
    assert validate_claim_records(raw) == raw
