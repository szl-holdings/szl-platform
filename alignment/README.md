# szl-alignment — the org alignment engine

**Control before action. Evidence after.**

`alignment/` is the tooling layer that brings every szl-holdings repository up
to one standard — the *"every repo fully styled"* layer:

- **One header** — every README carries the doctrine header
  (`templates/README_HEADER.md`, idempotency marker `<!-- szl:header v1 -->`).
- **One security policy** — every repo ships `SECURITY.md`
  (`templates/SECURITY.md`).
- **One CI gate** — every repo runs the release-blocking forbidden-domain
  gate (`.github/workflows/forbidden-domain.yml`); Python repos also get the
  base ruff+pytest pipeline (`base-python-ci.yml`, 3.11/3.12).
- **One contribution path** — `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, a PR
  template, and issue templates with the same shape everywhere.
- **Per-repo receipts** — every alignment change lands on branch
  `szl/alignment-v14` with a signed-off commit and a generated PR body
  (`.git/SZL_ALIGNMENT_PR_BODY.md`) listing what changed, why, and which
  receipts must be attached. UNKNOWN is never claimed as PASS.

## The forbidden-domain rule

The regex `(?<!-)a11oy\.com` is release-blocking CRITICAL across the org.
Canonical surfaces are `a-11-oy.com` (product) and `a11oy.net` (proof).

A line matching the forbidden regex is **allowed** when it is a
prohibition/guard context — i.e. the same line also matches:

```text
/(never|forbidden|not in|assertNotIn|does not appear|is not a surface|blocklist)/i
```

("never use the forbidden domain", `assertNotIn(...)` guards, "is not a
surface of this project", blocklist entries). This classification was
validated on the live org. Guard lines are counted as `guard_mentions`;
everything else is a true violation and becomes a `FIX_FORBIDDEN` action —
**prepared as a diff, flagged NEEDS_REVIEW, never auto-applied** (the right
fix — replace with `a-11-oy.com` or remove — is a human decision).

## Usage

```bash
pip install -e alignment/                # or: PYTHONPATH=alignment/src
python -m szl_alignment inspect <repo>           # one repo -> RepoReport
python -m szl_alignment plan <repo>              # -> deterministic list of Actions
python -m szl_alignment apply <repo>             # dry-run: prints unified diffs
python -m szl_alignment apply <repo> --apply     # branch + files + signed-off commit
python -m szl_alignment org-report <mirror> --out <dir>   # ALIGNMENT_REPORT.md + matrix.csv
```

Every command supports `--help`; `inspect`/`plan`/`apply` support `--json`.

## Safety contract

- Dry-run by default; `--apply` is required to change anything.
- Never touches the default branch: real applies happen on `szl/alignment-v14`
  and the tool aborts if it somehow lands on `main`/`master`.
- Never force-pushes, never deletes files, never overwrites an existing file
  whose content differs (skipped for manual merge instead).
- **Never writes a LICENSE.** Licenses are legal statements (the estate mixes
  Apache-2.0 and LicenseRef-SZL-Proprietary); a missing or unrecognized
  license becomes an advice-only note in the report, not an action.
- Idempotent: marker comments and content comparison make a second run a
  no-op (tested).
- `inspect` never raises on a weird repo — filesystem errors degrade fields
  to UNKNOWN-ish values and record an open question.

## Layout

```text
alignment/
├── README.md                  ← this file
├── pyproject.toml             ← package szl-alignment (src layout)
├── templates/                 ← drop-in governance files + workflows
│   ├── README_HEADER.md       ← doctrine header (badges row + links)
│   ├── SECURITY.md            ← disclosure policy, supported versions, receipts
│   ├── CONTRIBUTING.md        ← szl/<change> branches, conventional commits, sign-off
│   ├── CODE_OF_CONDUCT.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/{bug_report.yml, config.yml}
│   ├── workflows/{base-python-ci.yml, forbidden-domain.yml}
│   └── Makefile.snippet       ← optional standard make targets (manual adopt)
├── src/szl_alignment/
│   ├── inspect.py             ← read-only measurement (never raises)
│   ├── plan.py                ← RepoReport -> deterministic [Action]
│   ├── apply.py               ← dry-run diffs / branch+commit application
│   ├── report.py              ← org matrix.csv + ALIGNMENT_REPORT.md
│   └── cli.py                 ← python -m szl_alignment
└── tests/                     ← offline pytest suite with tmp_path fixture repos
```

Templates resolve by walking up from the installed module (works for the
source checkout and editable installs); override with the
`SZL_ALIGNMENT_TEMPLATES` environment variable.

`templates/Makefile.snippet` is provided for repos that want the standard
`make align-inspect / align-plan / align-check` targets. It is **adopted
manually** (merged into an existing Makefile by a human), never auto-planned:
tooling must not clobber build files.
