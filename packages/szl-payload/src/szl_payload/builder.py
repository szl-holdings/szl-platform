"""Builder — compile sections/ into dist/SZL_MASTER_PAYLOAD_V14.md.

The build is a pure function of the sections plus the manifest: no
timestamps, no randomness, no environment reads. That purity is what makes
the idempotency proof (build → copy → rebuild → byte-identical diff)
meaningful, so nothing in this module consults the clock, the network, or
the environment.

Assembly rule per section, in manifest order:

    <!-- section:<id> sha256:<hex of exact section bytes> -->

    <verbatim section bytes>

Gates run over the section texts (must_contain, require_dns_first) and over
the assembled document (forbidden patterns, banned claims, compound rules).
Any finding fails the compile and NOTHING is written — a partial payload is
worse than no payload.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

from . import __version__, gates
from .manifest import Manifest, ManifestError

PAYLOAD_TITLE = "SZL MASTER PAYLOAD V14"
PAYLOAD_SUBTITLE = "Deterministic build — sections/ is source, dist/ is derived"


class BuildError(Exception):
    """Operational build failure (missing section files, I/O, bad manifest)."""


def sha256_bytes(data: bytes) -> str:
    """Hex sha256 of *data* — the only digest primitive the payload uses."""
    return hashlib.sha256(data).hexdigest()


@dataclasses.dataclass(frozen=True)
class SectionDigest:
    """Digest record for one section: id, source path, sha256 of exact bytes."""

    id: str
    path: str
    sha256: str


@dataclasses.dataclass(frozen=True)
class BuildResult:
    """What a successful compile produced."""

    output_path: Path
    document: str
    payload_sha256: str
    sections: tuple[SectionDigest, ...]


def section_comment(section_id: str, digest: str) -> str:
    """The inline per-section digest comment format (single canonical form)."""
    return f"<!-- section:{section_id} sha256:{digest} -->"


def load_section_texts(manifest: Manifest) -> dict[str, tuple[str, str]]:
    """Read every section file in manifest order.

    Returns section id → (path, text). Any missing file fails the build
    closed: a payload missing a doctrine section is a false document.
    """
    texts: dict[str, tuple[str, str]] = {}
    for section in manifest.sections:
        section_file = manifest.root / section.path
        if not section_file.is_file():
            raise BuildError(f"section {section.id!r}: file not found: {section_file}")
        try:
            texts[section.id] = (section.path, section_file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise BuildError(f"section {section.id!r}: cannot read {section_file}: {exc}") from exc
    return texts


def render_document(
    manifest: Manifest, section_texts: dict[str, tuple[str, str]]
) -> tuple[str, tuple[SectionDigest, ...]]:
    """Assemble the document from sections in manifest order (pure function)."""
    parts: list[str] = [
        f"# {PAYLOAD_TITLE}",
        "",
        PAYLOAD_SUBTITLE,
        "",
        (
            "Assembly: deterministic function of sections/ + manifest.toml "
            "(szl-payload " + __version__ + "). No timestamps, no randomness. "
            "UNKNOWN is never PASS."
        ),
        "",
        "---",
    ]
    digests: list[SectionDigest] = []
    for section in manifest.sections:
        path, text = section_texts[section.id]
        digest = sha256_bytes(text.encode("utf-8"))
        digests.append(SectionDigest(id=section.id, path=path, sha256=digest))
        parts.append("")
        parts.append(section_comment(section.id, digest))
        parts.append("")
        parts.append(text.rstrip("\n"))
        parts.append("")
        parts.append("---")
    document = "\n".join(parts) + "\n"
    return document, tuple(digests)


def compile_payload(manifest: Manifest, *, write: bool = True) -> BuildResult:
    """Compile the payload: load sections, run gates, (optionally) write output.

    Gate order is deliberate: section gates first (they catch a malformed
    contract cheaply), then output gates over the assembled document. Any
    finding raises GateViolation before any byte touches disk.
    """
    section_texts = load_section_texts(manifest)

    # Section-structure gates: per-section token assertions + DNS-first order.
    section_findings = gates.run_section_gates(manifest, section_texts)
    gates.require_clean(section_findings)

    document, digests = render_document(manifest, section_texts)

    # Output gates over the assembled document exactly as it will be written.
    output_findings = gates.run_output_gates(manifest, document, manifest.output_path)
    gates.require_clean(output_findings)

    output_path = manifest.output_file
    if write:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(document, encoding="utf-8")
        except OSError as exc:
            raise BuildError(f"cannot write {output_path}: {exc}") from exc
    return BuildResult(
        output_path=output_path,
        document=document,
        payload_sha256=sha256_bytes(document.encode("utf-8")),
        sections=digests,
    )


def regenerate_sections(manifest: Manifest) -> tuple[str, ...]:
    """Validate that every manifest section source exists (the generate stage).

    Generation here is the deterministic step: the doctrine source in
    sections/ is human-authored and checked in, so 'generate' verifies the
    contract's footing (all declared paths present, lint files present) and
    returns the section ids in build order. It writes nothing.
    """
    load_section_texts(manifest)  # raises BuildError on any missing file
    for lint_rel in (manifest.forbidden_patterns_path, manifest.banned_claims_path):
        if not (manifest.root / lint_rel).is_file():
            raise ManifestError(f"lint file not found: {manifest.root / lint_rel}")
    return manifest.section_ids
