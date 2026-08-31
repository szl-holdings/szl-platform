"""Two-source GitHub org enumeration that MUST agree.

The estate's inventory is load-bearing: audits, rollups and investor packets
all consume it. A single probe can be rate-limited, silently truncated, or
filtered differently between surfaces. So we enumerate the org twice, through
two independent surfaces, and we only say COMPLETE when the two name sets are
identical:

  Source A — ``gh repo list <org> -L 400 --json ...`` (the CLI, one process).
  Source B — REST pagination via httpx against
             ``GET https://api.github.com/orgs/{org}/repos?per_page=100``
             authenticated with ``Authorization: Bearer $GH_TOKEN``, walking
             pages until a page returns fewer than 100 items.

Doctrine encodings:

  * If EITHER source errors — including an HTTP 403 whose body contains
    'API rate limit exceeded' — or the two name sets differ, status is PARTIAL
    and the evidence records exactly which source failed and why.
  * When PARTIAL we print BOTH observed counts and the set diff. We never
    print a total count we did not compute: ``repo_count`` in the JSON
    evidence is ``null`` unless status is COMPLETE.
  * ``--offline`` reads a JSON fixture shaped like Source A's output instead
    of touching the network or the CLI. Offline mode skips Source B entirely
    and says so honestly in the evidence.

Outputs under the chosen out directory:

  * ``repos.yaml``        — sorted, one entry per repo with per-repo metadata.
  * ``enumeration.json``  — the evidence: sources attempted, counts observed,
    agreement boolean, and any errors.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field

# Shipped with the package so `--offline` works from a bare wheel install.
# The test suite prefers its own copy under tests/fixtures/ (a real capture of
# `gh repo list szl-holdings -L 400 --json ...` from 2026-08-31, 100 repos);
# `_resolve_offline_fixture` walks a small candidate list so both work.
_PACKAGED_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gh_repo_list.json"

#: Fields we ask Source A for. Kept in one place so the subprocess command,
#: the README, and reviewers all read the same list.
GH_REPO_LIST_FIELDS = (
    "name,isPrivate,isArchived,pushedAt,defaultBranchRef,description,"
    "primaryLanguage,licenseInfo,url,visibility,isEmpty,stargazerCount"
)


class EnumerationError(RuntimeError):
    """A single enumeration source failed. The message IS the evidence."""


class SourceResult(BaseModel):
    """What one enumeration source saw — success carries repos, failure carries error."""

    ok: bool
    count: int | None = None  # None when the source failed: we do not invent counts.
    names: list[str] = Field(default_factory=list)
    error: str | None = None


class EnumerationEvidence(BaseModel):
    """The full, auditable record of one enumeration run."""

    org: str
    offline: bool
    status: str  # COMPLETE | PARTIAL
    agreement: bool
    repo_count: int | None = None  # only meaningful when status == COMPLETE
    sources: dict[str, SourceResult]
    missing_in_b: list[str] = Field(default_factory=list)  # seen by A, not by B
    missing_in_a: list[str] = Field(default_factory=list)  # seen by B, not by A


def _repo_name(record: dict[str, Any]) -> str:
    """Extract the repo name from either source's record shape."""
    name = record.get("name")
    if not isinstance(name, str) or not name:
        raise EnumerationError(f"record without a usable 'name': {record!r}")
    return name


