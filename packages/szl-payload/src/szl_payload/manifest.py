"""Manifest loading and validation — the build contract.

The manifest carries an explicit, ordered ``[[sections]]`` list of
``{id, path, must_contain}`` entries. It is NEVER a glob: a glob silently
reorders sections and DNS stops being Phase -1. Ordering is doctrine, not
presentation, so this module validates the contract strictly and fails
closed on anything it cannot prove.
"""

from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path


class ManifestError(Exception):
    """Raised when the manifest is missing, malformed, or violates the contract."""


# Characters that would make a section path a glob rather than an explicit
# file reference. Any of them in a section path rejects the manifest.
_GLOB_CHARS = frozenset("*?[")

MANIFEST_FILENAME = "manifest.toml"


@dataclasses.dataclass(frozen=True)
class Section:
    """One ordered section entry: identity, source path, token assertions."""

    id: str
    path: str
    must_contain: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Manifest:
    """The parsed, validated build contract."""

    root: Path  # package root the manifest was loaded from
    sections: tuple[Section, ...]  # explicit build order — never sorted, never globbed
    output_path: str  # e.g. "dist/SZL_MASTER_PAYLOAD_V14.md"
    export_dir: str  # e.g. "dist/export"
    embed_build_time_in_body: bool  # contract requires False
    publication_eligible: bool  # computed elsewhere; serialized verbatim
    require_dns_first: bool
    forbidden_patterns_path: str
    banned_claims_path: str

    @property
    def output_file(self) -> Path:
        """Absolute path of the built payload document."""
        return self.root / self.output_path

    @property
    def export_path(self) -> Path:
        """Absolute path of the export directory."""
        return self.root / self.export_dir

    @property
    def section_ids(self) -> tuple[str, ...]:
        """Section ids in build order."""
        return tuple(section.id for section in self.sections)


def _require_str(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{where}: {key!r} must be a non-empty string")
    return value


def _require_bool(table: dict, key: str, where: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise ManifestError(f"{where}: {key!r} must be a boolean")
    return value


def _check_explicit_path(path: str, where: str) -> None:
    """Reject globs and absolute paths in manifest file references."""
    if any(char in _GLOB_CHARS for char in path):
        raise ManifestError(
            f"{where}: {path!r} contains a glob character — sections must be an "
            "explicit ordered list (a glob silently reorders and DNS stops being Phase -1)"
        )
    if Path(path).is_absolute():
        raise ManifestError(f"{where}: {path!r} must be relative to the package root")


def load_manifest(root: Path | str) -> Manifest:
    """Load and validate ``manifest.toml`` from *root*.

    Fails closed: any malformed table, glob character, duplicate id, or
    contract violation raises ManifestError and nothing is built.
    """
    root = Path(root)
    manifest_file = root / MANIFEST_FILENAME
    if not manifest_file.is_file():
        raise ManifestError(f"manifest not found: {manifest_file}")
    try:
        data = tomllib.loads(manifest_file.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise ManifestError(f"cannot parse {manifest_file}: {exc}") from exc

    # [output] — where the built document is written.
    output = data.get("output")
    if not isinstance(output, dict):
        raise ManifestError("manifest: missing [output] table")
    output_path = _require_str(output, "path", "[output]")
    _check_explicit_path(output_path, "[output].path")

    # [export] — export directory and determinism contract.
    export = data.get("export")
    if not isinstance(export, dict):
        raise ManifestError("manifest: missing [export] table")
    export_dir = _require_str(export, "dir", "[export]")
    _check_explicit_path(export_dir, "[export].dir")
    embed_build_time = export.get("embed_build_time_in_body", False)
    if embed_build_time is not False:
        # Determinism doctrine: build time lives only in the export receipt.
        # Allowing it in the body would void the idempotency proof.
        raise ManifestError(
            "[export].embed_build_time_in_body must be false — build time lives only "
            "in the export receipt; a timestamped body voids the idempotency proof"
        )
    publication_eligible = export.get("publication_eligible", False)
    if not isinstance(publication_eligible, bool):
        raise ManifestError("[export].publication_eligible must be a boolean")

    # [gates] — compile-failure conditions.
    gates = data.get("gates")
    if not isinstance(gates, dict):
        raise ManifestError("manifest: missing [gates] table")
    require_dns_first = _require_bool(gates, "require_dns_first", "[gates]")
    forbidden_patterns = _require_str(gates, "forbidden_patterns", "[gates]")
    banned_claims = _require_str(gates, "banned_claims", "[gates]")
    _check_explicit_path(forbidden_patterns, "[gates].forbidden_patterns")
    _check_explicit_path(banned_claims, "[gates].banned_claims")

    # [[sections]] — the explicit ordered list. Never a glob.
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ManifestError(
            "manifest: [[sections]] must be a non-empty explicit ordered list — never a glob"
        )
    sections: list[Section] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_sections):
        where = f"[[sections]] entry {index}"
        if not isinstance(raw, dict):
            raise ManifestError(f"{where}: must be a table")
        section_id = _require_str(raw, "id", where)
        path = _require_str(raw, "path", where)
        _check_explicit_path(path, f"{where}.path")
        must_contain_raw = raw.get("must_contain", [])
        if not isinstance(must_contain_raw, list) or not all(
            isinstance(token, str) and token for token in must_contain_raw
        ):
            raise ManifestError(f"{where}: must_contain must be a list of non-empty strings")
        if section_id in seen_ids:
            raise ManifestError(f"{where}: duplicate section id {section_id!r}")
        seen_ids.add(section_id)
        sections.append(
            Section(id=section_id, path=path, must_contain=tuple(must_contain_raw))
        )

    return Manifest(
        root=root,
        sections=tuple(sections),
        output_path=output_path,
        export_dir=export_dir,
        embed_build_time_in_body=False,
        publication_eligible=publication_eligible,
        require_dns_first=require_dns_first,
        forbidden_patterns_path=forbidden_patterns,
        banned_claims_path=banned_claims,
    )
