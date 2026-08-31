"""Environment, credential, and DNS doctor for the SZL estate.

`doctor` answers one question: can this machine and this network identity run
the estate? Every check returns a structured result:

    STATUS    one of PASS | WARN | FAIL | BLOCKED | UNKNOWN
    EVIDENCE  what was actually observed (never a token, never a guess)
    ROLLBACK  how to undo whatever the fix for this check might touch
    NEXT SAFE ACTION  the single smallest safe step toward PASS

Exit contract: the process exits 1 if ANY check is FAIL (a FATAL check — the
huggingface_hub gate — is a FAIL carrying ``fatal=True``), else 0.

The human report's FIRST section header is exactly
``BLOCKERS THAT OUTRANK ALL COSMETIC WORK`` — the same header the estate audit
uses, so an operator learns one layout for every SZL health artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from pydantic import BaseModel

from szl_estate import BLOCKERS_HEADER, GITHUB_PAGES_A_RECORDS

#: A subprocess-runner takes argv and returns a completed process. Checks take
#: one as a parameter so tests can fake command output without a real OS.
Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


class CheckResult(BaseModel):
    """One doctor check, fully described."""

    name: str
    status: str  # PASS | WARN | FAIL | BLOCKED | UNKNOWN
    evidence: str
    rollback: str
    next_safe_action: str
    fatal: bool = False  # True iff failing this check blocks the estate outright


class _ResolutionUnavailable(RuntimeError):
    """The local resolver cannot answer the question at all (UNKNOWN, not FAIL)."""


def _run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing output. Callers handle non-zero exits."""
    return subprocess.run(  # noqa: S603 — fixed argv lists, no shell
        list(cmd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def check_python() -> CheckResult:
    """The estate requires Python >= 3.11 (src layout, tomllib-era tooling)."""
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 11)
    return CheckResult(
        name="python>=3.11",
        status="PASS" if ok else "FAIL",
        evidence=f"running {v.major}.{v.minor}.{v.micro}",
        rollback="no system change made; install python3.11+ alongside, never replace",
        next_safe_action="nothing" if ok else "install Python 3.11 or newer and re-run doctor",
        fatal=not ok,
    )


def check_git(run: Runner = _run) -> CheckResult:
    """git must be on PATH; audits and enumeration shells assume it."""
    if shutil.which("git") is None:
        return CheckResult(
            name="git",
            status="FAIL",
            evidence="git not found on PATH",
            rollback="nothing was changed",
            next_safe_action="install git (package manager of the host OS)",
            fatal=True,
        )
    try:
        proc = run(["git", "--version"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            name="git",
            status="UNKNOWN",
            evidence=f"git probe failed: {exc}",
            rollback="nothing was changed",
            next_safe_action="re-run on a healthy shell",
        )
    return CheckResult(
        name="git",
        status="PASS" if proc.returncode == 0 else "FAIL",
        evidence=proc.stdout.strip() or proc.stderr.strip(),
        rollback="nothing was changed",
        next_safe_action="nothing" if proc.returncode == 0 else "repair the git installation",
    )


def check_gh_auth(run: Runner = _run) -> CheckResult:
    """gh must exist AND be authenticated; we ask for the login, never a token."""
    if shutil.which("gh") is None:
        return CheckResult(
            name="gh_authenticated",
            status="FAIL",
            evidence="gh CLI not found on PATH",
            rollback="nothing was changed",
            next_safe_action="install GitHub CLI, then `gh auth login`",
            fatal=True,
        )
    try:
        # --jq .login returns only the username. Tokens are never requested,
        # never printed, never logged.
        proc = run(["gh", "api", "user", "--jq", ".login"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            name="gh_authenticated",
            status="UNKNOWN",
            evidence=f"gh auth probe failed: {exc}",
            rollback="nothing was changed",
            next_safe_action="re-run on a healthy shell",
        )
    login = proc.stdout.strip()
    ok = proc.returncode == 0 and bool(login)
    return CheckResult(
        name="gh_authenticated",
        status="PASS" if ok else "FAIL",
        evidence=f"authenticated as {login}"
        if ok
        else f"gh api user failed: {proc.stderr.strip()[:200]}",
        rollback="`gh auth logout` if this identity should not be on this machine",
        next_safe_action="nothing" if ok else "run `gh auth login` with the estate account",
        fatal=not ok,
    )


def check_gh_token(env: dict[str, str] | None = None) -> CheckResult:
    """GH_TOKEN must exist for REST enumeration. Presence is a boolean — the
    value is never read into evidence, never printed."""
    env = os.environ if env is None else env
    present = bool(env.get("GH_TOKEN"))
    return CheckResult(
        name="gh_token_env",
        status="PASS" if present else "FAIL",
        evidence="GH_TOKEN present (value not inspected)" if present else "GH_TOKEN is not set",
        rollback="unset GH_TOKEN if it must not persist in this shell",
        next_safe_action="nothing"
        if present
        else "export GH_TOKEN for REST enumeration (source B)",
    )


def check_cloudflare(
    env: dict[str, str] | None = None,
    client: httpx.Client | None = None,
) -> CheckResult:
    """Cloudflare token gate.

    If CF_API_TOKEN is unset the check is BLOCKED — not failed — with the
    evidence string 'token not provided to doctor': doctor cannot verify what
    it was never given, and estate scripts that need Cloudflare must know the
    credential was absent, not broken. When set, we verify against
    /user/tokens/verify and require result.status == "active".
    """
    env = os.environ if env is None else env
    token = env.get("CF_API_TOKEN")
    if not token:
        return CheckResult(
            name="cloudflare_token",
            status="BLOCKED",
            evidence="token not provided to doctor",
            rollback="nothing was changed",
            next_safe_action="export CF_API_TOKEN if this host manages szl DNS/tunnels",
        )
    url = "https://api.cloudflare.com/client/v4/user/tokens/verify"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        if client is not None:
            resp = client.get(url, headers=headers)
        else:
            with httpx.Client(timeout=15.0) as owned:
                resp = owned.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return CheckResult(
            name="cloudflare_token",
            status="UNKNOWN",
            evidence=f"verify request failed: {exc}",
            rollback="nothing was changed",
            next_safe_action="check outbound network, then re-run doctor",
        )
    try:
        status_value = resp.json().get("result", {}).get("status")
    except (json.JSONDecodeError, AttributeError):
        status_value = None
    ok = resp.status_code == 200 and status_value == "active"
    return CheckResult(
        name="cloudflare_token",
        status="PASS" if ok else "FAIL",
        evidence=(
            f"HTTP {resp.status_code}, token status '{status_value}'"
            if status_value is not None
            else f"HTTP {resp.status_code}, unparseable verify body"
        ),
        rollback="revoke the token in the Cloudflare dashboard if exposed",
        next_safe_action="nothing" if ok else "regenerate the Cloudflare API token",
    )


def _resolve_a_records(hostname: str) -> list[str]:
    """Resolve A records via the system resolver. Raises on NXDOMAIN/failure."""
    try:
        infos = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
    except socket.gaierror as exc:
        raise _ResolutionUnavailable(f"no A records (resolve failed: {exc})") from exc
    return sorted({info[4][0] for info in infos})


def _resolve_ns_records(hostname: str) -> list[str]:
    """Resolve NS records.

    The stdlib has no NS lookup, so: dnspython if installed, else `dig +short
    NS`, else we honestly admit we cannot answer (UNKNOWN via _ResolutionUnavailable).
    """
    try:
        import dns.resolver  # type: ignore[import-not-found]
    except ImportError:
        dns = None  # noqa: F841 — presence probe only
    else:
        answers = dns.resolver.resolve(hostname, "NS")  # type: ignore[name-defined]
        return sorted(str(ans).rstrip(".") for ans in answers)
    if shutil.which("dig") is None:
        raise _ResolutionUnavailable("no dnspython and no dig; NS lookup unsupported here")
    proc = _run(["dig", "+short", "NS", hostname])
    if proc.returncode != 0:
        raise _ResolutionUnavailable(f"dig exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    records = sorted(line.strip().rstrip(".") for line in proc.stdout.splitlines() if line.strip())
    if not records:
        raise _ResolutionUnavailable("no delegation")
    return records


def check_dns_a11oy_net(resolver: Callable[[str], list[str]] = _resolve_a_records) -> CheckResult:
    """a11oy.net is served by GitHub Pages: its A set must be a subset of the
    four published GitHub Pages addresses."""
    try:
        records = resolver("a11oy.net")
    except _ResolutionUnavailable as exc:
        return CheckResult(
            name="dns_a11oy_net",
            status="FAIL",
            evidence=str(exc),
            rollback="remove any stale DNS records added during debugging",
            next_safe_action="point a11oy.net A records at GitHub Pages or restore the zone",
        )
    ok = bool(records) and set(records) <= set(GITHUB_PAGES_A_RECORDS)
    return CheckResult(
        name="dns_a11oy_net",
        status="PASS" if ok else "FAIL",
        evidence=f"A records {records}; required subset of {sorted(GITHUB_PAGES_A_RECORDS)}",
        rollback="revert A records to the four GitHub Pages addresses",
        next_safe_action="nothing" if ok else "remove non-GitHub-Pages A records from a11oy.net",
    )


def check_dns_a_11_oy_com(resolver: Callable[[str], list[str]] = _resolve_a_records) -> CheckResult:
    """a-11-oy.com is the product origin; any A set is PASS, values as evidence.
    NXDOMAIN here is WARN: the site failing would be a product outage, not a
    doctor lie, so we report what the resolver said."""
    try:
        records = resolver("a-11-oy.com")
    except _ResolutionUnavailable as exc:
        return CheckResult(
            name="dns_a_11_oy_com",
            status="WARN",
            evidence=str(exc),
            rollback="nothing was changed",
            next_safe_action="check the a-11-oy.com deployment (Served by the a11oy Docker Space)",
        )
    return CheckResult(
        name="dns_a_11_oy_com",
        status="PASS",
        evidence=f"A records {records}",
        rollback="nothing was changed",
        next_safe_action="nothing",
    )


def check_dns_szl_dev_ns(resolver: Callable[[str], list[str]] = _resolve_ns_records) -> CheckResult:
    """szl.dev must be delegated: empty or NXDOMAIN is FAIL with 'no delegation'."""
    try:
        records = resolver("szl.dev")
    except _ResolutionUnavailable as exc:
        msg = str(exc)
        # 'no delegation' must survive verbatim into the evidence for audits.
        status = "UNKNOWN" if "unsupported" in msg else "FAIL"
        return CheckResult(
            name="dns_szl_dev_ns",
            status=status,
            evidence=msg if "no delegation" in msg else f"{msg} ('no delegation' if NXDOMAIN)",
            rollback="nothing was changed",
            next_safe_action="restore NS records for szl.dev at the registrar",
        )
    return CheckResult(
        name="dns_szl_dev_ns",
        status="PASS",
        evidence=f"NS records {records}",
        rollback="nothing was changed",
        next_safe_action="nothing",
    )


def check_cloudflared(run: Runner = _run) -> CheckResult:
    """Is the tunnel service up? If systemd itself is absent: UNKNOWN."""
    if shutil.which("systemctl") is None:
        return CheckResult(
            name="cloudflared_service",
            status="UNKNOWN",
            evidence="systemctl not present on this host; cannot query service state",
            rollback="nothing was changed",
            next_safe_action="run doctor on the tunnel host itself",
        )
    try:
        proc = run(["systemctl", "is-active", "cloudflared"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            name="cloudflared_service",
            status="UNKNOWN",
            evidence=f"systemctl probe failed: {exc}",
            rollback="nothing was changed",
            next_safe_action="re-run on the tunnel host",
        )
    # rc!=0 covers 'inactive', 'failed', 'unknown', and 'systemd not running
    # in this container'; keep stderr so those cases are distinguishable.
    state = proc.stdout.strip() or f"rc={proc.returncode} {proc.stderr.strip()}".strip()
    return CheckResult(
        name="cloudflared_service",
        status="PASS" if state == "active" else "WARN",
        evidence=f"systemctl is-active cloudflared -> {state}",
        rollback="`systemctl stop cloudflared` if the tunnel must come down",
        next_safe_action="nothing"
        if state == "active"
        else "`systemctl status cloudflared` then restart if expected",
    )


def check_huggingface_hub() -> CheckResult:
    """huggingface_hub >= 1.0 with HfApi.list_user_repos.

    This gate is FATAL (status FAIL + fatal=True) because HfApi.list_user_repos
    is the only call in the estate that can see certain private model/dataset
    buckets on the SZLHOLDINGS org: anonymous REST listing and older hub
    versions silently omit private, gated, or draft repos. A control plane
    that cannot see those buckets would report an inventory it does not
    actually hold — so the library is import-checked and feature-checked, not
    merely version-checked.
    """
    try:
        import huggingface_hub
    except ImportError:
        return CheckResult(
            name="huggingface_hub",
            status="FAIL",
            evidence="huggingface_hub is not installed",
            rollback="pip uninstall huggingface_hub if it must not be here",
            next_safe_action="pip install 'huggingface_hub>=1.0'",
            fatal=True,
        )
    version = getattr(huggingface_hub, "__version__", "0.0.0")
    try:
        parts = tuple(int(p) for p in version.split(".")[:2])
    except ValueError:
        parts = (0, 0)
    has_api = hasattr(huggingface_hub.HfApi, "list_user_repos")
    ok = parts >= (1, 0) and has_api
    evidence = (
        f"huggingface_hub {version}, HfApi.list_user_repos {'present' if has_api else 'MISSING'}"
    )
    return CheckResult(
        name="huggingface_hub",
        status="PASS" if ok else "FAIL",
        evidence=evidence,
        rollback="pin an older huggingface_hub only if the rollback runbook commands it",
        next_safe_action="nothing" if ok else "pip install --upgrade 'huggingface_hub>=1.0'",
        fatal=not ok,
    )


def run_all_checks(
    *,
    env: dict[str, str] | None = None,
    run: Runner = _run,
    a_resolver: Callable[[str], list[str]] = _resolve_a_records,
    ns_resolver: Callable[[str], list[str]] = _resolve_ns_records,
    cf_client: httpx.Client | None = None,
) -> list[CheckResult]:
    """Run every check in a fixed, documented order. All parameters are
    injectable so the test suite never touches the network or the OS."""
    return [
        check_python(),
        check_git(run=run),
        check_gh_auth(run=run),
        check_gh_token(env=env),
        check_cloudflare(env=env, client=cf_client),
        check_dns_a11oy_net(resolver=a_resolver),
        check_dns_a_11_oy_com(resolver=a_resolver),
        check_dns_szl_dev_ns(resolver=ns_resolver),
        check_cloudflared(run=run),
        check_huggingface_hub(),
    ]


def any_fail(checks: list[CheckResult]) -> bool:
    """Exit-1 condition: any FAIL (fatal checks are FAIL carrying fatal=True)."""
    return any(c.status == "FAIL" for c in checks)


def format_human(checks: list[CheckResult]) -> str:
    """Human report. The FIRST section header is, by contract, exactly
    'BLOCKERS THAT OUTRANK ALL COSMETIC WORK'."""
    lines = ["SZL ESTATE DOCTOR", "", BLOCKERS_HEADER, "-" * len(BLOCKERS_HEADER)]
    blockers = [c for c in checks if c.status in ("FAIL", "WARN", "BLOCKED", "UNKNOWN")]
    if blockers:
        lines += [f"- {c.name}: {c.status} — {c.evidence}" for c in blockers]
    else:
        lines.append("none — every check is PASS")
    lines += ["", "CHECK DETAILS", "-------------"]
    for c in checks:
        lines += [
            "",
            f"[{c.status}] {c.name}" + (" (FATAL)" if c.fatal else ""),
            f"  EVIDENCE: {c.evidence}",
            f"  ROLLBACK: {c.rollback}",
            f"  NEXT SAFE ACTION: {c.next_safe_action}",
        ]
    return "\n".join(lines)


def payload(checks: list[CheckResult]) -> dict[str, Any]:
    """The --json structure mirrors the human report exactly."""
    return {
        "blockers_section": BLOCKERS_HEADER,
        "any_fail": any_fail(checks),
        "checks": [c.model_dump(mode="json") for c in checks],
    }


def main(argv: list[str] | None = None, *, checks: list[CheckResult] | None = None) -> int:
    """Module entry point: `python -m szl_estate.doctor`."""
    parser = argparse.ArgumentParser(
        prog="szl_estate.doctor",
        description="Environment/credential/DNS doctor. Exits 1 if any check is FAIL.",
    )
    parser.add_argument("--json", action="store_true", help="emit the structured report as JSON")
    args = parser.parse_args(argv)

    checks = run_all_checks() if checks is None else checks
    if args.json:
        print(json.dumps(payload(checks), indent=2))
    else:
        print(format_human(checks))
    return 1 if any_fail(checks) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
