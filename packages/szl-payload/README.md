# szl-payload

The deterministic SZL master-payload builder with hard compile gates. It
compiles the doctrine in `sections/` into `dist/SZL_MASTER_PAYLOAD_V14.md`,
extracts inline scaffold files into `dist/extracted/`, and exports the
attestation-side artifacts (`export_manifest.unsigned.json`, receipt,
report, operator packet) into `dist/export/`.

## Doctrine invariants

- **sections/ is source; dist/ is derived.** Never hand-edit anything under
  `dist/` — the next build overwrites it.
- **No timestamps in the payload body.** Build time lives only in the export
  receipt (which uses the newest source-input mtime — the SOURCE_DATE_EPOCH
  reproducible-build convention — so identical inputs rebuild byte-identical
  export directories). This is what makes `make idempotent` a real proof.
- **UNKNOWN is never PASS.** Every gate fails closed; the operator packet
  renders UNKNOWN until evidence exists.

## Layout

```
pyproject.toml          package metadata; deps: rfc8785==1.0.2 (pinned), jinja2>=3.1
manifest.toml           explicit ordered [[sections]] list — never a glob
sections/               the doctrine source (one markdown file per phase)
lint/forbidden.txt      forbidden regexes scanned over the built output
lint/banned_claims.txt  banned claims + the signed/unsigned proximity rule
templates/              Jinja2: RECEIPT.j2, REPORT.j2, OPERATOR_PACKET.j2
src/szl_payload/        manifest.py, gates.py, builder.py, extract.py, export.py, cli.py
tests/                  offline pytest suite
Makefile                all / verify / idempotent / clean
```

## Usage

```
python -m szl_payload.build [generate|compile|extract|export|verify|all] [--root DIR] [--json]
```

- `generate` — validate the manifest contract footing (sections present, lint
  files present); writes nothing.
- `compile` — assemble the payload; per-section `must_contain` token
  assertions, `require_dns_first`, forbidden patterns, banned claims, and the
  compound `proxied_pages_apex` rule all run as compile gates. Any finding
  fails the build with line numbers.
- `extract` — write `<!-- extract: <relpath> mode=<octal> -->` scaffold
  blocks to `dist/extracted/`. Path escape (`..`, absolute paths) is rejected
  before any byte is written — this document gets fed to agents.
- `export` — compile + extract, then write the canonicalized
  `export_manifest.unsigned.json` (named unsigned because `signatures == []`
  — honest naming), the receipt, the report, and the ten-answer operator
  packet (all UNKNOWN by default).
- `verify` — re-digest sections against the embedded comments, re-run all
  gates over the built file, assert the export manifest is honestly named
  with `signatures == []`, grep `dist/` for the forbidden domain, and assert
  `publication_eligible` is false.
- `all` (default) — generate → compile → extract → export.

Exit codes: `0` clean · `2` gate failure · `3` operational error.

## Make targets

```
make all         # generate → compile → extract → export
make verify      # the verify stage above
make idempotent  # build, copy dist/, rebuild, diff -r — must be byte-identical
make test        # pytest
make clean       # rm -rf dist/
```

## Canonicalization backend

RFC 8785 JCS is load-bearing (Phase 1, Defect 2: `json.dumps(sort_keys=True)`
is not JCS). The package prefers the pinned `rfc8785==1.0.2` distribution. In
environments where that pin cannot be installed, `szl_payload._jcs` falls
back to the estate's stdlib-only implementation, `szl_receipts.jcs` from the
sibling `packages/szl-receipts` package (full ES6 number rules, UTF-16 key
ordering, minimal escaping). The active backend is recorded in every export
manifest as `jcs_backend`.

## Tests

```
python3 -m pytest packages/szl-payload -q    # from the repo root
```

The suite runs fully offline: gate unit tests (including the forbidden-domain
lookbehind, the banned-claims proximity window, and the compound
proxied-apex rule), extract escape rejection, unsigned-export honesty,
end-to-end build over the real `sections/`, CLI exit codes, and full-tree
idempotency.
