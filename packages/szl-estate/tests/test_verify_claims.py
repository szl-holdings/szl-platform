"""Offline tests for claim verification: DRIFT is computed, static_expected is
UNKNOWN by construction, and http_json goes through an injected transport."""

from __future__ import annotations

import json
from pathlib import Path

from szl_estate import verify_claims as vc


def _claim(claim_id: str, expected, check: dict) -> vc.Claim:  # noqa: ANN001, ANN202
    return vc.Claim.model_validate(
        {
            "claim_id": claim_id,
            "description": f"desc {claim_id}",
            "source": "unit test",
            "expected": expected,
            "check": check,
        }
    )


class _Resp:
    def __init__(self, status_code: int, payload) -> None:  # noqa: ANN001
        self.status_code = status_code
        self._payload = payload

    def json(self):  # noqa: ANN202
        return self._payload


class TestStaticExpected:
    def test_static_expected_is_unknown_never_pass(self) -> None:
        claim = _claim("ouroboros_tests", "218/218", {"type": "static_expected"})
        result = vc.run_claim(claim)
        assert result.verdict == "UNKNOWN"
        assert result.observed is None, "no number was computed, so none may be printed as observed"
        assert "not recomputed" in result.evidence

    def test_all_seeded_static_claims_are_unknown(self) -> None:
        """The shipped claims.yaml: every static_expected claim must be UNKNOWN."""
        for claim in vc.load_claims():
            if claim.check.type == "static_expected":
                result = vc.run_claim(claim)
                assert result.verdict == "UNKNOWN", claim.claim_id
                assert result.verdict != "PASS"


class TestCountFiles:
    def test_matching_count_passes(self, tmp_path: Path) -> None:
        pkg = tmp_path / "packages"
        for name in ("a", "b", "c"):
            (pkg / name).mkdir(parents=True)
            (pkg / name / "pyproject.toml").write_text("[project]\nname='x'\n")
        claim = _claim(
            "monorepo_packages",
            3,
            {"type": "count_files", "base_path": "packages", "glob": "*/pyproject.toml"},
        )
        result = vc.run_claim(claim, base_dir=tmp_path)
        assert result.observed == 3
        assert result.verdict == "PASS"

    def test_mismatch_is_drift_with_both_numbers(self, tmp_path: Path) -> None:
        pkg = tmp_path / "packages"
        for name in ("a", "b"):
            (pkg / name).mkdir(parents=True)
            (pkg / name / "pyproject.toml").write_text("[project]\nname='x'\n")
        claim = _claim(
            "monorepo_packages",
            126,
            {"type": "count_files", "base_path": "packages", "glob": "*/pyproject.toml"},
        )
        result = vc.run_claim(claim, base_dir=tmp_path)
        assert result.observed == 2  # computed in this run
        assert result.verdict == "DRIFT"
        assert "126" in result.expected_quoted

    def test_missing_path_is_unknown_not_zero(self, tmp_path: Path) -> None:
        claim = _claim(
            "monorepo_packages",
            126,
            {"type": "count_files", "base_path": "packages", "glob": "*/pyproject.toml"},
        )
        result = vc.run_claim(claim, base_dir=tmp_path / "empty")
        assert result.verdict == "UNKNOWN"
        assert result.observed is None


