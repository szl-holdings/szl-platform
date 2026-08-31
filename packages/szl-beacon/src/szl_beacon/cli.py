"""Command-line interface: ``python -m szl_beacon ...``.

Commands::

    demo                      one complete Reality Transaction, end to end
    verify <logdir>           verify an event-log hash chain
    fleet validate <yaml>     validate a fleet configuration
    rc1-test                  run the RC1-01..04 acceptance fixtures (SIMULATION)
    sync <dir_a> <dir_b> <out>  offline-first peer sync of two logs

Every command accepts ``--json`` for machine-readable output. The demo writes
its verifiable chain to a temp directory and prints the path.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import __version__, rc1_sim
from . import fleet as fleet_mod
from . import log as eventlog
from . import sync as sync_mod
from .labels import Label
from .protocol import RealityTransaction, State
from .witness import WitnessClass, witness_event_payload

__all__ = ["main", "run_demo"]


def _print(data: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))


# ---------------------------------------------------------------------- demo


def run_demo(logdir: Path | None = None) -> dict[str, Any]:
    """Run one complete Reality Transaction and return a transcript.

    help request -> offer -> authorization -> action -> two distinct
    witnesses -> outcome verified -> receipt. Every transition is a separate
    event on the chain; the chain is verified before the demo returns.
    """

    own_tempdir = logdir is None
    if logdir is None:
        logdir = Path(tempfile.mkdtemp(prefix="szl-beacon-demo-"))
    logdir = Path(logdir)

    operator = {"kind": "human", "id": "operator-demo-01"}
    resident = {"kind": "human", "id": "resident-demo-42"}
    helper = {"kind": "human", "id": "helper-demo-07"}
    machine = {"kind": "machine", "id": "a11oy-revA-demo"}

    tx = RealityTransaction(logdir, node_id="beacon-demo-00")
    steps: list[dict[str, Any]] = []

    def record(event: dict) -> None:
        steps.append(
            {
                "seq": event["seq"],
                "transition": f"{event['state_from']} -> {event['state_to']}",
                "event_id": event["event_id"],
                "label": event["label"],
            }
        )

    # 1. INTENT — a resident asks for help (Proof of Intent).
    record(
        tx.open_intent(
            actor=resident,
            summary="Resident requests help: insulin refrigeration lost after outage",
            label=Label.COMMUNITY_REPORT,
            request={"proposal_type": "matching_proposal"},
        )
    )
    # 2. EVIDENCE — grid outage corroboration attached.
    evidence_ref = "ev:" + tx.transaction_id
    record(
        tx.advance(
            State.EVIDENCE,
            actor=resident,
            payload={"type": "EVIDENCE", "note": "outage report + photo of meter"},
            evidence_refs=[str(evidence_ref)],
            label=Label.COMMUNITY_REPORT,
        )
    )
    # 3. PROPOSAL — machine offers a matching proposal (hard-typed as such).
    record(
        tx.advance(
            State.PROPOSAL,
            actor=machine,
            payload={
                "type": "PROPOSAL",
                "proposal_type": "matching_proposal",
                "summary": "3 offers of refrigerated storage within 1.2 km",
            },
            label=Label.MACHINE_INFERENCE,
        )
    )
    # 4. SIMULATION — pre-action assessment.
    record(
        tx.advance(
            State.SIMULATION,
            actor=machine,
            payload={
                "type": "SIMULATION",
                "assessment": "handoff feasible under NOTIFY action class",
            },
            label=Label.MACHINE_INFERENCE,
        )
    )
    # 5. POLICY — Rev A scope check: matching proposal is permitted.
    record(
        tx.advance(
            State.POLICY,
            actor=operator,
            payload={
                "type": "POLICY",
                "decision": "ALLOWED",
                "scope": "Rev A matching proposal",
            },
            label=Label.AUTHORIZED_OPERATOR,
        )
    )
    # 6. CONSENT — operator authorizes the NOTIFY action.
    record(
        tx.advance(
            State.CONSENT,
            actor=operator,
            payload={"action_class": "NOTIFY"},
            label=Label.AUTHORIZED_OPERATOR,
        )
    )
    # 7. ACTION — the offer is delivered (Proof of Action: handoff receipt).
    record(
        tx.advance(
            State.ACTION,
            actor=helper,
            payload={"type": "ACTION", "action": "offer delivered to resident"},
            label=Label.VERIFIED_SOURCE,
        )
    )
    # 8. WITNESS — two DISTINCT classes (Proof of Outcome).
    record(
        tx.advance(
            State.WITNESS,
            actor={"kind": "sensor", "id": "temp-sensor-2231"},
            payload=witness_event_payload(
                WitnessClass.INDEPENDENT_SENSOR,
                "ev:sensor-2231-reading",
                observer_id="temp-sensor-2231",
                observation="insulin at 4.1 C in helper's fridge (independent)",
            ),
            label=Label.VERIFIED_SOURCE,
        )
    )
    record(
        tx.advance(
            State.WITNESS,
            actor=resident,
            payload=witness_event_payload(
                WitnessClass.RECIPIENT_CONFIRMATION,
                "ev:resident-confirmation",
                observer_id="resident-demo-42",
                observation="resident confirms insulin received and cold",
            ),
            label=Label.COMMUNITY_REPORT,
        )
    )
    # 9. OUTCOME — diversity gate passes, outcome VERIFIED (not assumed).
    record(
        tx.advance(
            State.OUTCOME,
            actor=operator,
            payload={"type": "OUTCOME", "summary": "insulin safely stored"},
        )
    )
    # 10. RECONCILIATION — nothing to reconcile; the record shows the check.
    record(
        tx.advance(
            State.RECONCILIATION,
            actor=operator,
            payload={"type": "RECONCILIATION", "open_debt": []},
            label=Label.AUTHORIZED_OPERATOR,
        )
    )
    # 11. RECEIPT — close the transaction.
    record(tx.advance(State.RECEIPT, actor=operator, payload={}))

    chain = eventlog.verify(logdir)
    receipt_event = eventlog.read_events(logdir)[-1]
    return {
        "logdir": str(logdir),
        "own_tempdir": own_tempdir,
        "transaction_id": tx.transaction_id,
        "transitions": steps,
        "transition_count": len(steps),
        "chain_ok": chain.ok,
        "receipt": receipt_event["payload"].get("receipt"),
        "receipt_event_id": receipt_event["event_id"],
    }


def _cmd_demo(args: argparse.Namespace) -> int:
    result = run_demo()
    if args.json:
        _print(result, as_json=True)
    else:
        print(f"SZL Beacon REALITY PROTOCOL demo (reference implementation, {__version__})")
        print(f"transaction: {result['transaction_id']}")
        for step in result["transitions"]:
            print(
                f"  seq {step['seq']:>2}  {step['transition']:<28} "
                f"{step['event_id'][:16]}…  [{step['label']}]"
            )
        print(f"chain verifies: {'YES' if result['chain_ok'] else 'NO'}")
        print(f"receipt: {json.dumps(result['receipt'], sort_keys=True, default=str)}")
        print(f"verifiable chain written to: {result['logdir']}")
    return 0 if result["chain_ok"] else 1


# -------------------------------------------------------------------- verify


def _cmd_verify(args: argparse.Namespace) -> int:
    report = eventlog.verify(args.logdir)
    data = report.to_dict()
    if args.json:
        _print(data, as_json=True)
    else:
        status = "OK" if report.ok else "FAILED"
        print(f"verify {args.logdir}: {status} ({report.events_checked} events)")
        for finding in report.findings:
            lineno = f" line {finding['lineno']}" if "lineno" in finding else ""
            print(f"  {finding['code']}:{lineno} {finding['detail']}")
    return 0 if report.ok else 1


# --------------------------------------------------------------------- fleet


def _cmd_fleet_validate(args: argparse.Namespace) -> int:
    try:
        config = fleet_mod.load_fleet(args.yaml)
    except Exception as exc:
        print(f"fleet validate: cannot load {args.yaml}: {exc}", file=sys.stderr)
        return 2
    report = fleet_mod.validate_fleet(config)
    if args.json:
        _print(report, as_json=True)
    else:
        status = "OK" if report["ok"] else "FAILED"
        print(
            f"fleet validate {args.yaml}: {status} "
            f"({report['node_count']} nodes, {report['field_nodes']} FIELD)"
        )
        for finding in report["findings"]:
            print(f"  {finding['code']}: {finding['detail']}")
    return 0 if report["ok"] else 1


# ------------------------------------------------------------------- rc1-test


def _cmd_rc1_test(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="szl-beacon-rc1-") as tmp:
        results = rc1_sim.run_acceptance_fixtures(tmp)
    all_passed = all(r["passed"] for r in results)
    if args.json:
        _print({"simulation": True, "all_passed": all_passed, "results": results}, as_json=True)
    else:
        print("RC1 acceptance fixtures — SOFTWARE SIMULATION of the hardware boundary")
        for result in results:
            mark = "PASS" if result["passed"] else "FAIL"
            print(f"  {result['test']} [{mark}] {result['name']} — {result['detail']}")
    return 0 if all_passed else 1


# ---------------------------------------------------------------------- sync


def _cmd_sync(args: argparse.Namespace) -> int:
    report = sync_mod.merge_logs(args.dir_a, args.dir_b, args.out)
    if args.json:
        _print(report, as_json=True)
    else:
        status = "OK" if report["ok"] else "FAILED"
        print(f"sync: {status}")
        print(
            f"  merged {report.get('merged_events', 0)} events "
            f"({report.get('duplicates_removed', 0)} duplicates removed)"
        )
        for conflict in report["conflicts"]:
            print(
                f"  CONFLICT seq {conflict['seq']}: {conflict['digest_a'][:12]}… vs "
                f"{conflict['digest_b'][:12]}… -> debt {conflict['debt_id']} (OPEN)"
            )
        for note in report["notes"]:
            print(f"  note: {note}")
    return 0 if report["ok"] else 1


# -------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="szl_beacon",
        description=(
            "SZL Beacon REALITY PROTOCOL reference implementation. "
            "Zero physical units exist; this is protocol software only."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="run one complete Reality Transaction end to end")
    p_demo.add_argument("--json", action="store_true", help="machine-readable output")
    p_demo.set_defaults(func=_cmd_demo)

    p_verify = sub.add_parser("verify", help="verify an event-log hash chain")
    p_verify.add_argument("logdir", help="directory containing events.jsonl")
    p_verify.add_argument("--json", action="store_true", help="machine-readable output")
    p_verify.set_defaults(func=_cmd_verify)

    p_fleet = sub.add_parser("fleet", help="fleet configuration commands")
    fleet_sub = p_fleet.add_subparsers(dest="fleet_command", required=True)
    p_fv = fleet_sub.add_parser("validate", help="validate a fleet YAML configuration")
    p_fv.add_argument("yaml", help="path to fleet YAML file")
    p_fv.add_argument("--json", action="store_true", help="machine-readable output")
    p_fv.set_defaults(func=_cmd_fleet_validate)

    p_rc1 = sub.add_parser(
        "rc1-test", help="run the RC1-01..04 acceptance fixtures (SIMULATION)"
    )
    p_rc1.add_argument("--json", action="store_true", help="machine-readable output")
    p_rc1.set_defaults(func=_cmd_rc1_test)

    p_sync = sub.add_parser("sync", help="offline-first peer sync of two event logs")
    p_sync.add_argument("dir_a", help="first log directory")
    p_sync.add_argument("dir_b", help="second log directory")
    p_sync.add_argument("out", help="output directory for the merged log")
    p_sync.add_argument("--json", action="store_true", help="machine-readable output")
    p_sync.set_defaults(func=_cmd_sync)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
