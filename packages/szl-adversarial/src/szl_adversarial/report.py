"""The ATTACK_REPORT: public markdown plus the harness's self-receipt.

The report is a *runtime receipt of the harness itself*: its timestamp is
real wall-clock time (doctrine in szl-receipts: receipts record that
something happened at a moment; determinism lives in canonical form, not in
pretending runs are timeless), and its body is hashed and bound into a
GovernedAction/v1 receipt written through ``szl_receipts.write_envelope``.

A harness that refuses to attest to its own output has no business auditing
anyone else's: whatever the table says — clean pass or honest break — the
report and its receipt are written the same way, and the receipt names the
exact ``szl-receipts`` version under attack so a fixed core and a broken
core can never share an attestation.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import szl_receipts
from szl_receipts import (
    Outcome,
    build_receipt,
    jcs_canon_bytes,
    load_private_key,
    sha256_file,
    sha256_hex,
    sign_bytes,
    write_envelope,
)

from .harness import HarnessResult

__all__ = [
    "REPORT_FILENAME",
    "REPORT_PAYLOAD_TYPE",
    "render_markdown",
    "verdict_outcome",
    "write_report",
]

REPORT_FILENAME = "ATTACK_REPORT.md"
REPORT_PAYLOAD_TYPE = "application/vnd.szl.governed-action+json"

_PROCESS_POLICY_DIGEST = sha256_hex(b"szl-adversarial:v1:attack-harness-policy")


def verdict_outcome(harness: HarnessResult) -> Outcome:
    """The outcome the harness records for its own run — FAIL if anything won.

    Doctrine rule 3 means there is no third option here: a run either
    resisted everything (PASS) or it did not (FAIL). WARN-only limitations do
    not fail the run, but they are recorded in the receipt's rationale.
    """
    return Outcome.PASS if harness.passed else Outcome.FAIL


def render_markdown(harness: HarnessResult, *, generated_at: datetime | None = None) -> str:
    """Render the full ATTACK_REPORT.md body."""
    moment = (generated_at or datetime.now(UTC)).astimezone(UTC)
    stamped = moment.isoformat().replace("+00:00", "Z")
    verdict_line = harness.verdict_line()
    outcome = verdict_outcome(harness)

    lines: list[str] = []
    lines.append("# SZL Receipt Chain — ATTACK REPORT")
    lines.append("")
    lines.append(f"- **Generated at (UTC):** {stamped}")
    lines.append(f"- **szl-receipts version under attack:** {szl_receipts.__version__}")
    lines.append(
        f"- **Run duration:** {harness.duration_seconds:.2f}s across "
        f"{harness.total} attacks, each against an isolated fresh fixture"
    )
    lines.append(f"- **Harness self-assessment:** {outcome.value}")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{verdict_line}.**")
    lines.append("")
    if harness.passed:
        lines.append(
            "Every non-limitation attack was blocked by the real "
            f"`szl-receipts` {szl_receipts.__version__} library — no mocks, "
            "no toy verifiers, no fixture reuse between attacks."
        )
    else:
        lines.append("The following attacks **succeeded** and must be fixed before")
        lines.append("the receipt chain's public claim stands:")
        lines.append("")
        for result in harness.broken:
            lines.append(f"- **{result.name}** ({result.category}) — {result.detail}")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| # | Attack | Category | Result | Detail |")
    lines.append("|---|--------|----------|--------|--------|")
    for index, result in enumerate(harness.results, start=1):
        if result.blocked:
            representation = "BLOCKED"
        elif result.limitation:
            representation = "WARN"
        else:
            representation = "BROKEN"
        detail = result.detail.replace("|", "\\|")
        lines.append(
            f"| {index} | `{result.name}` | {result.category} | **{representation}** | {detail} |"
        )
    lines.append("")
    lines.append("### Result semantics")
    lines.append("")
    lines.append("- **BLOCKED** — the defense held; counts toward the pass.")
    lines.append(
        "- **BROKEN** — the attack won (or the verifier crashed, which *is* a "
        "successful attack); fails the run."
    )
    lines.append(
        "- **WARN** — a documented limitation of the security model itself; "
        "does not fail the run, and must never silently disappear from this table."
    )
    lines.append("")
    if harness.warnings:
        lines.append("## Documented limitations (WARN)")
        lines.append("")
        for warning in harness.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    lines.append("## Self-receipt")
    lines.append("")
    lines.append(
        "This file's bytes are hashed (sha256) and bound as the subject of a "
        "`GovernedAction/v1` receipt written by the harness itself via "
        "`szl_receipts.write_envelope`, honestly named "
        "`attack-report.unsigned.json` (or signed when the run is given an "
        "operator key via `--sign-with`). The receipt records the verdict "
        "outcome "
        f"({outcome.value}) and pins the `szl-receipts` version under attack, so "
        "this report can itself be verified with the same library it attacks."
    )
    lines.append("")
    return "\n".join(lines)


def _self_receipt(
    harness: HarnessResult,
    report_path: Path,
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    """Build the GovernedAction receipt attesting to this report."""
    report_sha = sha256_file(report_path)
    verdict = harness.verdict_line()
    rationale = (
        f"Adversarial harness run: {verdict}. "
        f"{harness.blocked_count}/{harness.non_limitation_total} non-limitation "
        f"attacks blocked; {harness.limitation_count} documented limitation(s); "
        f"szl-receipts=={szl_receipts.__version__}."
    )
    return build_receipt(
        actor="szl-adversarial",
        action="adversarial-attack-run",
        policy={
            "id": "szl.adversarial-harness",
            "version": "1.0",
            "digest_sha256": _PROCESS_POLICY_DIGEST,
        },
        outcome=verdict_outcome(harness),
        rationale=rationale,
        subjects=[{"name": report_path.name, "sha256": report_sha}],
        evidence=[
            {
                "uri": f"library://szl-receipts/{szl_receipts.__version__}",
                "sha256": sha256_hex(jcs_canon_bytes(harness.to_dict())),
            }
        ],
        created_at=generated_at,
    )


def write_report(
    harness: HarnessResult,
    out_dir: str | Path,
    *,
    sign_with: str | Path | None = None,
) -> dict[str, Path]:
    """Write ATTACK_REPORT.md and the harness's self-receipt into *out_dir*.

    Returns the paths written. If *sign_with* points at an Ed25519 private
    key PEM, the self-receipt is signed (and lands under the honest
    ``attack-report.json`` name); otherwise it is written unsigned under the
    honest ``attack-report.unsigned.json`` name.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC)
    report_path = out / REPORT_FILENAME
    report_path.write_text(
        render_markdown(harness, generated_at=generated_at),
        encoding="utf-8",
    )

    receipt = _self_receipt(harness, report_path, generated_at=generated_at)
    payload = jcs_canon_bytes(receipt)
    if sign_with is not None:
        key = load_private_key(sign_with)
        envelope = sign_bytes(payload, REPORT_PAYLOAD_TYPE, key)
    else:
        # An empty signatures array is NOT a signature: write_envelope maps
        # this to the honest *.unsigned.json name automatically.
        envelope = {
            "payload": base64.b64encode(payload).decode("ascii"),
            "payloadType": REPORT_PAYLOAD_TYPE,
            "signatures": [],
        }
    receipt_path = write_envelope(out / "attack-report", envelope)
    return {"report": report_path, "receipt": receipt_path}
