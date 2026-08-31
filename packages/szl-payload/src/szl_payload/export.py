"""Export — the attestation-side artifacts of a build.

Produces under ``dist/export/``:

* ``export_manifest.unsigned.json`` — payload digest, per-section digests,
  extracted-file subjects, ``generated_by``, ``publication_eligible``, and
  an empty ``signatures`` array. Canonicalized with RFC 8785 before its
  digest is taken. It is named ``.unsigned.json`` because ``signatures == []``
  — honest naming (Phase 1, Defect 3); this package obeys its own doctrine.
* ``RECEIPT.md`` — the build receipt, and the ONLY export artifact that may
  carry a timestamp (``embed_build_time_in_body = false`` keeps the payload
  body itself timeless so the idempotency proof holds). The timestamp is the
  newest source-input mtime (the SOURCE_DATE_EPOCH reproducible-build
  convention), so identical inputs reproduce identical receipts and the
  byte-identical rebuild proof covers the export directory too.
* ``REPORT.md`` — the build/gate report.
* ``OPERATOR_PACKET.md`` — the top human-facing output: ten mandatory
  answers, every one UNKNOWN until evidence exists. UNKNOWN is never
  asserted and never promoted.
"""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import jinja2

from . import __version__, _jcs
from .builder import sha256_bytes
from .manifest import Manifest

if TYPE_CHECKING:
    from .builder import SectionDigest
    from .extract import ExtractedFile

EXPORT_MANIFEST_NAME = "export_manifest.unsigned.json"
GENERATED_BY = f"szl-payload {__version__}"

#: The safe-defaults block, verbatim. Every export report carries it so the
#: reader sees the run's mutation posture without opening the payload.
SAFE_DEFAULTS = (
    "AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false "
    "DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false "
    "HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false"
)

#: The ten mandatory operator-packet answers, in contract order.
OPERATOR_PACKET_QUESTIONS = (
    "What was verified",
    "What was fixed",
    "What is still failing",
    "What is blocked on credentials",
    "The exact DNS record diff",
    "The exact rollback records",
    "The exact next safe command",
    "Per-domain DNS/TLS/app pass state",
    "Whether any forbidden links remain",
    "V11 artifact state (verified / regressed / unknown)",
)

UNKNOWN = "UNKNOWN"

#: Section digest comments as emitted by builder.section_comment().
_SECTION_COMMENT_RE = re.compile(r"<!-- section:(?P<id>\S+) sha256:(?P<digest>[0-9a-f]{64}) -->")


class ExportError(Exception):
    """Export failure — unreadable payload, template failure, or I/O."""


@dataclasses.dataclass(frozen=True)
class ExportResult:
    """What a successful export wrote."""

    export_dir: Path
    export_manifest_path: Path
    export_manifest_sha256: str
    payload_sha256: str
    receipt_path: Path
    report_path: Path
    operator_packet_path: Path
    subject_count: int


