# szl-iso42001

**A free, fully offline readiness self-assessment for ISO/IEC 42001 (AI management
systems) and EU AI Act Article 50 (transparency) — that emits a tamper-evident
receipt of its own findings.**

> Readiness self-assessment only. Not legal advice. Not certification. Only an
> accredited body certifies ISO/IEC 42001.

## Why a free checker exists

Getting certified against ISO/IEC 42001 typically costs **tens to hundreds of
thousands of dollars** once you add up consultants, gap analysis, remediation,
and the accredited body's audit fees — and takes **6–12 months** of organized
effort. Most teams don't know where they stand before writing the first check.

This tool answers the only question that matters at the start: **how big is the
gap?** It walks you through 44 controls (34 ISO/IEC 42001 across clauses 4–10
and Annex A themes A.2–A.10, plus 10 EU AI Act Article 50 transparency items),
scores your answers, and hands you a prioritized work plan — in minutes, offline,
for free.

**That is also the point.** This checker demonstrates the product it ships with:
its own readiness report is bound into a tamper-evident receipt (signed-style
when the sibling `szl-receipts` package is installed, honestly named
`*.unsigned.json` when it is not). A governance tool that says "prove, don't
assert" and then emits an unverifiable PDF would be a contradiction. So this
tool receipts itself.

## Install and run

```bash
pip install -e packages/szl-iso42001     # from the szl-platform root

# Browse the corpus
python -m szl_iso42001 list

# First run: generates an all-'unknown' template and exits 2.
# That is a feature — unknown-by-default is the honest starting position.
python -m szl_iso42001 check --answers answers.yaml --out ./out

# Fill in answers.yaml, then run for real:
python -m szl_iso42001 check --answers answers.yaml --out ./out
# -> out/readiness-report.md + out/readiness-receipt.unsigned.json (or signed)
```

`--json` works on both subcommands; `--help` works everywhere.

## How scoring works (and why you can trust it)

- Each control has a **weight** of 1–3 (3 = audit-blocking / legally load-bearing).
- Answers are `yes` (full points), `partial` (half), `no` (zero), `unknown` (zero).
- **`unknown` is never a pass.** It is tracked separately from `no`, because the
  remediation differs: `no` means *fix it*, `unknown` means *go find out*.
- Bands: `READY_FOR_STAGE1_AUDIT` requires ≥ 85% weighted **and** zero `no`
  answers on any weight-3 control. A single unfixed critical control caps you at
  `PARTIAL` even at 90%+ — because that's how a real Stage-1 audit behaves.
  ≥ 50% is `PARTIAL`; below that, `NOT_READY`.
- Scoring is pure and deterministic: same answers, same bytes, same receipt hash,
  on any machine.

**This tool never says "certified" or "compliant".** Those words belong to
accredited certification bodies and courts, not to software.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Assessment ran (any band — `NOT_READY` is a result, not an error) |
| 1 | Invalid input (bad YAML, unknown control ids, invalid answers) |
| 2 | Answers file missing — template generated, go fill it in |

## Verify the receipt

```bash
python - <<'PY'
import hashlib, json, pathlib
out = pathlib.Path("out")
report_hash = hashlib.sha256((out / "readiness-report.md").read_bytes()).hexdigest()
receipt = json.loads((out / "readiness-receipt.unsigned.json").read_text())
assert receipt["subjects"][0]["sha256"] == report_hash, "receipt does not match report"
print("receipt matches report ✓")
PY
```

## Development

```bash
python -m pytest packages/szl-iso42001 -q   # fully offline
ruff check packages/szl-iso42001
```

The control corpus is a single embedded YAML string in
`src/szl_iso42001/controls.py` — reviewable and diffable as data, validated
strictly at load (unique ids, weights in {1,2,3}).

License: Apache-2.0.
