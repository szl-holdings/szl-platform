"""Command line: ``python -m szl_adversarial run [--out DIR] [--json] [--sign-with KEY.pem]``.

Exit codes — deliberately distinct, so CI can tell "the claim held" apart
from "the claim broke" apart from "the harness couldn't run":

* **0** — every non-limitation attack was blocked; the report's verdict line
  is ``receipt chain resisted N/N non-limitation attacks``.
* **2** — at least one attack succeeded (or crashed the verifier); the
  report names exactly which attack won.
* **3** — usage/IO error; the harness itself could not complete (bad key
  path, unwritable output dir, …). No verdict is claimed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from .harness import HarnessResult, run_all
from .report import write_report

__all__ = ["main"]

EXIT_PASS = 0
EXIT_ATTACK_SUCCEEDED = 2
EXIT_USAGE = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m szl_adversarial",
        description=(
            "Attack the SZL receipt chain and publish the result either way. "
            "Exit 0: all non-limitation attacks blocked. Exit 2: an attack won "
            "(the report says exactly which one)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser(
        "run",
        help="execute the full attack battery and write ATTACK_REPORT.md",
    )
    run.add_argument(
        "--out",
        default="attack-out",
        help="output directory for report + self-receipt (default: ./attack-out)",
    )
    run.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="also write results.json into --out and print machine-readable JSON to stdout",
    )
    run.add_argument(
        "--sign-with",
        metavar="KEY.pem",
        default=None,
        help="Ed25519 private key used to sign the harness's self-receipt",
    )
    return parser


def _run(out: str, as_json: bool, sign_with: str | None, stdout: TextIO) -> int:
    out_dir = Path(out)
    if sign_with is not None and not Path(sign_with).is_file():
        print(f"error: --sign-with key not found: {sign_with}", file=sys.stderr)
        return EXIT_USAGE

    harness: HarnessResult = run_all()

    try:
        paths = write_report(harness, out_dir, sign_with=sign_with)
    except OSError as exc:
        print(f"error: cannot write report into {out_dir}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if as_json:
        results_path = out_dir / "results.json"
        results_path.write_text(
            json.dumps(harness.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(harness.to_dict(), sort_keys=True), file=stdout)

    print(harness.verdict_line(), file=stdout)
    for warning in harness.warnings:
        print(warning, file=stdout)
    print(f"report: {paths['report']}", file=stdout)
    print(f"self-receipt: {paths['receipt']}", file=stdout)

    return EXIT_PASS if harness.passed else EXIT_ATTACK_SUCCEEDED


def main(argv: list[str] | None = None, stdout: TextIO | None = None) -> int:
    """Entry point for both ``python -m szl_adversarial`` and the console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    out_stream = stdout if stdout is not None else sys.stdout
    if args.command == "run":
        return _run(args.out, args.as_json, args.sign_with, out_stream)
    parser.print_help(out_stream)
    return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