class TestHttpJson:
    def _client(self, response):  # noqa: ANN001, ANN202
        class FakeClient:
            def get(self, url):  # noqa: ANN001, ANN202
                return response

        return FakeClient()

    def test_array_length_is_computed_and_compared(self) -> None:
        claim = _claim(
            "hf_models",
            43,
            {
                "type": "http_json",
                "url": "https://huggingface.co/api/models?author=SZLHOLDINGS",
                "path": "",
            },
        )
        result = vc.run_claim(
            claim, client=self._client(_Resp(200, [{"id": f"m{i}"} for i in range(43)]))
        )
        assert result.observed == 43
        assert result.verdict == "PASS"

    def test_drift_when_counts_disagree(self) -> None:
        claim = _claim(
            "hf_datasets",
            28,
            {
                "type": "http_json",
                "url": "https://huggingface.co/api/datasets?author=SZLHOLDINGS",
                "path": "",
            },
        )
        result = vc.run_claim(claim, client=self._client(_Resp(200, [{"id": "d0"}])))
        assert result.observed == 1
        assert result.verdict == "DRIFT"

    def test_network_failure_is_unknown_never_a_remembered_number(self) -> None:
        import httpx

        class BadClient:
            def get(self, url):  # noqa: ANN001, ANN202
                raise httpx.ConnectError("no route to host")

        claim = _claim(
            "hf_models",
            43,
            {"type": "http_json", "url": "https://huggingface.co/api/models", "path": ""},
        )
        result = vc.run_claim(claim, client=BadClient())
        assert result.verdict == "UNKNOWN"
        assert result.observed is None
        assert "network failure" in result.evidence

    def test_http_error_status_is_unknown(self) -> None:
        claim = _claim(
            "hf_models", 43, {"type": "http_json", "url": "https://example.com/x", "path": ""}
        )
        result = vc.run_claim(claim, client=self._client(_Resp(503, {})))
        assert result.verdict == "UNKNOWN"

    def test_dotted_path_extraction(self) -> None:
        claim = _claim(
            "endpoint_count",
            5524,
            {"type": "http_json", "url": "https://example.com/stats", "path": "result.count"},
        )
        result = vc.run_claim(claim, client=self._client(_Resp(200, {"result": {"count": 5524}})))
        assert result.observed == 5524
        assert result.verdict == "PASS"


class TestReporting:
    def test_report_and_json_written(self, tmp_path: Path) -> None:
        (tmp_path / "packages" / "only").mkdir(parents=True)
        (tmp_path / "packages" / "only" / "pyproject.toml").write_text("[project]\nname='x'\n")
        claims = [
            _claim(
                "monorepo_packages",
                126,
                {"type": "count_files", "base_path": "packages", "glob": "*/pyproject.toml"},
            ),
            _claim("ouroboros_tests", "218/218", {"type": "static_expected"}),
        ]
        results = vc.verify(tmp_path / "out", base_dir=tmp_path, claims=claims)
        by_id = {r.claim_id: r for r in results}
        assert by_id["monorepo_packages"].verdict == "DRIFT"
        assert by_id["monorepo_packages"].observed == 1
        assert by_id["ouroboros_tests"].verdict == "UNKNOWN"

        report = (tmp_path / "out" / "CLAIMS_REPORT.md").read_text()
        assert "CLAIM_DRIFT" in report
        assert "monorepo_packages" in report
        # The observed cell exists only for the computed claim; the static one is an em-dash.
        lines = [line for line in report.splitlines() if line.startswith("|")]
        static_row = next(line for line in lines if "ouroboros_tests" in line)
        assert "| — |" in static_row, "a run must never print a number it did not compute"

        data = json.loads((tmp_path / "out" / "claims.json").read_text())
        assert data["findings"][0]["code"] == "CLAIM_DRIFT"
        assert len(data["results"]) == 2

    def test_seeded_registry_loads_all_nine_claims(self) -> None:
        claims = vc.load_claims()
        assert len(claims) == 9
        ids = [c.claim_id for c in claims]
        assert "hf_models" in ids and "hf_datasets" in ids and "lambda_overhead_ms_median" in ids


def test_extract_number_parsing() -> None:
    assert vc._extract_number("1220/1220 across 76 packages") == 1220
    assert vc._extract_number("<= 0.59 ms") == 0.59
    assert vc._extract_number("no digits") is None
    assert vc._compare("<= 0.59 ms", 0.4) is True
    assert vc._compare("<= 0.59 ms", 0.61) is False
