"""Recompute the org's public numeric claims. DRIFT is a finding, not a hunch.

The org README quotes numbers ("218/218 tests", "126 packages", "43 HF
models"). This module re-derives whatever can be re-derived and compares:

    PASS     observed == expected, observed computed IN THIS RUN
    DRIFT    observed != expected, observed computed in this run
             (a CLAIM_DRIFT finding is opened — severity HIGH)
    UNKNOWN  no recomputation exists, or the recomputation failed
             (static_expected claims are UNKNOWN BY CONSTRUCTION and the
             report says so; UNKNOWN is never PASS)

Output contract: a run of this tool never prints a number it did not itself
compute in that run. Claims that could not be recomputed print a "—" in the
Observed column and carry their expected value only as a quoted string.

Outputs: ``<out>/CLAIMS_REPORT.md`` and ``<out>/claims.json``.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel

from szl_estate import BLOCKERS_HEADER

_CLAIMS_YAML = Path(__file__).resolve().parent / "claims.yaml"

#: Claim ids whose numeric pair is reported as "observed/expected" text rather
#: than compared arithmetically — kept out of PASS entirely. Anything with a
#: static_expected check is UNKNOWN regardless.


class ClaimCheck(BaseModel):
    """How one claim is re-verified."""

    type: str  # static_expected | http_json | count_files
    note: str | None = None
    # http_json:
    url: str | None = None
    path: str | None = None  # dotted path into the JSON; "" / None = top-level array length
    # count_files:
    base_path: str | None = None
    glob: str | None = None


class Claim(BaseModel):
    """One seeded public claim. `expected` is verbatim from the source doc —
    a quoted claim string, which may embed non-numeric prose."""

    claim_id: str
    description: str
    source: str
    expected: Any
    check: ClaimCheck


class ClaimResult(BaseModel):
    """The verdict for one claim, with run-local evidence."""

    claim_id: str
    description: str
    source: str
    expected_quoted: str  # the claim as published, verbatim — never treated as ours
    verdict: str  # PASS | DRIFT | UNKNOWN
    observed: int | None = None  # only set when computed in this run
    evidence: str


def load_claims(path: Path | None = None) -> list[Claim]:
    """Load the seeded claims registry (packaged claims.yaml by default)."""
    raw = yaml.safe_load(Path(path or _CLAIMS_YAML).read_text(encoding="utf-8"))
    return [Claim.model_validate(item) for item in (raw or {}).get("claims", [])]


def _extract_number(text: str) -> int | float | None:
    """Pull the first numeric literal out of a quoted expected string.

    "1220/1220 across 76 packages" -> 1220 (the passing count); "<= 0.59 ms"
    -> 0.59. This parses the CLAIM for comparison purposes only; the original
    string is preserved in expected_quoted for display.
    """
    m = re.search(r"\d+(?:\.\d+)?", str(text))
    if not m:
        return None
    literal = m.group(0)
    return float(literal) if "." in literal else int(literal)


def _compare(expected: Any, observed: int | float) -> bool:
    """Observed (computed this run) vs the number parsed out of the claim."""
    expected_str = str(expected).strip()
    num = _extract_number(expected_str)
    if num is None:
        return False
    if expected_str.startswith("<="):
        return observed <= num
    # "1220/1220 ..." style: the numerator (passing count) is what we compare.
    return observed == num


def _resolve_dotted(payload: Any, path: str | None) -> Any:
    """Walk a dotted path through parsed JSON."""
    node = payload
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(node, dict):
            node = node[part]
        elif isinstance(node, list):
            node = node[int(part)]
        else:
            raise KeyError(f"cannot descend into {type(node).__name__} at '{part}'")
    return node


def _run_http_json(claim: Claim, *, client: httpx.Client | None = None) -> ClaimResult:
    """Fetch a URL, extract via dotted path, count/compare. Failure -> UNKNOWN."""
    url = claim.check.url or ""
    try:
        if client is not None:
            resp = client.get(url)
        else:
            with httpx.Client(timeout=30.0, follow_redirects=True) as owned:
                resp = owned.get(url)
    except httpx.HTTPError as exc:
        return ClaimResult(
            claim_id=claim.claim_id,
            description=claim.description,
            source=claim.source,
            expected_quoted=str(claim.expected),
            verdict="UNKNOWN",
            evidence=f"network failure fetching {url}: {exc}; claim left unverified",
        )
    if resp.status_code != 200:
        return ClaimResult(
            claim_id=claim.claim_id,
            description=claim.description,
            source=claim.source,
            expected_quoted=str(claim.expected),
            verdict="UNKNOWN",
            evidence=f"HTTP {resp.status_code} from {url}; claim left unverified",
        )
    try:
        node = _resolve_dotted(resp.json(), claim.check.path)
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        return ClaimResult(
            claim_id=claim.claim_id,
            description=claim.description,
            source=claim.source,
            expected_quoted=str(claim.expected),
            verdict="UNKNOWN",
            evidence=f"could not extract path '{claim.check.path}' from {url}: {exc}",
        )
    # Computed quantities only: length of a fetched list, or the node itself
    # if it is already numeric.
    if isinstance(node, list):
        observed: int | float = len(node)
    elif isinstance(node, (int, float)):
        observed = node
    else:
        return ClaimResult(
            claim_id=claim.claim_id,
            description=claim.description,
            source=claim.source,
            expected_quoted=str(claim.expected),
            verdict="UNKNOWN",
            evidence=(
                f"extracted value at '{claim.check.path}' is {type(node).__name__}, not countable"
            ),
        )
    verdict = "PASS" if _compare(claim.expected, observed) else "DRIFT"
    return ClaimResult(
        claim_id=claim.claim_id,
        description=claim.description,
        source=claim.source,
        expected_quoted=str(claim.expected),
        verdict=verdict,
        observed=int(observed),
        evidence=(
            f"computed len of JSON array at {url} in this run"
            if isinstance(node, list)
            else f"read numeric node '{claim.check.path}' from {url} in this run"
        ),
    )


def _run_count_files(claim: Claim, *, base_dir: Path | None = None) -> ClaimResult:
    """Offline recomputation: count files matching a glob under a path."""
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    root = base / claim.check.base_path if claim.check.base_path else base
    if not root.exists():
        return ClaimResult(
            claim_id=claim.claim_id,
            description=claim.description,
            source=claim.source,
            expected_quoted=str(claim.expected),
            verdict="UNKNOWN",
            evidence=f"path {root} does not exist; nothing counted",
        )
    pattern = claim.check.glob or "*"
    # fnmatch over relative paths keeps the glob semantics explicit and
    # dependency-free; rglob("*") + match also handles '*/*.toml' on py<3.13.
    observed = sum(
        1
        for candidate in root.rglob("*")
        if candidate.is_file() and fnmatch.fnmatch(str(candidate.relative_to(root)), pattern)
    )
    verdict = "PASS" if _compare(claim.expected, observed) else "DRIFT"
    return ClaimResult(
        claim_id=claim.claim_id,
        description=claim.description,
        source=claim.source,
        expected_quoted=str(claim.expected),
        verdict=verdict,
        observed=observed,
        evidence=f"counted files matching '{pattern}' under {root} in this run",
    )


def run_claim(
    claim: Claim,
    *,
    client: httpx.Client | None = None,
    base_dir: Path | None = None,
) -> ClaimResult:
    """Dispatch one claim to its checker. UNKNOWN by default; never guess."""
    if claim.check.type == "static_expected":
        # Doctrine: no local recompute exists, so this tool CANNOT pass the
        # claim. The verdict is UNKNOWN and the note explains why.
        note = claim.check.note or "no local recomputation exists for this claim"
        return ClaimResult(
            claim_id=claim.claim_id,
            description=claim.description,
            source=claim.source,
            expected_quoted=str(claim.expected),
            verdict="UNKNOWN",
            evidence=f"static_expected (not recomputed): {note}",
        )
    if claim.check.type == "http_json":
        return _run_http_json(claim, client=client)
    if claim.check.type == "count_files":
        return _run_count_files(claim, base_dir=base_dir)
    return ClaimResult(
        claim_id=claim.claim_id,
        description=claim.description,
        source=claim.source,
        expected_quoted=str(claim.expected),
        verdict="UNKNOWN",
        evidence=f"unknown check type '{claim.check.type}'; claim left unverified",
    )


def run_all(
    claims: list[Claim] | None = None,
    *,
    client: httpx.Client | None = None,
    base_dir: Path | None = None,
) -> list[ClaimResult]:
    """Verify every seeded claim, in registry order."""
    claims = load_claims() if claims is None else claims
    return [run_claim(c, client=client, base_dir=base_dir) for c in claims]


def _render_report(results: list[ClaimResult]) -> str:
    """CLAIMS_REPORT.md: blockers header (drifts first), then the full table."""
    findings = [
        {
            "severity": "HIGH",
            "code": "CLAIM_DRIFT",
            "claim_id": r.claim_id,
            "detail": f"expected '{r.expected_quoted}', observed {r.observed}: {r.evidence}",
        }
        for r in results
        if r.verdict == "DRIFT"
    ]
    lines = [
        "# Claims verification report",
        "",
        f"Claims checked: {len(results)}",
        "",
        f"## {BLOCKERS_HEADER}",
        "",
    ]
    if findings:
        lines += [
            f"- **{f['severity']}** `{f['code']}` — `{f['claim_id']}`: {f['detail']}"
            for f in findings
        ]
    else:
        lines.append("No CLAIM_DRIFT findings in this run.")
    lines += [
        "",
        "## Claim table",
        "",
        "| Claim | Expected (quoted) | Observed | Verdict | Evidence |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        observed_cell = str(r.observed) if r.observed is not None else "—"
        evidence = r.evidence.replace("|", "\\|")
        lines.append(
            f"| {r.claim_id} | {r.expected_quoted} | {observed_cell} | {r.verdict} | {evidence} |"
        )
    lines += [
        "",
        "_Observed is em-dash when the claim was not recomputed in this run; "
        "static_expected claims are UNKNOWN by construction and are never PASS._",
        "",
    ]
    return "\n".join(lines)


def verify(
    out: Path,
    *,
    client: httpx.Client | None = None,
    base_dir: Path | None = None,
    claims: list[Claim] | None = None,
) -> list[ClaimResult]:
    """Run all claims and write CLAIMS_REPORT.md + claims.json."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    results = run_all(claims, client=client, base_dir=base_dir)
    (out / "CLAIMS_REPORT.md").write_text(_render_report(results), encoding="utf-8")
    drift_findings = [
        {
            "severity": "HIGH",
            "code": "CLAIM_DRIFT",
            "claim_id": r.claim_id,
            "detail": f"expected '{r.expected_quoted}', observed {r.observed}",
        }
        for r in results
        if r.verdict == "DRIFT"
    ]
    payload = {
        "results": [r.model_dump(mode="json") for r in results],
        "findings": drift_findings,
    }
    (out / "claims.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    """Module entry point: `python -m szl_estate.verify_claims`."""
    parser = argparse.ArgumentParser(
        prog="szl_estate.verify_claims",
        description="Recompute the org's public numeric claims. UNKNOWN is never PASS.",
    )
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    args = parser.parse_args(argv)

    results = verify(args.out)
    if args.json:
        print(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
    else:
        pass_count = sum(1 for r in results if r.verdict == "PASS")
        drift = [r.claim_id for r in results if r.verdict == "DRIFT"]
        unknown = sum(1 for r in results if r.verdict == "UNKNOWN")
        print(f"Claims: {pass_count} PASS, {len(drift)} DRIFT, {unknown} UNKNOWN of {len(results)}")
        if drift:
            print(f"  CLAIM_DRIFT opened for: {', '.join(drift)}")
        print(f"  wrote {args.out / 'CLAIMS_REPORT.md'} and {args.out / 'claims.json'}")
    # DRIFT is a measurement outcome; the tool exits 0 when it measured honestly.
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
