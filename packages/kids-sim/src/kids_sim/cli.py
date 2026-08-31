"""KIDS v0.1 command-line interface.

    python -m kids_sim.cli run-program program.json --json
    python -m kids_sim.cli verify-receipts receipts.json
    python -m kids_sim.cli perf program.json

Every subcommand supports --help; machine-readable output via --json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import perf
from .engine import Engine
from .isa import SchemaError, program_from_dicts
from .receipts import ChainVerificationError, verify_chain


def _load_program(path: Path):
    doc = json.loads(path.read_text())
    if isinstance(doc, dict):
        if doc.get("domainSeparation") != "SZL-KIDS-RECEIPT-V1":
            raise SchemaError("program document missing/mismatched domainSeparation const")
        doc = doc["program"]
    return program_from_dicts(doc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kids_sim", description="KIDS v0.1 golden simulator CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("run-program", help="execute a KIDS program JSON")
    rp.add_argument("program", type=Path)
    rp.add_argument("--json", action="store_true")

    vp = sub.add_parser("verify-receipts", help="verify a receipt chain JSON")
    vp.add_argument("receipts", type=Path)
    vp.add_argument("--json", action="store_true")

    pp = sub.add_parser("perf", help="cycle ESTIMATE report for a program")
    pp.add_argument("program", type=Path)
    pp.add_argument("--json", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "run-program":
        prog = _load_program(args.program)
        eng = Engine()
        eng.run(prog)
        out = {
            "events": eng.events,
            "receipt_root": eng.receipts.root.hex(),
            "cycles_estimate": {"value": eng.total_cycles, "label": "ESTIMATE"},
            "wall_clock": perf.measured_wall_clock(),
        }
        print(json.dumps(out, indent=2) if args.json else
              f"executed {len(eng.events)} commands, receipt root {eng.receipts.root.hex()[:16]}…, "
              f"cycles {eng.total_cycles} (ESTIMATE), wall clock {out['wall_clock']}")
        return 0

    if args.cmd == "verify-receipts":
        doc = json.loads(args.receipts.read_text())
        try:
            ok = verify_chain(doc["receipts"], doc.get("events"))
        except ChainVerificationError as e:
            print(json.dumps({"valid": False, "reason": str(e)}) if args.json else f"INVALID: {e}")
            return 1
        print(json.dumps({"valid": ok}) if args.json else "VALID")
        return 0

    if args.cmd == "perf":
        prog = _load_program(args.program)
        ests = [perf.estimate_cycles(c).to_dict() for c in prog]
        out = {"estimates": ests, "total_cycles": sum(e["cycles"] for e in ests),
               "label": "ESTIMATE", "wall_clock": perf.measured_wall_clock()}
        print(json.dumps(out, indent=2) if args.json else
              "\n".join(f"{e['op']:20s} {e['cycles']:>10d} cycles ({e['label']})" for e in ests)
              + f"\ntotal {out['total_cycles']} cycles (ESTIMATE); wall clock {out['wall_clock']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
