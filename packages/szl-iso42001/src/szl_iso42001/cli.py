"""Command-line interface for szl-iso42001.

Two subcommands:
  list   — print the full control corpus grouped by instrument and domain.
  check  — run a readiness assessment from an answers YAML file.

Honesty-by-default behaviors baked into the CLI:
  * `check` with a MISSING answers file does not fail as an error — it writes
    a template with every control set to 'unknown' and exits 2, telling the
    user to fill it in. Unknown-by-default is the honest starting position:
    this tool never assumes a control passes because nobody answered it.
  * A template (all-unknown) run produces NOT_READY with every control listed
    as an evidence gap. That is a feature, not a bug.
  * Exit codes: 0 = ran fine (any band — NOT_READY is a valid outcome, not an
    error), 1 = invalid input (bad YAML, unknown control ids, bad answers),
    2 = template generated, go fill it in.

The CLI layer does no scoring itself; it only wires files to the pure
functions in score.py / report.py / receipt.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .controls import (
    ANSWER_KINDS,
    DISCLAIMER,
    Control,
    instruments,
    load_controls,
)
from .receipt import emit_receipt
from .report import render_report
from .score import score_answers

# Exit codes — stable, documented, scriptable.
EXIT_OK = 0
EXIT_INVALID_INPUT = 1
EXIT_TEMPLATE_GENERATED = 2

TEMPLATE_NAME = "answers.yaml"
REPORT_NAME = "readiness-report.md"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser. Kept separate from main() so tests can call
    `--help` and `--version` through argparse's own exit paths."""
    parser = argparse.ArgumentParser(
        prog="szl_iso42001",
        description=(
            "Free, offline ISO/IEC 42001 + EU AI Act Article 50 readiness "
            "self-assessment. Never says 'certified' — bands are NOT_READY, "
            "PARTIAL, READY_FOR_STAGE1_AUDIT. Unanswered controls are gaps, "
            "never assumed passes."
        ),
        epilog=DISCLAIMER,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser(
        "list", help="print all controls grouped by instrument and domain"
    )
    p_list.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )

    p_check = sub.add_parser(
        "check", help="run a readiness assessment from an answers YAML file"
    )
    p_check.add_argument(
        "--answers",
        required=True,
        help=(
            "path to answers YAML (control id -> yes|partial|no|unknown). "
            "If missing, a template is generated and the exit code is 2."
        ),
    )
    p_check.add_argument(
        "--out",
        default=".",
        help="directory for readiness-report.md and the receipt (default: .)",
    )
    p_check.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON summary"
    )
    return parser


# ---------------------------------------------------------------------------
# `list`
# ---------------------------------------------------------------------------

