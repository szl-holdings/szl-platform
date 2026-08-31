# Phase 6 — MCP Attestation (deny-on-drift)

MCP servers mutate their tool surfaces over time, and the MCP spec has no
standard mechanism to verify that a runtime tool description matches the
install-time audit — the recommended control in the wild is manual diffing,
and most evaluated clients do zero static validation. OWASP's MCP Top 10
calls the failure mode MCP03 Tool Poisoning and prescribes manifest integrity
verification. This phase is that control, running as a gate.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## The 13 drift classes

A server manifest is compared against its attested baseline across these
classes:

1. **tool-description** — any semantic change to a tool's description text.
2. **input-schema** — added, removed, or re-typed input properties.
3. **output-schema** — response shape changes.
4. **default-value** — changed defaults (silent behavior change).
5. **annotation-hint** — readOnlyHint/destructiveHint and friends flipping.
6. **permission-scope** — widened or narrowed scopes.
7. **endpoint-transport** — command, args, URL, or transport changes.
8. **auth-requirement** — credential or audience changes.
9. **version-pin** — server or tool version drift.
10. **manifest-digest** — canonical digest mismatch not attributable to a
    listed class.
11. **tool-removal** — a previously attested tool is gone.
12. **tool-addition** — an unattested tool appears.
13. **server-instructions** — the server-level instructions block changed.

## Deny-on-drift: exit 2

Any detected drift class is a denial: the gate exits **exit 2**, prints the
drift class with evidence (baseline digest, runtime digest, differing JSON
pointer), and nothing downstream runs. There is no warn-through.

## Canonical equivalence — whitespace-only must NOT drift

Manifests are compared after RFC 8785 canonicalization (Defect 2, Phase 1).
A **whitespace-only** or key-order change produces identical canonical bytes
and therefore must NOT raise drift; a drift gate that fires on
canonical-equivalent documents trains operators to ignore it. Eight fixtures
pin this harness: one clean pair, one fixture per representative drift class,
and one canonical-equivalent pair that must pass.

## Estate context

`hatun-mcp` (the doctrine-aware MCP server) is the first attested server; its
baseline manifest is the reference for the fixture set. The scaffold below is
the baseline shape the drift checker consumes.

<!-- extract: szl_v14/fixtures/mcp_manifest.baseline.json mode=644 -->
```json
{
  "server": "hatun-mcp",
  "manifest_version": 1,
  "tools": [
    {
      "name": "doctrine_lookup",
      "description": "Look up doctrine by phase id",
      "input_schema": {"type": "object", "properties": {"phase": {"type": "string"}}, "required": ["phase"]},
      "annotations": {"readOnlyHint": true}
    },
    {
      "name": "receipt_verify",
      "description": "Verify a DSSE receipt envelope",
      "input_schema": {"type": "object", "properties": {"envelope": {"type": "string"}}, "required": ["envelope"]},
      "annotations": {"readOnlyHint": true}
    }
  ]
}
```

UNKNOWN is never PASS: a server whose runtime manifest cannot be fetched is
UNKNOWN, and UNKNOWN blocks the gate exactly like a drift finding does.
