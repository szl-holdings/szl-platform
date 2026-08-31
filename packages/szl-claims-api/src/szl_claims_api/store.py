"""The claims store: strict loading of the claims file, honest degradation.

The output contract with szl-estate is a FILE, not an import. This module
reads one JSON document — a top-level list of claim records — and treats it
as the only source of numbers the API may serve. The service never computes
claim values itself; when there is nothing honest to serve, it degrades:

    OK           file present and strictly valid — claims served verbatim
    UNAVAILABLE  file missing (or unreadable) — seeded claims, all UNKNOWN
    INVALID      file failed strict validation — seeded claims, all UNKNOWN

UNKNOWN is a first-class state here, not an error: an UNAVAILABLE store still
answers with every seeded claim marked UNKNOWN and a note explaining why.
Fabricated numbers are structurally impossible — in degraded states the only
numbers present at all are the quoted ``expected`` claims attributed to
their sources.

The optional estate boundary: :func:`refresh_from_estate` invokes
``szl_estate.verify_claims.verify()`` to rewrite the claims file when that
package is importable. Any failure — import, permission, network — returns
``(False, note)``; the store simply keeps reading whatever file exists.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from szl_claims_api.seed import load_seed_registry, seeded_unknown_claims

__all__ = [
    "BLOCKERS_HEADER",
    "CLAIMS_FILE_ENV_VAR",
    "ClaimsFileError",
    "ClaimStore",
    "DEFAULT_CLAIMS_FILE",
    "STORE_STATES",
    "StoreStats",
    "default_claims_file_path",
    "refresh_from_estate",
    "validate_claim_records",
]

#: Environment variable pointing at the claims file.
CLAIMS_FILE_ENV_VAR = "SZL_CLAIMS_FILE"

#: Default claims file location, relative to the process working directory.
DEFAULT_CLAIMS_FILE = Path("artifacts") / "claims" / "claims.json"

#: Closed store-state vocabulary. DEGRADED_STATES: everything but OK.
STORE_STATES: tuple[str, ...] = ("OK", "UNAVAILABLE", "INVALID")

#: Closed claim-verdict vocabulary, per the claims-file contract.
VERDICTS: tuple[str, ...] = ("PASS", "DRIFT", "UNKNOWN")

#: Top-of-report header when any claim has drifted. Matches the estate
#: doctrine constant verbatim, duplicated deliberately: the contract with
#: szl-estate is file-based, so this package must not import it.
BLOCKERS_HEADER = "BLOCKERS THAT OUTRANK ALL COSMETIC WORK"

#: Every claims-file record carries exactly these keys — no fewer, no more.
CLAIM_KEYS = (
    "claim_id",
    "description",
    "source",
    "expected",
    "observed",
    "verdict",
    "evidence",
    "last_run",
)

#: The estate's wire-timestamp grammar: ISO-8601 with a mandatory timezone.
_ISO_UTC_RE = re.compile(
    r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})\Z"
)


def default_claims_file_path() -> Path:
    """Claims file path: SZL_CLAIMS_FILE when set, else the default location."""
    return Path(os.environ.get(CLAIMS_FILE_ENV_VAR, DEFAULT_CLAIMS_FILE))


class ClaimsFileError(ValueError):
    """The claims file failed strict validation. Carries every finding."""

    def __init__(self, findings: list[str]) -> None:
        self.findings = list(findings)
        joined = "; ".join(self.findings)
        super().__init__(f"claims file is invalid ({len(findings)} findings): {joined}")


def _valid_last_run(value: Any) -> bool:
    """Timezone-aware ISO-8601 that names a real calendar moment."""
    if not isinstance(value, str) or _ISO_UTC_RE.match(value) is None:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_claim_records(data: Any) -> list[dict[str, Any]]:
    """Validate claims-file JSON strictly; return the records or raise.

    Strict means: the document is a list; every record has exactly
    CLAIM_KEYS; ids are unique non-empty strings; verdict is in the closed
    vocabulary; and the honesty invariants hold —

      * PASS/DRIFT require observed != null AND a real last_run timestamp
        (a verdict names a run, and a run names a number);
      * UNKNOWN requires observed == null (you cannot know a number you
        did not compute).
    """
    findings: list[str] = []
    if not isinstance(data, list):
        raise ClaimsFileError([f"top level must be a list, got {type(data).__name__}"])
    if any(not isinstance(item, dict) for item in data):
        bad = next(i for i, item in enumerate(data) if not isinstance(item, dict))
        raise ClaimsFileError([f"records[{bad}] must be an object"])

    seen: set[str] = set()
    for index, record in enumerate(data):
        where = f"records[{index}]"
        claim_id = record.get("claim_id")
        if isinstance(claim_id, str) and claim_id:
            where = f"records[{index}] ({claim_id!r})"

        keys = set(record.keys())
        for key in sorted(set(CLAIM_KEYS) - keys):
            findings.append(f"{where}: missing key: {key}")
        for key in sorted(keys - set(CLAIM_KEYS)):
            findings.append(f"{where}: unexpected key: {key}")

        if not isinstance(claim_id, str) or not claim_id:
            findings.append(f"{where}: claim_id must be a non-empty string")
        elif claim_id in seen:
            findings.append(f"{where}: duplicate claim_id {claim_id!r}")
        else:
            seen.add(claim_id)

        for field_name in ("description", "source", "evidence"):
            if not isinstance(record.get(field_name), str) or not record[field_name]:
                findings.append(f"{where}: {field_name} must be a non-empty string")

        if record.get("expected") is None:
            findings.append(f"{where}: expected must not be null — it is the claim itself")

        verdict = record.get("verdict")
        if verdict not in VERDICTS:
            findings.append(
                f"{where}: verdict must be one of PASS|DRIFT|UNKNOWN, got {verdict!r}"
            )
            continue  # Honesty invariants depend on a known verdict.

        observed = record.get("observed")
        if isinstance(observed, bool):  # bool is an int in Python; reject explicitly.
            findings.append(f"{where}: observed must be int/float/str or null, not bool")
        elif observed is not None and not isinstance(observed, (int, float, str)):
            findings.append(
                f"{where}: observed must be int/float/str or null, "
                f"got {type(observed).__name__}"
            )

        last_run = record.get("last_run")
        if last_run is not None and not _valid_last_run(last_run):
            findings.append(
                f"{where}: last_run must be timezone-aware ISO-8601 or null, "
                f"got {last_run!r}"
            )

        if verdict == "UNKNOWN":
            if observed is not None:
                findings.append(
                    f"{where}: verdict UNKNOWN forbids a non-null observed "
                    "— you cannot know a number you did not compute"
                )
        else:
            if observed is None:
                findings.append(
                    f"{where}: verdict {verdict} requires a non-null observed "
                    "— a verdict names a number"
                )
            if last_run is None:
                findings.append(
                    f"{where}: verdict {verdict} requires a non-null last_run "
                    "— a verdict names a run"
                )

    if findings:
        raise ClaimsFileError(findings)
    return list(data)


@dataclass(frozen=True)
class StoreStats:
    """Aggregate counts by verdict — arithmetic over loaded data, never claims."""

    total: int = 0
    passed: int = 0
    drift: int = 0
    unknown: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "PASS": self.passed,
            "DRIFT": self.drift,
            "UNKNOWN": self.unknown,
        }


def _degraded_state_note(state: str, detail: str) -> str:
    if state == "UNAVAILABLE":
        return (
            f"claims file {detail} is missing or unreadable; serving the seeded "
            "registry with every claim UNKNOWN — no numbers have been recomputed. "
            "Run `python -m szl_claims_api seed --out <dir>` to initialize, or "
            "`python -m szl_estate verify-claims --out <dir>` to recompute."
        )
    return (
        f"claims file failed strict validation and was refused ({detail}); serving "
        "the seeded registry with every claim UNKNOWN — an invalid file must never "
        "be laundered into served numbers."
    )


@dataclass
class ClaimStore:
    """The claims file, loaded and validated — or an honest degraded state.

    ``loader`` is injectable for tests: ``path -> parsed JSON``. The default
    reads UTF-8 JSON from disk. OSError and JSONDecodeError degrade to
    UNAVAILABLE; ClaimsFileError degrades to INVALID. Either way the API
    keeps answering with every seeded claim marked UNKNOWN.
    """

    path: Path
    loader: Callable[[Path], Any] | None = None
    _claims: list[dict[str, Any]] = field(init=False, repr=False, default_factory=list)
    _state: str = field(init=False, repr=False, default="OK")
    _note: str | None = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        load = self.loader or self._read_json
        try:
            data = load(self.path)
        except (OSError, json.JSONDecodeError) as exc:
            self._degrade(
                "UNAVAILABLE", _degraded_state_note("UNAVAILABLE", f"{self.path} ({exc})")
            )
        else:
            try:
                self._claims = validate_claim_records(data)
            except ClaimsFileError as exc:
                self._degrade(
                    "INVALID", _degraded_state_note("INVALID", "; ".join(exc.findings))
                )
            else:
                self._state = "OK"
                self._note = None
        self._by_id = {claim["claim_id"]: claim for claim in self._claims}

    @staticmethod
    def _read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _degrade(self, state: str, note: str) -> None:
        self._claims = seeded_unknown_claims()
        self._state = state
        self._note = note

    @property
    def state(self) -> str:
        """OK | UNAVAILABLE | INVALID."""
        return self._state

    @property
    def ok(self) -> bool:
        return self._state == "OK"

    @property
    def note(self) -> str | None:
        """Human explanation of a degraded state; None when OK."""
        return self._note

    def get_all(self) -> list[dict[str, Any]]:
        """Every claim record, verbatim from the claims file (or seeded UNKNOWNs)."""
        return list(self._claims)

    def get_one(self, claim_id: str) -> dict[str, Any] | None:
        """One claim by id, or None when the id is not claimed at all."""
        return self._by_id.get(claim_id)

    def stats(self) -> StoreStats:
        """Counts by verdict over the served claims."""
        passed = sum(1 for c in self._claims if c["verdict"] == "PASS")
        drift = sum(1 for c in self._claims if c["verdict"] == "DRIFT")
        unknown = sum(1 for c in self._claims if c["verdict"] == "UNKNOWN")
        return StoreStats(total=len(self._claims), passed=passed, drift=drift, unknown=unknown)


def _adapt_estate_claims_file(
    estate_file: Path, *, last_run: str
) -> list[dict[str, Any]]:
    """File-to-file adapter: szl-estate's claims.json -> this service's schema.

    The estate runner writes ``{"results": [...], "findings": [...]}`` where a
    result carries ``expected_quoted`` and no ``last_run``. This service's
    contract is a bare list of eight-key records. The adapter bridges the two
    file formats — the ONLY sanctioned coupling, and it is file-based: no
    estate type is imported, no number is recomputed here (values are copied
    verbatim from the estate's file; ``last_run`` is stamped with the refresh
    run's completion time, which is when the recomputation happened).

    Typed ``expected`` values are restored from this package's seed registry
    when the claim_id is known there (the estate quotes every expected value
    as a string); seed claims the estate does not know are merged in as
    UNKNOWN, so a refresh can never silently drop a public claim.
    """
    raw = json.loads(estate_file.read_text(encoding="utf-8"))
    if isinstance(raw, list):  # already in this service's schema
        return validate_claim_records(raw)
    if not isinstance(raw, dict) or not isinstance(raw.get("results"), list):
        raise ValueError(
            "unrecognized claims payload: expected a list of records or an "
            "object with a 'results' list"
        )
    seed_by_id = {entry["claim_id"]: entry for entry in load_seed_registry()}
    records: list[dict[str, Any]] = []
    for index, result in enumerate(raw["results"]):
        if not isinstance(result, dict):
            raise ValueError(f"results[{index}] must be an object")
        claim_id = result.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError(f"results[{index}].claim_id must be a non-empty string")
        seed = seed_by_id.get(claim_id)
        records.append(
            {
                "claim_id": claim_id,
                "description": str(
                    result.get("description") or (seed or {}).get("description", "")
                ),
                "source": str(result.get("source") or (seed or {}).get("source", "")),
                "expected": (seed or {}).get("expected", result.get("expected_quoted")),
                "observed": result.get("observed"),
                "verdict": result.get("verdict"),
                "evidence": str(result.get("evidence") or "recomputed by szl-estate"),
                # The refresh run happened at last_run for every claim —
                # including UNKNOWNs (a failed recomputation is still a run).
                "last_run": last_run,
            }
        )
    covered = {r["claim_id"] for r in records}
    for entry in load_seed_registry():
        if entry["claim_id"] not in covered:
            records.append(
                {
                    "claim_id": entry["claim_id"],
                    "description": entry["description"],
                    "source": entry["source"],
                    "expected": entry["expected"],
                    "observed": None,
                    "verdict": "UNKNOWN",
                    "evidence": "not covered by the szl-estate refresh run; claim left unverified",
                    "last_run": None,
                }
            )
    return validate_claim_records(records)


def refresh_from_estate(out_dir: str | Path) -> tuple[bool, str]:
    """Optional boundary: ask szl-estate to recompute and rewrite the claims file.

    Runs ``szl_estate.verify_claims.verify()`` into a temporary directory,
    adapts its claims file into this service's schema (file-to-file — no
    estate internals imported beyond the runner's public entry point),
    strictly validates the result, and only then atomically replaces
    ``<out_dir>/claims.json``. Every failure mode — szl-estate not installed,
    the runner raising, an output that fails validation — returns
    ``(False, note)`` and leaves the existing claims file byte-identical:
    this service degrades, it never fabricates.
    """
    try:
        module = importlib.import_module("szl_estate.verify_claims")
        verify = getattr(module, "verify", None)
        if not callable(verify):
            raise AttributeError("szl_estate.verify_claims.verify")
    except (ImportError, AttributeError) as exc:
        return (
            False,
            f"szl-estate refresh unavailable ({exc}); existing claims file, if any, "
            "continues to be served",
        )
    out = Path(out_dir)
    try:
        with tempfile.TemporaryDirectory(prefix="szl-claims-refresh-") as tmp:
            tmp_claims = Path(tmp) / "claims.json"
            verify(Path(tmp))
            finished_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            records = _adapt_estate_claims_file(tmp_claims, last_run=finished_at)
        out.mkdir(parents=True, exist_ok=True)
        staging = out / f".claims.json.{os.getpid()}.tmp"
        staging.write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(staging, out / "claims.json")  # atomic on POSIX
    except Exception as exc:  # noqa: BLE001 — the boundary must never crash the service
        return (
            False,
            f"szl-estate refresh failed ({type(exc).__name__}: {exc}); existing claims "
            "file, if any, continues to be served unchanged",
        )
    return (
        True,
        f"szl-estate recomputed {len(records)} claims; claims file rewritten at "
        f"{out / 'claims.json'} (validated strictly before replacing)",
    )