def _load_templates(root: Path) -> jinja2.Environment:
    templates_dir = root / "templates"
    if not templates_dir.is_dir():
        raise ExportError(f"templates directory not found: {templates_dir}")
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=False,  # markdown output, not HTML
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _relpath(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _context_root(manifest: Manifest) -> dict:
    """Operator packet context: every answer UNKNOWN — asserted, never green."""
    return {
        "generated_by": GENERATED_BY,
        "safe_defaults": SAFE_DEFAULTS,
        "answers": [{"question": question, "status": UNKNOWN, "detail": UNKNOWN}
                    for question in OPERATOR_PACKET_QUESTIONS],
        "publication_eligible": manifest.publication_eligible,
    }


def export_manifest_object(
    payload_relpath: str,
    payload_sha256: str,
    section_digests: list[dict],
    subjects: list[dict],
    publication_eligible: bool,
) -> dict:
    """The export manifest as a plain JSON object (canonicalized at write time).

    Subjects follow the contract shape exactly: ``[{name, sha256}]``.
    """
    return {
        "generated_by": GENERATED_BY,
        "payload": {"path": payload_relpath, "sha256": payload_sha256},
        "sections": section_digests,
        "subjects": subjects,
        "publication_eligible": publication_eligible,
        "signatures": [],  # empty → the file must be named .unsigned.json
        "jcs_backend": _jcs.JCS_BACKEND,
    }


def source_epoch_iso(manifest: Manifest) -> str:
    """Deterministic 'build time': newest source-input mtime, UTC ISO-8601.

    Reproducible-build convention (SOURCE_DATE_EPOCH): the receipt timestamp
    is a function of THE INPUTS, not the wall clock, so rebuilding unchanged
    inputs reproduces a byte-identical export directory. Inputs are the
    manifest, every section, the lint files, and every template.
    """
    candidates = [
        manifest.root / "manifest.toml",
        *(manifest.root / section.path for section in manifest.sections),
        manifest.root / manifest.forbidden_patterns_path,
        manifest.root / manifest.banned_claims_path,
    ]
    templates_dir = manifest.root / "templates"
    if templates_dir.is_dir():
        candidates.extend(sorted(templates_dir.glob("*.j2")))
    newest = max(
        (path.stat().st_mtime for path in candidates if path.is_file()),
        default=0.0,
    )
    return datetime.fromtimestamp(newest, UTC).isoformat(timespec="seconds")


def run_export(
    manifest: Manifest,
    payload_sha256: str,
    section_digests: tuple[SectionDigest, ...],
    extracted_files: list[ExtractedFile],
) -> ExportResult:
    """Write the export manifest + rendered report/packet/receipt into dist/export/."""
    export_dir = manifest.export_path
    try:
        export_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportError(f"cannot create {export_dir}: {exc}") from exc

    section_dicts = [
        {"id": item.id, "path": item.path, "sha256": item.sha256} for item in section_digests
    ]
    # Manifest subjects are the contract shape [{name, sha256}]; the report
    # table additionally shows path/mode for humans.
    subjects = [{"name": item.relpath, "sha256": item.sha256} for item in extracted_files]
    subject_rows = [
        {"path": item.relpath, "mode": format(item.mode, "03o"), "sha256": item.sha256}
        for item in extracted_files
    ]
    obj = export_manifest_object(
        payload_relpath=manifest.output_path,
        payload_sha256=payload_sha256,
        section_digests=section_dicts,
        subjects=subjects,
        publication_eligible=manifest.publication_eligible,
    )
    # Canonicalize with real RFC 8785 (never json.dumps(sort_keys=True)) so
    # the manifest digest is reproducible by any conforming implementation.
    canonical_bytes = _jcs.canonicalize(obj)
    manifest_sha256 = sha256_bytes(canonical_bytes)
    manifest_path = export_dir / EXPORT_MANIFEST_NAME
    try:
        # Pretty-printed for humans, but the DIGEST is over canonical bytes.
        manifest_path.write_text(
            json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise ExportError(f"cannot write {manifest_path}: {exc}") from exc

    environment = _load_templates(manifest.root)
    generated_at = source_epoch_iso(manifest)
    common = _context_root(manifest)
    common.update(
        {
            "generated_at": generated_at,  # receipt/report only — never the payload body
            "payload": {"path": manifest.output_path, "sha256": payload_sha256},
            "sections": section_dicts,
            "subjects": subjects,
            "subject_rows": subject_rows,
            "export_manifest": {
                "path": _relpath(manifest_path, manifest.root),
                "sha256": manifest_sha256,
                "signatures_empty": True,
                "unsigned_name": True,
            },
            "jcs_backend": _jcs.JCS_BACKEND,
            "gates": {
                "require_dns_first": manifest.require_dns_first,
                "forbidden_patterns": manifest.forbidden_patterns_path,
                "banned_claims": manifest.banned_claims_path,
            },
        }
    )

    outputs = {
        "RECEIPT.j2": export_dir / "RECEIPT.md",
        "REPORT.j2": export_dir / "REPORT.md",
        "OPERATOR_PACKET.j2": export_dir / "OPERATOR_PACKET.md",
    }
    rendered: dict[str, Path] = {}
    for template_name, target in outputs.items():
        try:
            text = environment.get_template(template_name).render(**common)
            target.write_text(text, encoding="utf-8")
        except (jinja2.TemplateError, OSError) as exc:
            raise ExportError(f"cannot render {template_name} → {target}: {exc}") from exc
        rendered[template_name] = target

    return ExportResult(
        export_dir=export_dir,
        export_manifest_path=manifest_path,
        export_manifest_sha256=manifest_sha256,
        payload_sha256=payload_sha256,
        receipt_path=rendered["RECEIPT.j2"],
        report_path=rendered["REPORT.j2"],
        operator_packet_path=rendered["OPERATOR_PACKET.j2"],
        subject_count=len(extracted_files),
    )
