"""Command-line interface: ``python -m szl_alignment``.

Subcommands:

- ``inspect PATH``                        — print one repo's RepoReport
- ``plan PATH``                           — print the deterministic action list
- ``apply PATH [--apply] [--json]``       — dry-run diff summary by default;
                                            --apply writes on the alignment branch
- ``org-report MIRROR_DIR --out DIR``     — ALIGNMENT_REPORT.md + matrix.csv
                                            over every repo in a mirror dir

All read paths are offline and never raise on weird repos; ``--help`` is
available on the root parser and every subcommand.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from szl_alignment.apply import ApplyError, apply_plan, format_summary
from szl_alignment.const import ALIGNMENT_BRANCH, __version__
from szl_alignment.inspect import RepoReport, inspect_repo
from szl_alignment.plan import plan_alignment
from szl_alignment.report import render_org_report, score_repo, totals_line


def build_parser() -> argparse.ArgumentParser:
    """Build the root parser with all subcommands (tested directly)."""
    parser = argparse.ArgumentParser(
        prog="szl_alignment",
        description=(
            "szl-holdings org alignment engine — one header, one security policy, "
            "one CI gate, one contribution path, per-repo receipts. "
            "Control before action. Evidence after."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p_inspect = sub.add_parser(
        "inspect",
        help="inspect one repo and print its RepoReport",
        description="Read-only measurement of one repo against the org standard.",
    )
    p_inspect.add_argument("path", help="path to the repository")
    p_inspect.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    p_plan = sub.add_parser(
        "plan",
        help="print the deterministic alignment plan for one repo",
        description="Compute the action list for one repo without changing anything.",
    )
    p_plan.add_argument("path", help="path to the repository")
    p_plan.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    p_apply = sub.add_parser(
        "apply",
        help="dry-run the plan (default) or apply it on the alignment branch",
        description=(
            "Dry-run by default: prints the unified-diff summary. With --apply, "
            f"writes files on branch {ALIGNMENT_BRANCH!r} (created if needed), "
            "commits with a signed-off message, and writes the PR body to "
            ".git/SZL_ALIGNMENT_PR_BODY.md. Never touches the default branch, "
            "never force-pushes, never deletes files."
        ),
    )
    p_apply.add_argument("path", help="path to the repository (must be a git repo for --apply)")
    p_apply.add_argument(
        "--apply",
        action="store_true",
        help="actually apply (default: dry-run only)",
    )
    p_apply.add_argument(
        "--json",
        action="store_true",
        help="emit the ApplyResult as JSON instead of the diff summary",
    )
    p_apply.add_argument(
        "--branch",
        default=ALIGNMENT_BRANCH,
        help=f"alignment branch to use (default: {ALIGNMENT_BRANCH})",
    )

    p_org = sub.add_parser(
        "org-report",
        help="render ALIGNMENT_REPORT.md + matrix.csv over a mirror of repos",
        description=(
            "Inspect every immediate child directory of MIRROR_DIR that looks "
            "like a repo and write the org report into DIR."
        ),
    )
    p_org.add_argument("mirror_dir", help="directory whose children are repos")
    p_org.add_argument("--out", required=True, help="output directory for the two artifacts")
    p_org.add_argument("--json", action="store_true", help="also print reports as JSON to stdout")

    return parser


# ---------------------------------------------------------------------------
# subcommand implementations
# ---------------------------------------------------------------------------


def _report_to_dict(report: RepoReport) -> dict:
    """asdict plus the computed score — the JSON shape the CLI promises."""
    data = asdict(report)
    data["score"] = score_repo(report)
    return data


def cmd_inspect(args: argparse.Namespace) -> int:
    report = inspect_repo(args.path)
    if args.json:
        print(json.dumps(_report_to_dict(report), indent=2))
    else:
        _print_report(report)
    return 0


def _print_report(report: RepoReport) -> None:
    print(f"# {report.name}")
    print(f"  path:               {report.path}")
    print(f"  score:              {score_repo(report)}%")
    print(f"  readme:             {'yes' if report.has_readme else 'no'}")
    print(
        f"  license:            {report.license_kind}"
        + (f" ({report.license_file})" if report.license_file else "")
    )
    print(f"  security:           {'yes' if report.has_security else 'no'}")
    print(f"  contributing:       {'yes' if report.has_contributing else 'no'}")
    print(f"  code of conduct:    {'yes' if report.has_coc else 'no'}")
    print(f"  pr template:        {'yes' if report.has_pr_template else 'no'}")
    print(f"  issue templates:    {'yes' if report.has_issue_templates else 'no'}")
    print(f"  ci workflows:       {', '.join(report.ci_workflows) or 'none'}")
    print(f"  python detected:    {'yes' if report.python_detected else 'no'}")
    print(f"  typescript detected:{'yes' if report.typescript_detected else 'no'}")
    print(f"  doctrine header:    {'yes' if report.doctrine_header_present else 'no'}")
    scan = report.forbidden_scan
    print(
        f"  forbidden scan:     {len(scan.violations)} violation(s), "
        f"{scan.guard_mentions} guard mention(s), "
        f"{scan.files_scanned} file(s) scanned, {scan.files_skipped} skipped"
    )
    for v in scan.violations:
        print(f"    VIOLATION {v.file}:{v.line}: {v.text}")
    for q in report.open_questions:
        print(f"  open question:      {q}")


def cmd_plan(args: argparse.Namespace) -> int:
    report = inspect_repo(args.path)
    actions = plan_alignment(report)
    if args.json:
        print(json.dumps([asdict(a) for a in actions], indent=2, default=str))
    else:
        _print_plan(actions)
    return 0


def _print_plan(actions) -> None:
    if not actions:
        print("plan: repo is fully aligned — 0 actions")
        return
    print(f"plan: {len(actions)} action(s)")
    for i, a in enumerate(actions, 1):
        flag = " [NEEDS REVIEW]" if a.needs_review else ""
        print(f"  {i}. {a.kind.value} {a.path}{flag}")
        print(f"       {a.reason}")


def cmd_apply(args: argparse.Namespace) -> int:
    report = inspect_repo(args.path)
    actions = plan_alignment(report)
    if not actions:
        print("plan: repo is fully aligned — nothing to apply")
        return 0
    try:
        result = apply_plan(args.path, actions, branch=args.branch, dry_run=not args.apply)
    except ApplyError as exc:
        print(f"apply refused: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(asdict(result), indent=2, default=str))
    else:
        print(format_summary(result))
    return 0


def cmd_org_report(args: argparse.Namespace) -> int:
    mirror = Path(args.mirror_dir)
    if not mirror.is_dir():
        print(f"org-report: not a directory: {mirror}", file=sys.stderr)
        return 2

    repos = sorted(
        (child for child in mirror.iterdir() if child.is_dir() and not child.name.startswith(".")),
        key=lambda p: p.name.lower(),
    )
    if not repos:
        print(f"org-report: no repo-like directories under {mirror}", file=sys.stderr)
        return 2

    print(f"org-report: inspecting {len(repos)} repos under {mirror} ...", file=sys.stderr)
    reports: list[RepoReport] = []
    for i, repo in enumerate(repos, 1):
        reports.append(inspect_repo(repo))
        if i % 10 == 0 or i == len(repos):
            print(f"org-report:   {i}/{len(repos)} done", file=sys.stderr)

    report_md, matrix_csv = render_org_report(reports)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "ALIGNMENT_REPORT.md"
    matrix_path = out_dir / "matrix.csv"
    report_path.write_text(report_md, encoding="utf-8")
    matrix_path.write_text(matrix_csv, encoding="utf-8")

    if args.json:
        print(json.dumps({"reports": [_report_to_dict(r) for r in reports]}, indent=2, default=str))

    print(f"wrote {report_path}")
    print(f"wrote {matrix_path}")
    print(totals_line(reports))
    return 0


_COMMANDS = {
    "inspect": cmd_inspect,
    "plan": cmd_plan,
    "apply": cmd_apply,
    "org-report": cmd_org_report,
}


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0 ok, 2 usage/refusal)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return _COMMANDS[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
