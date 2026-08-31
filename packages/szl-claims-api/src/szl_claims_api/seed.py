"""Seed registry — the org's public claims, before any recomputation.

The packaged ``claims_registry.seed.json`` records every public numeric
claim SZL Holdings makes, with the source that made it. Seeding turns each
entry into a full claims-file record in the only honest initial state:

    observed = null, verdict = UNKNOWN, last_run = null

— because this service has not recomputed anything, and UNKNOWN is never
PASS. Numbers appear only after ``szl-estate verify-claims`` (or any runner
honoring the same file contract) recomputes them and writes the claims file.

This module is deliberately standalone (stdlib only): the store depends on
it for the UNAVAILABLE/INVALID fallback, so it must not depend back.
"""

from __future__ import annotations

import importlib.resources
import json
from pathlib import Path
from typing import Any

__all__ = [
    "SEED_RESOURCE",
    "SeedRegistryError",
    "load_seed_registry",
    "seed_claims",
    "seeded_unknown_claims",
]

#: Packaged seed registry shipped as package data (see pyproject.toml).
SEED_RESOURCE = "claims_registry.seed.json"

_SEED_ENTRY_KEYS = frozenset({"claim_id", "description", "source", "expected"})


class SeedRegistryError(ValueError):
    """The packaged seed registry failed validation — a build-time bug."""


def load_seed_registry() -> list[dict[str, Any]]:
    """Load the packaged seed registry, validating its shape strictly.

    Raises SeedRegistryError on any deviation: the seed is authored data,
    and a malformed seed is a packaging bug, not an operational event.
    """
    text = (
        importlib.resources.files("szl_claims_api")
        .joinpath(SEED_RESOURCE)
        .read_text(encoding="utf-8")
    )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - packaging bug
        raise SeedRegistryError(f"{SEED_RESOURCE} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise SeedRegistryError(f"{SEED_RESOURCE} must be an object with a 'claims' list")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(data["claims"]):
        where = f"seed claims[{index}]"
        if not isinstance(entry, dict):
            raise SeedRegistryError(f"{where} must be an object")
        keys = set(entry.keys())
        missing = sorted(_SEED_ENTRY_KEYS - keys)
        if missing:
            raise SeedRegistryError(f"{where} is missing keys: {', '.join(missing)}")
        claim_id = entry["claim_id"]
        if not isinstance(claim_id, str) or not claim_id:
            raise SeedRegistryError(f"{where}.claim_id must be a non-empty string")
        if claim_id in seen:
            raise SeedRegistryError(f"duplicate seed claim_id: {claim_id!r}")
        seen.add(claim_id)
        for field in ("description", "source"):
            if not isinstance(entry[field], str) or not entry[field]:
                raise SeedRegistryError(f"{where}.{field} must be a non-empty string")
        if entry["expected"] is None:
            raise SeedRegistryError(f"{where}.expected must not be null — it is the claim")
        entries.append(
            {
                "claim_id": claim_id,
                "description": entry["description"],
                "source": entry["source"],
                "expected": entry["expected"],
            }
        )
    return entries


def seeded_unknown_claims() -> list[dict[str, Any]]:
    """Full claims-file records in the honest initial state: all UNKNOWN.

    ``evidence`` says exactly why there is no number yet; ``expected`` stays
    a quoted claim attributed to its source — never a measurement.
    """
    return [
        {
            "claim_id": entry["claim_id"],
            "description": entry["description"],
            "source": entry["source"],
            "expected": entry["expected"],
            "observed": None,
            "verdict": "UNKNOWN",
            "evidence": (
                f"seeded from {SEED_RESOURCE}; awaiting recomputation by "
                "szl-estate — no run has verified this claim"
            ),
            "last_run": None,
        }
        for entry in load_seed_registry()
    ]


def seed_claims(out_dir: str | Path) -> Path:
    """Write ``<out_dir>/claims.json`` from the seed registry. Returns the path.

    The written file passes the store's strict validation by construction;
    the CLI re-loads it through :class:`szl_claims_api.store.ClaimStore` as a
    round-trip check before reporting success.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "claims.json"
    path.write_text(
        json.dumps(seeded_unknown_claims(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