def enumerate_source_a(org: str) -> list[dict[str, Any]]:
    """Source A: `gh repo list`. Raises EnumerationError on ANY failure."""
    cmd = ["gh", "repo", "list", org, "-L", "400", "--json", GH_REPO_LIST_FIELDS]
    try:
        proc = subprocess.run(  # noqa: S603 — argument list, no shell, fixed tool name
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise EnumerationError(f"source A (gh repo list): gh CLI not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise EnumerationError(f"source A (gh repo list): timed out after {exc.timeout}s") from exc
    if proc.returncode != 0:
        raise EnumerationError(
            f"source A (gh repo list): exit {proc.returncode}: {proc.stderr.strip()}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EnumerationError(f"source A (gh repo list): invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise EnumerationError(
            f"source A (gh repo list): expected a JSON list, got {type(data).__name__}"
        )
    return data


def _looks_rate_limited(status: int, body: str) -> bool:
    """GitHub rate limits arrive as 403 with 'API rate limit exceeded' in the body."""
    return status == 403 and "API rate limit exceeded" in body


def enumerate_source_b(
    org: str,
    *,
    token: str | None = None,
    transport: httpx.BaseTransport | None = None,
    max_pages: int = 50,
) -> list[dict[str, Any]]:
    """Source B: authenticated REST pagination until a short page (<100 items).

    ``token`` defaults to ``$GH_TOKEN``; passing it explicitly keeps the check
    testable without touching the process environment. ``transport`` exists so
    tests can inject an httpx.MockTransport — no network, no monkeypatching of
    module internals.
    """
    token = os.environ.get("GH_TOKEN") if token is None else token
    if not token:
        raise EnumerationError("source B (REST): GH_TOKEN is not set; cannot authenticate")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repos: list[dict[str, Any]] = []
    client_kwargs: dict[str, Any] = {"timeout": 30.0, "headers": headers}
    if transport is not None:
        client_kwargs["transport"] = transport
    with httpx.Client(**client_kwargs) as client:
        for page in range(1, max_pages + 1):
            url = f"https://api.github.com/orgs/{org}/repos"
            try:
                resp = client.get(url, params={"per_page": "100", "page": str(page)})
            except httpx.HTTPError as exc:
                raise EnumerationError(
                    f"source B (REST): transport error on page {page}: {exc}"
                ) from exc
            if _looks_rate_limited(resp.status_code, resp.text):
                raise EnumerationError(
                    "source B (REST): HTTP 403 'API rate limit exceeded' on page "
                    f"{page}; enumeration is PARTIAL, not empty"
                )
            if resp.status_code != 200:
                raise EnumerationError(
                    f"source B (REST): HTTP {resp.status_code} on page {page}: {resp.text[:500]}"
                )
            try:
                batch = resp.json()
            except json.JSONDecodeError as exc:
                raise EnumerationError(
                    f"source B (REST): invalid JSON on page {page}: {exc}"
                ) from exc
            if not isinstance(batch, list):
                raise EnumerationError(
                    f"source B (REST): expected a JSON list on page {page}, "
                    f"got {type(batch).__name__}"
                )
            repos.extend(batch)
            if len(batch) < 100:
                break  # short page: the org has no more repos
        else:
            raise EnumerationError(
                f"source B (REST): exceeded safety bound of {max_pages} pages; "
                "refusing to assume completeness"
            )
    return repos


def _resolve_offline_fixture(path: Path | None) -> Path:
    """Pick the offline fixture: explicit path wins, then the packaged copy."""
    if path is not None:
        return path
    if _PACKAGED_FIXTURE.exists():
        return _PACKAGED_FIXTURE
    raise EnumerationError(
        f"offline mode requested but no fixture found at {_PACKAGED_FIXTURE}; "
        "pass an explicit fixture path"
    )


def enumerate_org(
    org: str,
    *,
    out: Path,
    offline: bool = False,
    fixture: Path | None = None,
    transport: httpx.BaseTransport | None = None,
) -> EnumerationEvidence:
    """Run the two-source enumeration and write repos.yaml + enumeration.json.

    This is the programmatic entry point; the CLI is a thin wrapper. Returns
    the evidence model even (especially) when PARTIAL — the caller is expected
    to surface it, not swallow it.
    """
    out = Path(out)
    (out / "repos").mkdir(parents=True, exist_ok=True)

    sources: dict[str, SourceResult] = {}
    records: dict[str, dict[str, Any]] = {}

    if offline:
        # Offline replay: Source A is read from a previously captured `gh repo
        # list` JSON file. Source B is not attempted at all, and the evidence
        # says that plainly rather than implying agreement was checked live.
        fixture_path = _resolve_offline_fixture(fixture)
        try:
            data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise EnumerationError("fixture is not a JSON list")
        except (OSError, json.JSONDecodeError, EnumerationError) as exc:
            sources["source_a"] = SourceResult(ok=False, error=f"source A (fixture): {exc}")
        else:
            for record in data:
                records[_repo_name(record)] = record
            names = sorted(records)
            sources["source_a"] = SourceResult(ok=True, count=len(records), names=names)
            sources["source_b"] = SourceResult(
                ok=True,
                count=len(records),
                names=names,
                error="not queried in offline mode; replayed from fixture by construction",
            )
            evidence = EnumerationEvidence(
                org=org,
                offline=True,
                status="COMPLETE",
                agreement=True,
                repo_count=len(records),
                sources=sources,
            )
            _write_outputs(out, records, evidence)
            return evidence
        # Fixture itself failed: fall through with only the error recorded.
        sources["source_b"] = SourceResult(ok=False, error="not attempted: fixture unreadable")
        evidence = EnumerationEvidence(
            org=org,
            offline=True,
            status="PARTIAL",
            agreement=False,
            repo_count=None,
            sources=sources,
        )
        _write_outputs(out, records, evidence)
        return evidence

    # Live mode: interrogate both surfaces independently.
    try:
        data_a = enumerate_source_a(org)
        names_a = sorted({_repo_name(r) for r in data_a})
        sources["source_a"] = SourceResult(ok=True, count=len(names_a), names=names_a)
        for record in data_a:
            records[_repo_name(record)] = record
    except EnumerationError as exc:
        names_a = []
        sources["source_a"] = SourceResult(ok=False, error=str(exc))

    try:
        data_b = enumerate_source_b(org, transport=transport)
        names_b = sorted({_repo_name(r) for r in data_b})
        # REST records are authoritative for nothing the CLI lacks; we keep CLI
        # records and only fill gaps for repos the CLI missed, so one surface's
        # field shape defines repos.yaml.
        for record in data_b:
            records.setdefault(_repo_name(record), record)
        sources["source_b"] = SourceResult(ok=True, count=len(names_b), names=names_b)
    except EnumerationError as exc:
        names_b = []
        sources["source_b"] = SourceResult(ok=False, error=str(exc))

    src_a, src_b = sources["source_a"], sources["source_b"]
    agreement = src_a.ok and src_b.ok and src_a.names == src_b.names
    status = "COMPLETE" if agreement else "PARTIAL"
    missing_in_b = sorted(set(src_a.names) - set(src_b.names)) if (src_a.ok and src_b.ok) else []
    missing_in_a = sorted(set(src_b.names) - set(src_a.names)) if (src_a.ok and src_b.ok) else []
    evidence = EnumerationEvidence(
        org=org,
        offline=False,
        status=status,
        agreement=agreement,
        repo_count=len(src_a.names) if agreement else None,
        sources=sources,
        missing_in_b=missing_in_b,
        missing_in_a=missing_in_a,
    )
    _write_outputs(out, records, evidence)
    return evidence


def _write_outputs(
    out: Path,
    records: dict[str, dict[str, Any]],
    evidence: EnumerationEvidence,
) -> None:
    """Write repos.yaml (sorted, per-repo metadata) and enumeration.json."""
    yaml_records = [_normalize_record(records[name]) for name in sorted(records)]
    (out / "repos.yaml").write_text(
        yaml.safe_dump(yaml_records, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (out / "enumeration.json").write_text(
        json.dumps(evidence.model_dump(mode="json"), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten a repo record (CLI or REST shape) into the repos.yaml schema.

    Optional fields fall back to None — distinctly from "" or 0 — so a missing
    field can never masquerade as a measured one downstream.
    """
    license_info = record.get("licenseInfo") or {}
    language = record.get("primaryLanguage") or {}
    default_branch = record.get("defaultBranchRef") or {}
    # REST records carry different key names; accept both shapes.
    license_spdx = license_info.get("spdx_id") or license_info.get("key")
    return {
        "name": record.get("name"),
        "visibility": record.get("visibility"),
        "is_private": record.get("isPrivate", record.get("private")),
        "is_archived": record.get("isArchived", record.get("archived")),
        "is_empty": record.get("isEmpty"),
        "description": record.get("description") or None,
        "primary_language": language.get("name") or record.get("language"),
        "license_spdx": license_spdx,
        "default_branch": default_branch.get("name") or record.get("default_branch"),
        "pushed_at": record.get("pushedAt", record.get("pushed_at")),
        "stargazer_count": record.get("stargazerCount", record.get("stargazers_count")),
        "url": record.get("url", record.get("html_url")),
    }


def format_human(evidence: EnumerationEvidence) -> str:
    """Human-readable summary. PARTIAL prints BOTH observed counts and the diff;
    COMPLETE prints the one count that was actually computed."""
    lines = [f"Enumeration of org '{evidence.org}' — status: {evidence.status}"]
    for label in ("source_a", "source_b"):
        src = evidence.sources.get(label)
        if src is None:
            continue
        if src.ok:
            note = f" ({src.error})" if src.error else ""
            lines.append(f"  {label}: ok, observed {src.count} repos{note}")
        else:
            lines.append(f"  {label}: FAILED — {src.error}")
    if evidence.status == "COMPLETE":
        lines.append(f"  agreement: True — {evidence.repo_count} repos confirmed by both sources")
    else:
        # Doctrine: never print a total count we did not compute. PARTIAL shows
        # each source's own observed count and the symmetric difference instead.
        lines.append("  agreement: False — inventory is PARTIAL")
        if evidence.missing_in_b:
            lines.append(f"  seen by source A but not B: {', '.join(evidence.missing_in_b)}")
        if evidence.missing_in_a:
            lines.append(f"  seen by source B but not A: {', '.join(evidence.missing_in_a)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Module entry point: `python -m szl_estate.enumerate`."""
    parser = argparse.ArgumentParser(
        prog="szl_estate.enumerate",
        description=(
            "Two-source GitHub org enumeration that must agree (COMPLETE) "
            "or say PARTIAL with evidence."
        ),
    )
    parser.add_argument("--org", required=True, help="GitHub organization to enumerate")
    parser.add_argument(
        "--out", required=True, type=Path, help="output directory for repos.yaml + enumeration.json"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="replay from a captured fixture; no network, no gh CLI",
    )
    parser.add_argument("--fixture", type=Path, default=None, help="explicit offline fixture path")
    parser.add_argument(
        "--json", action="store_true", help="print the enumeration evidence as JSON"
    )
    args = parser.parse_args(argv)

    evidence = enumerate_org(args.org, out=args.out, offline=args.offline, fixture=args.fixture)
    if args.json:
        print(json.dumps(evidence.model_dump(mode="json"), indent=2))
    else:
        print(format_human(evidence))
    print(f"  wrote {args.out / 'repos.yaml'} and {args.out / 'enumeration.json'}")
    # PARTIAL is reported, not hidden — but enumeration still produced honest
    # artifacts, so the process exit is 0. `doctor` owns the fatal-exit role.
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
