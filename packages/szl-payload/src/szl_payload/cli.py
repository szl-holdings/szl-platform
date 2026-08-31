"""Command line: python -m szl_payload [generate|compile|extract|export|verify|all]

Exit codes (doctrine):

* 0 — everything requested succeeded and every gate passed.
* 2 — a gate failed (compile/verify findings are printed with line numbers).
* 3 — operational error (missing files, malformed manifest, I/O, templates).

Every command supports --json (machine-readable result on stdout) and every
command is safe to run in Pass 1: none of them touch the network or mutate
anything outside dist/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__, builder, export, extract, gates
from .builder import BuildError, sha256_bytes
from .export import ExportError
from .extract import ExtractError
from .manifest import Manifest, ManifestError, load_manifest

EXIT_OK = 0
EXIT_GATE_FAILED = 2
EXIT_OPERATIONAL_ERROR = 3

COMMANDS = ("generate", "compile", "extract", "export", "verify", "all")


# ---------------------------------------------------------------------------
# stage runners — each returns a JSON-serializable result dict
# ---------------------------------------------------------------------------


def run_generate(manifest: Manifest) -> dict:
    """generate: validate the manifest contract footing (sections + lint files)."""
    section_ids = builder.regenerate_sections(manifest)
    return {
        "stage": "generate",
        "sections": list(section_ids),
        "section_count": len(section_ids),
    }


def run_compile(manifest: Manifest) -> dict:
    """compile: assemble the payload and enforce every gate (fail = exit 2)."""
    result = builder.compile_payload(manifest, write=True)
    return {
        "stage": "compile",
        "output": str(result.output_path),
        "payload_sha256": result.payload_sha256,
        "section_count": len(result.sections),
    }


def run_extract(manifest: Manifest) -> dict:
    """extract: write dist/extracted/ scaffolds from the built payload."""
    written = extract.extract_payload(manifest.output_file, manifest.root / "dist")
    return {
        "stage": "extract",
        "dest": str(manifest.root / "dist" / extract.EXTRACT_DIR_NAME),
        "files": [
            {"path": item.relpath, "mode": format(item.mode, "03o"), "sha256": item.sha256}
            for item in written
        ],
        "file_count": len(written),
    }


def run_export(manifest: Manifest) -> dict:
    """export: compile → extract → export manifest + receipt/report/packet."""
    compiled = builder.compile_payload(manifest, write=True)
    written = extract.extract_document(
        compiled.document, manifest.root / "dist" / extract.EXTRACT_DIR_NAME
    )
    result = export.run_export(manifest, compiled.payload_sha256, compiled.sections, written)
    return {
        "stage": "export",
        "export_manifest": str(result.export_manifest_path),
        "export_manifest_sha256": result.export_manifest_sha256,
        "payload_sha256": result.payload_sha256,
        "receipt": str(result.receipt_path),
        "report": str(result.report_path),
        "operator_packet": str(result.operator_packet_path),
        "subject_count": result.subject_count,
    }


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

_SECTION_COMMENT_RE = re.compile(r"<!-- section:(?P<id>\S+) sha256:(?P<digest>[0-9a-f]{64}) -->")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def run_verify(manifest: Manifest) -> dict:
    """Re-verify a built dist/: digests, gates, export honesty, forbidden scan.

    Raises GateViolation (exit 2) on any failed check; operational problems
    (missing payload etc.) raise one of the *Error types (exit 3).
    """
    findings: list[gates.Finding] = []
    checks: dict[str, object] = {}

    # -- 1. The payload must exist ------------------------------------------------
    payload_path = manifest.output_file
    if not payload_path.is_file():
        raise BuildError(f"payload not found: {payload_path} — run compile first")
    document = payload_path.read_text(encoding="utf-8")
    payload_label = manifest.output_path

    # -- 2. Re-digest sections and compare against the embedded comments ---------
    section_texts = builder.load_section_texts(manifest)
    embedded: dict[str, tuple[str, int]] = {}  # id -> (digest, char offset)
    for match in _SECTION_COMMENT_RE.finditer(document):
        embedded[match.group("id")] = (match.group("digest"), match.start())
    digest_mismatches = []
    for section in manifest.sections:
        expected = sha256_bytes(section_texts[section.id][1].encode("utf-8"))
        got = embedded.get(section.id)
        if got is None:
            digest_mismatches.append(f"{section.id}: digest comment missing")
            findings.append(
                gates.Finding(
                    "verify_digest",
                    payload_label,
                    f"section {section.id!r} has no digest comment in the built document",
                )
            )
        elif got[0] != expected:
            digest_mismatches.append(f"{section.id}: {got[0][:12]}… != {expected[:12]}…")
            findings.append(
                gates.Finding(
                    "verify_digest",
                    f"{payload_label}:{document.count(chr(10), 0, got[1]) + 1}",
                    f"section {section.id!r} digest mismatch — sections/ changed since build",
                )
            )
    checks["section_digests"] = {
        "sections": len(manifest.sections),
        "mismatches": digest_mismatches,
        "passed": not digest_mismatches,
    }

    # -- 3. Ordering: embedded comments appear in manifest order ------------------
    positions = [embedded[s.id][1] for s in manifest.sections if s.id in embedded]
    ordering_ok = len(positions) == len(manifest.sections) and positions == sorted(positions)
    if not ordering_ok:
        findings.append(
            gates.Finding(
                "verify_order", payload_label, "section digest comments are out of manifest order"
            )
        )
    checks["section_order"] = {"passed": ordering_ok}

    # -- 4. Re-run every gate over the built file ---------------------------------
    gate_findings = gates.run_section_gates(manifest, section_texts)
    gate_findings += gates.run_output_gates(manifest, document, payload_label)
    findings += gate_findings
    checks["gates"] = {
        "finding_count": len(gate_findings),
        "findings": [f.render() for f in gate_findings],
        "passed": not gate_findings,
    }

    # -- 5. Export manifest honesty ----------------------------------------------
    export_dir = manifest.export_path
    manifest_path = export_dir / export.EXPORT_MANIFEST_NAME
    unsigned_ok = True
    signatures_ok = True
    publication_ok = True
    payload_match_ok = True
    details: dict[str, object] = {}
    # Honest naming: the manifest must carry the .unsigned.json name, and no
    # "signed-looking" sibling export_manifest.json may exist beside it.
    bare_sibling = export_dir / "export_manifest.json"
    if bare_sibling.exists():
        unsigned_ok = False
        findings.append(
            gates.Finding(
                "verify_export",
                _rel(bare_sibling, manifest.root),
                "bare export_manifest.json exists beside the .unsigned.json — dishonest naming",
            )
        )
    if not manifest_path.is_file():
        findings.append(
            gates.Finding(
                "verify_export",
                _rel(manifest_path, manifest.root),
                "export manifest missing — run export first",
            )
        )
        unsigned_ok = signatures_ok = publication_ok = payload_match_ok = False
    else:
        try:
            obj = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BuildError(f"export manifest is not valid JSON: {manifest_path}: {exc}") from exc
        signatures = obj.get("signatures")
        if signatures != []:
            signatures_ok = False
            findings.append(
                gates.Finding(
                    "verify_export",
                    _rel(manifest_path, manifest.root),
                    f"signatures must be [] in {export.EXPORT_MANIFEST_NAME}, got {signatures!r}",
                )
            )
        if obj.get("publication_eligible") is not False:
            publication_ok = False
            findings.append(
                gates.Finding(
                    "verify_export",
                    _rel(manifest_path, manifest.root),
                    "publication_eligible must be false in the default build — "
                    "it is computed elsewhere, never asserted",
                )
            )
        recorded = (obj.get("payload") or {}).get("sha256")
        actual = sha256_bytes(document.encode("utf-8"))
        details = {
            "recorded_payload_sha256": recorded,
            "actual_payload_sha256": actual,
            "generated_by": obj.get("generated_by"),
            "subject_count": len(obj.get("subjects", [])),
        }
        if recorded != actual:
            payload_match_ok = False
            findings.append(
                gates.Finding(
                    "verify_export",
                    _rel(manifest_path, manifest.root),
                    "export manifest payload digest does not match the built document",
                )
            )
    checks["export_manifest"] = {
        "name": export.EXPORT_MANIFEST_NAME,
        "unsigned_name_ok": unsigned_ok,
        "signatures_empty": signatures_ok,
        "publication_eligible_false": publication_ok,
        "payload_digest_match": payload_match_ok,
        "passed": unsigned_ok and signatures_ok and publication_ok and payload_match_ok,
        **details,
    }

    # -- 6. Forbidden-domain grep over all of dist/ --------------------------------
    dist_dir = manifest.root / "dist"
    domain_hits = []
    if dist_dir.is_dir():
        for path in sorted(dist_dir.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable derived file — nothing to match
            for match in gates.FORBIDDEN_DOMAIN_RE.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                domain_hits.append(f"{_rel(path, manifest.root)}:{line}")
    if domain_hits:
        findings.append(
            gates.Finding(
                "verify_forbidden_domain",
                "dist/",
                f"forbidden domain found at {', '.join(domain_hits)}",
            )
        )
    checks["forbidden_domain_scan"] = {"hits": domain_hits, "passed": not domain_hits}

    passed = not findings
    return {
        "stage": "verify",
        "passed": passed,
        "checks": checks,
        "finding_count": len(findings),
        "findings": [f.render() for f in findings],
    }


def run_all(manifest: Manifest) -> dict:
    """all: generate → compile → extract → export."""
    return {
        "stage": "all",
        "generate": run_generate(manifest),
        "compile": run_compile(manifest),
        "extract": run_extract(manifest),
        "export": run_export(manifest),
    }


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def _print_result(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    stage = result.get("stage", "?")
    print(f"stage: {stage}")
    for key, value in result.items():
        if key == "stage":
            continue
        if key == "findings":
            for finding in value:
                print(f"  {finding}")
        elif isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, (dict, list)):
                    print(f"  {sub_key}: {json.dumps(sub_value, sort_keys=True)}")
                else:
                    print(f"  {sub_key}: {sub_value}")
        elif isinstance(value, list):
            print(f"{key}: {json.dumps(value)}")
        else:
            print(f"{key}: {value}")
    if stage in {"compile", "export", "all"}:
        print("PASS")
    if stage == "verify":
        print("PASS: verify clean" if result["passed"] else "FAIL: verify found gate violations")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="szl_payload",
        description=(
            "Deterministic SZL master-payload builder (v" + __version__ + "). "
            "sections/ is source; dist/ is derived; UNKNOWN is never PASS."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=COMMANDS,
        help="stage to run (default: all)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="package root containing manifest.toml (default: cwd)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        manifest = load_manifest(root)
        command = args.command
        if command == "verify":
            result = run_verify(manifest)
            _print_result(result, args.json)
            return EXIT_OK if result["passed"] else EXIT_GATE_FAILED
        result = {
            "generate": run_generate,
            "compile": run_compile,
            "extract": run_extract,
            "export": run_export,
            "all": run_all,
        }[command](manifest)
        _print_result(result, args.json)
        return EXIT_OK
    except gates.GateViolation as violation:
        # Gate failure: report every finding (with line numbers) and exit 2.
        if args.json:
            print(
                json.dumps(
                    {
                        "error": "gate_violation",
                        "finding_count": len(violation.findings),
                        "findings": [f.render() for f in violation.findings],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print("GATE FAILURE:", file=sys.stderr)
            for finding in violation.findings:
                print(f"  {finding.render()}", file=sys.stderr)
        return EXIT_GATE_FAILED
    except (ManifestError, BuildError, ExtractError, ExportError) as exc:
        # Operational error: exit 3.
        if args.json:
            print(json.dumps({"error": "operational", "detail": str(exc)}, indent=2))
        else:
            print(f"operational error: {exc}", file=sys.stderr)
        return EXIT_OPERATIONAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
