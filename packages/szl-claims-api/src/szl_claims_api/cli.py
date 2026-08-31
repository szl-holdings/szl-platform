"""Argparse front door: `python -m szl_claims_api <subcommand>`.

Subcommands (each with --help):

    serve   [--claims-file P] [--host H] [--port N] [--refresh]
    seed    --out DIR
    print   [--claims-file P] [--json]

The CLI never fabricates a number: `print` renders exactly what the API
would serve, and `seed` writes the honest all-UNKNOWN initial state.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from szl_claims_api import __version__
from szl_claims_api.receipts import ReceiptMinter
from szl_claims_api.seed import seed_claims
from szl_claims_api.store import (
    ClaimStore,
    default_claims_file_path,
    refresh_from_estate,
)


def build_parser() -> argparse.ArgumentParser:
    """Top-level parser with serve/seed/print subcommands."""
    parser = argparse.ArgumentParser(
        prog="szl_claims_api",
        description="The live Covenant Proof Standard service: every public numeric "
        "claim SZL Holdings makes, receipted and recomputable.",
    )
    parser.add_argument(
        "--version", action="version", version=f"szl-claims-api {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the HTTP service (uvicorn)")
    serve.add_argument(
        "--claims-file",
        type=Path,
        default=None,
        help="claims file path (default: SZL_CLAIMS_FILE or artifacts/claims/claims.json)",
    )
    serve.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="bind port (default 8000)")
    serve.add_argument(
        "--refresh",
        action="store_true",
        help="attempt a one-shot szl-estate recomputation of the claims file before "
        "serving (optional boundary; degrades cleanly when szl-estate is absent)",
    )

    seed = sub.add_parser(
        "seed", help="write claims.json from the packaged seed registry (all UNKNOWN)"
    )
    seed.add_argument("--out", required=True, type=Path, help="output directory")

    printer = sub.add_parser(
        "print", help="print the claims view the API would serve (no server)"
    )
    printer.add_argument(
        "--claims-file",
        type=Path,
        default=None,
        help="claims file path (default: SZL_CLAIMS_FILE or artifacts/claims/claims.json)",
    )
    printer.add_argument("--json", action="store_true", help="print as JSON")

    return parser


def _cmd_serve(args: argparse.Namespace) -> int:
    """Serve with uvicorn, optionally refreshing the claims file first."""
    import uvicorn

    from szl_claims_api.app import create_app

    claims_file = args.claims_file or default_claims_file_path()
    if args.refresh:
        ok, note = refresh_from_estate(claims_file.parent)
        print(f"refresh: {note}")
        if not ok:
            # Degrade cleanly: serve whatever honest state exists (or
            # UNAVAILABLE + seeded UNKNOWNs when no file exists).
            print("refresh: continuing without recomputed numbers")
    store = ClaimStore(claims_file)
    print(f"store state: {store.state}" + (f" — {store.note}" if store.note else ""))
    app = create_app(claims_file)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _cmd_seed(args: argparse.Namespace) -> int:
    """Write the honest all-UNKNOWN claims file, then round-trip validate it."""
    path = seed_claims(args.out)
    store = ClaimStore(path)  # refuses to print success over an invalid file
    stats = store.stats()
    print(
        f"seeded {stats.total} claims to {path} "
        f"({stats.unknown} UNKNOWN, awaiting recomputation by szl-estate)"
    )
    return 0


def _cmd_print(args: argparse.Namespace) -> int:
    """Print the same claims view the API serves, for terminals and CI."""
    store = ClaimStore(args.claims_file or default_claims_file_path())
    minter = ReceiptMinter()
    claims = store.get_all()
    if args.json:
        print(
            json.dumps(
                {
                    "store_state": store.state,
                    "note": store.note,
                    "stats": store.stats().to_dict(),
                    "claims": [
                        {
                            "claim_id": c["claim_id"],
                            "claimed": c["expected"],
                            "actual": c["observed"],
                            "last_run": c["last_run"],
                            "verdict": c["verdict"],
                            "drift": c["verdict"] == "DRIFT",
                            "receipt_id": minter.receipt_for(c)["receipt_id"],
                        }
                        for c in claims
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    print(f"store state: {store.state}" + (f" — {store.note}" if store.note else ""))
    for claim in claims:
        receipt_id = minter.receipt_for(claim)["receipt_id"]
        actual = claim["observed"] if claim["observed"] is not None else "—"
        last_run = claim["last_run"] if claim["last_run"] is not None else "—"
        print(
            f"  {claim['claim_id']}: claimed {claim['expected']!r}, actual {actual}, "
            f"last_run {last_run}, verdict {claim['verdict']} "
            f"(receipt {receipt_id[:16]}…)"
        )
    stats = store.stats()
    print(
        f"totals: {stats.total} claims — {stats.passed} PASS, {stats.drift} DRIFT, "
        f"{stats.unknown} UNKNOWN"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to the requested subcommand."""
    args = build_parser().parse_args(argv)
    handlers = {"serve": _cmd_serve, "seed": _cmd_seed, "print": _cmd_print}
    return handlers[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
