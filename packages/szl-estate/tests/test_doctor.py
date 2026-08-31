"""Offline tests for doctor: every external surface is faked (subprocess
runners, DNS resolvers, httpx, module imports). Nothing touches the network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import FakeProc
from szl_estate import BLOCKERS_HEADER, doctor
from szl_estate.doctor import CheckResult


class TestCloudflareGate:
    def _cf_result(self, env, response):  # noqa: ANN001, ANN202
        class FakeClient:
            def get(self, url, headers=None):  # noqa: ANN001, ANN202
                return response

        return doctor.check_cloudflare(env=env, client=FakeClient())

    class _Resp:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self):  # noqa: ANN202
            return self._payload

    def test_active_token_passes(self) -> None:
        result = self._cf_result(
            {"CF_API_TOKEN": "cf_secret_unit_token_XYZ"},
            self._Resp(200, {"result": {"status": "active"}}),
        )
        assert result.status == "PASS"
        assert "cf_secret_unit_token_XYZ" not in result.evidence, (
            "token value must never leak into evidence"
        )

    def test_inactive_token_fails(self) -> None:
        result = self._cf_result(
            {"CF_API_TOKEN": "cf_secret_unit_token_XYZ"},
            self._Resp(200, {"result": {"status": "disabled"}}),
        )
        assert result.status == "FAIL"

    def test_missing_token_is_blocked_not_failed(self) -> None:
        result = self._cf_result({}, self._Resp(200, {}))
        assert result.status == "BLOCKED"
        assert result.evidence == "token not provided to doctor"


class TestCredentials:
    def test_gh_token_presence_is_boolean_only(self) -> None:
        assert doctor.check_gh_token(env={"GH_TOKEN": "s3cret"}).status == "PASS"
        result = doctor.check_gh_token(env={"GH_TOKEN": "s3cret"})
        assert "s3cret" not in result.evidence
        assert doctor.check_gh_token(env={}).status == "FAIL"

    def test_gh_auth_success_reports_login(self) -> None:
        def run(cmd):  # noqa: ANN001, ANN202
            return FakeProc(stdout="stephenlutar2-hash\n")

        result = doctor.check_gh_auth(run=run)
        assert result.status == "PASS"
        assert result.evidence == "authenticated as stephenlutar2-hash"

    def test_gh_auth_failure_is_fail(self) -> None:
        def run(cmd):  # noqa: ANN001, ANN202
            return FakeProc(returncode=1, stderr="gh: not logged in")

        result = doctor.check_gh_auth(run=run)
        assert result.status == "FAIL"
        assert result.fatal is True


class TestDns:
    def test_szl_dev_nxdomain_is_fail_with_no_delegation(self) -> None:
        def resolver(host):  # noqa: ANN001, ANN202
            raise doctor._ResolutionUnavailable("no delegation")

        result = doctor.check_dns_szl_dev_ns(resolver=resolver)
        assert result.status == "FAIL"
        assert "no delegation" in result.evidence

    def test_szl_dev_delegated_passes(self) -> None:
        result = doctor.check_dns_szl_dev_ns(
            resolver=lambda host: ["ns1.example.net", "ns2.example.net"]
        )
        assert result.status == "PASS"
        assert "ns1.example.net" in result.evidence

    def test_a11oy_net_must_be_github_pages(self) -> None:
        pages = ["185.199.108.153", "185.199.111.153"]
        ok = doctor.check_dns_a11oy_net(resolver=lambda host: pages)
        assert ok.status == "PASS"

        bad = doctor.check_dns_a11oy_net(resolver=lambda host: ["185.199.108.153", "203.0.113.9"])
        assert bad.status == "FAIL"
        assert "203.0.113.9" in bad.evidence

    def test_a_11_oy_com_any_result_passes_with_values(self) -> None:
        result = doctor.check_dns_a_11_oy_com(resolver=lambda host: ["76.76.21.21"])
        assert result.status == "PASS"
        assert "76.76.21.21" in result.evidence


class TestCloudflared:
    def test_active_is_pass(self) -> None:
        result = doctor.check_cloudflared(run=lambda cmd: FakeProc(stdout="active\n"))
        assert result.status == "PASS"

    def test_inactive_is_warn_not_pass(self) -> None:
        result = doctor.check_cloudflared(
            run=lambda cmd: FakeProc(returncode=3, stdout="inactive\n")
        )
        assert result.status == "WARN"
        assert "inactive" in result.evidence


class TestHuggingFaceHubGate:
    def _install_fake(self, monkeypatch: pytest.MonkeyPatch, version: str, with_api: bool) -> None:
        import sys
        import types

        module = types.ModuleType("huggingface_hub")
        module.__version__ = version

        class HfApi:
            pass

        if with_api:
            HfApi.list_user_repos = lambda self, *a, **k: []  # noqa: ARG005
        module.HfApi = HfApi
        monkeypatch.setitem(sys.modules, "huggingface_hub", module)

    def test_valid_version_and_api_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_fake(monkeypatch, "1.2.3", with_api=True)
        result = doctor.check_huggingface_hub()
        assert result.status == "PASS"
        assert result.fatal is False

    def test_old_version_is_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_fake(monkeypatch, "0.34.0", with_api=True)
        result = doctor.check_huggingface_hub()
        assert result.status == "FAIL"
        assert result.fatal is True, "the only call that can see private HF buckets must gate hard"

    def test_missing_list_user_repos_is_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_fake(monkeypatch, "1.2.3", with_api=False)
        result = doctor.check_huggingface_hub()
        assert result.status == "FAIL"
        assert result.fatal is True
        assert "MISSING" in result.evidence


class TestReportShape:
    def _checks(self, failing: bool) -> list[CheckResult]:
        checks = [
            CheckResult(name="a", status="PASS", evidence="e", rollback="r", next_safe_action="n"),
        ]
        if failing:
            checks.append(
                CheckResult(
                    name="b",
                    status="FAIL",
                    evidence="boom",
                    rollback="r",
                    next_safe_action="n",
                    fatal=True,
                )
            )
        return checks

    def test_first_section_header_is_the_blockers_line(self) -> None:
        report = doctor.format_human(self._checks(failing=True))
        lines = [line for line in report.splitlines() if line.strip()]
        # After the title line, the first header must be exactly the blockers line.
        assert BLOCKERS_HEADER in lines[1:3]

    def test_json_mirrors_report_structure(self) -> None:
        data = doctor.payload(self._checks(failing=True))
        assert data["blockers_section"] == BLOCKERS_HEADER
        assert data["any_fail"] is True
        assert {c["name"] for c in data["checks"]} == {"a", "b"}
        json.dumps(data)  # must be serializable

    def test_exit_code(self, tmp_path: Path) -> None:
        assert doctor.main(["--json"], checks=self._checks(failing=False)) == 0
        assert doctor.main([], checks=self._checks(failing=True)) == 1

    def test_run_all_checks_uses_injected_fakes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        import types

        module = types.ModuleType("huggingface_hub")
        module.__version__ = "1.0.0"

        class HfApi:
            def list_user_repos(self):  # noqa: ANN202
                return []

        module.HfApi = HfApi
        monkeypatch.setitem(sys.modules, "huggingface_hub", module)
        # Hermetic tool detection: pretend every binary exists on PATH.
        monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")

        class _Resp:
            status_code = 200

            def json(self):  # noqa: ANN202
                return {"result": {"status": "active"}}

        class _CFClient:
            def get(self, url, headers=None):  # noqa: ANN001, ANN202
                return _Resp()

        def run(cmd):  # noqa: ANN001, ANN202
            if cmd[:2] == ["gh", "api"]:
                return FakeProc(stdout="stephenlutar2-hash\n")
            if cmd == ["git", "--version"]:
                return FakeProc(stdout="git version 2.40")
            return FakeProc(stdout="active\n")

        checks = doctor.run_all_checks(
            env={"GH_TOKEN": "x", "CF_API_TOKEN": "y"},
            run=run,
            a_resolver=lambda host: ["185.199.108.153"],
            ns_resolver=lambda host: ["ns1.example.net"],
            cf_client=_CFClient(),
        )
        # With every surface faked healthy, nothing may be FAIL.
        assert [c.status for c in checks] == ["PASS"] * len(checks)
        names = [c.name for c in checks]
        assert names == [
            "python>=3.11",
            "git",
            "gh_authenticated",
            "gh_token_env",
            "cloudflare_token",
            "dns_a11oy_net",
            "dns_a_11_oy_com",
            "dns_szl_dev_ns",
            "cloudflared_service",
            "huggingface_hub",
        ]


def test_python_check_passes_on_this_interpreter() -> None:
    # The environment running this suite is >= 3.11 by project requirement.
    assert doctor.check_python().status == "PASS"