def _cmd_list(as_json: bool) -> int:
    """Print the corpus, grouped by instrument then domain."""
    by_instrument = instruments()
    if as_json:
        payload = {
            "disclaimer": DISCLAIMER,
            "instruments": {
                name: [
                    {
                        "id": c.id,
                        "title": c.title,
                        "question": c.question,
                        "evidence_hint": c.evidence_hint,
                        "domain": c.domain,
                        "weight": c.weight,
                    }
                    for c in controls
                ]
                for name, controls in by_instrument.items()
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK

    print(f"DISCLAIMER: {DISCLAIMER}\n")
    for name, controls in by_instrument.items():
        heading = (
            "ISO/IEC 42001 — AI management system readiness"
            if name == "ISO42001"
            else "EU AI Act Article 50 — transparency readiness"
        )
        print(f"== {heading} ({len(controls)} controls) ==")
        current_domain = None
        for c in controls:
            if c.domain != current_domain:
                current_domain = c.domain
                print(f"\n  [{current_domain}]")
            print(f"    {c.id} (w{c.weight})  {c.title}")
        print()
    return EXIT_OK


# ---------------------------------------------------------------------------
# `check`
# ---------------------------------------------------------------------------

def _write_template(path: Path, controls: list[Control]) -> None:
    """Write a starter answers.yaml with every control set to 'unknown'.

    The template is hand-rendered (not yaml.dump) so each entry carries the
    control's title and question as comments — the template doubles as the
    interview script for whoever fills it in. Answer values are quoted so YAML
    does not turn `yes`/`no` into booleans.
    """
    lines = [
        "# szl-iso42001 answers file.",
        "# Answer each control with one of: " + ", ".join(ANSWER_KINDS),
        "#   yes     — fully implemented, evidence exists",
        "#   partial — partly implemented",
        "#   no      — not implemented (a gap to FIX)",
        "#   unknown — not assessed yet (an EVIDENCE GAP: go find out)",
        f"# {DISCLAIMER}",
        "",
    ]
    current_domain = None
    for c in controls:
        if c.domain != current_domain:
            current_domain = c.domain
            lines.append(f"# --- {c.domain} ---")
        lines.append(f"# {c.title} (weight {c.weight})")
        lines.append(f"# Q: {c.question}")
        lines.append(f'{c.id}: "unknown"')
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _load_answers(path: Path) -> dict[str, Any]:
    """Read and shape-check an answers YAML file.

    Returns the raw mapping; answer normalization and unknown-id rejection
    happen in score.score_answers (single source of truth).
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping of control id -> answer")
    return data


def _cmd_check(answers_path: str, out_dir: str, as_json: bool) -> int:
    """Run an assessment end-to-end and emit report + receipt."""
    controls = load_controls()
    path = Path(answers_path)

    # --- Missing answers file: the honest-start feature --------------------
    if not path.exists():
        _write_template(path, controls)
        message = (
            f"No answers file found. Wrote a template to {path} with every "
            f"control set to 'unknown' — fill it in and re-run:\n"
            f"  python -m szl_iso42001 check --answers {path} --out {out_dir}\n"
            "Note: an all-unknown run scores NOT_READY. That is the honest "
            "starting position, not a bug."
        )
        if as_json:
            print(
                json.dumps(
                    {
                        "event": "template_generated",
                        "template": str(path),
                        "control_count": len(controls),
                        "exit_code": EXIT_TEMPLATE_GENERATED,
                        "disclaimer": DISCLAIMER,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(message)
        return EXIT_TEMPLATE_GENERATED

    # --- Load + score --------------------------------------------------------
    try:
        answers = _load_answers(path)
        result = score_answers(answers, controls)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    report_md = render_report(result)

    # --- Emit artifacts ------------------------------------------------------
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / REPORT_NAME
    report_path.write_text(report_md, encoding="utf-8")

    receipt_info = emit_receipt(
        report_md,
        answers,
        out,
        band=result.band,
        counts=result.counts,
        control_count=result.control_count,
        tool_version=__version__,
    )

    # --- Output ----------------------------------------------------------------
    if as_json:
        print(
            json.dumps(
                {
                    "band": result.band,
                    "percentage": round(result.percentage, 4),
                    "earned": result.earned,
                    "possible": result.possible,
                    "answer_counts": result.counts,
                    "gap_count": len(result.gaps),
                    "no_fix_count": len(result.no_fix_gaps),
                    "evidence_gap_count": len(result.evidence_gaps),
                    "gaps": [
                        {
                            "control_id": g.control_id,
                            "kind": g.kind,
                            "weight": g.weight,
                            "domain": g.domain,
                            "title": g.title,
                        }
                        for g in result.gaps
                    ],
                    "report": str(report_path),
                    "receipt": receipt_info,
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"Band: {result.band} ({result.percentage:.1f}% weighted readiness)")
        print(f"Answers: {result.counts}")
        print(
            f"Gaps: {len(result.gaps)} "
            f"({len(result.no_fix_gaps)} to fix, "
            f"{len(result.evidence_gaps)} evidence gaps)"
        )
        print(f"Report:  {report_path}")
        print(f"Receipt: {receipt_info['path']} "
              f"({'signed' if receipt_info['signed'] else 'unsigned'})")
        print(f"\n{DISCLAIMER}")

    # Any band — including NOT_READY — is a successful run. Honesty means a bad
    # result is still a good exit code.
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m szl_iso42001` and the console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        return _cmd_list(args.json)
    if args.command == "check":
        return _cmd_check(args.answers, args.out, args.json)
    parser.error(f"unknown command {args.command!r}")  # pragma: no cover
    return EXIT_INVALID_INPUT  # pragma: no cover — parser.error exits first


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
