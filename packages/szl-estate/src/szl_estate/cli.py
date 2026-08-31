"""Argparse front door: `python -m szl_estate <subcommand>` and `szl-estate`.

Subcommands (each with --help):

    enumerate      --org --out [--offline] [--fixture P] [--json]
    audit          --org --out [--offline] [--fixture P] [--json]
    doctor         [--json]                     (exit 1 if any FAIL)
    verify-claims  --out [--json]

Behavior lives in the per-command modules; this file only wires argv to them.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from szl_estate import __version__, audit, doctor, enumerate, verify_claims


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with all four subcommands."""
    parser = argparse.ArgumentParser(
        prog="szl_estate",
        description="SZL estate control plane: enumerate, audit, doctor, verify-claims.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"szl-estate {__version__}",
        help="print version and exit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--org", required=True, help="GitHub organization")
    common.add_argument("--out", required=True, help="output directory")
    common.add_argument(
        "--offline", action="store_true", help="no network; replay fixtures / mark probes UNKNOWN"
    )
    common.add_argument("--fixture", default=None, help="explicit offline fixture path")
    common.add_argument("--json", action="store_true", help="emit JSON")

    sub.add_parser("enumerate", parents=[common], help=enumerate.main.__doc__ or "enumerate")
    sub.add_parser("audit", parents=[common], help=audit.main.__doc__ or "audit")

    doctor_parser = sub.add_parser("doctor", help=doctor.main.__doc__ or "doctor")
    doctor_parser.add_argument("--json", action="store_true", help="emit JSON")

    claims_parser = sub.add_parser(
        "verify-claims", help=verify_claims.main.__doc__ or "verify claims"
    )
    claims_parser.add_argument("--out", required=True, help="output directory")
    claims_parser.add_argument("--json", action="store_true", help="emit JSON")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to the requested subcommand and return its exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    forwarded: list[str] = []
    # Re-forward the parsed namespace to each module's own argparse main, so
    # every subcommand keeps exactly one source of truth for its flags.
    if args.command == "doctor":
        if args.json:
            forwarded.append("--json")
        return doctor.main(forwarded)
    if args.command == "verify-claims":
        forwarded += ["--out", args.out]
        if args.json:
            forwarded.append("--json")
        return verify_claims.main(forwarded)
    # enumerate / audit share flags.
    forwarded += ["--org", args.org, "--out", args.out]
    if args.offline:
        forwarded.append("--offline")
    if args.fixture:
        forwarded += ["--fixture", args.fixture]
    if args.json:
        forwarded.append("--json")
    if args.command == "enumerate":
        return enumerate.main(forwarded)
    if args.command == "audit":
        return audit.main(forwarded)
    parser.error(f"unknown command {args.command}")  # unreachable; argparse guards
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
