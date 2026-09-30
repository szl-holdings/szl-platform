# Sovereign Cloud Node — runbook (live since 2026-09-30)

The always-on mesh node: a Vast.ai RTX 4060 Ti 16GB (instance `49576549`, ~$0.063/hr
against the account credit) running the full governed stack. Built entirely by the
estate's own tooling; every piece below is real and reproducible.

## Architecture (all verified live)

```
client (a11oy Space / any OpenAI-compatible caller)
  │  HTTPS, Cloudflare edge TLS (valid cert, auto)
  ▼
trycloudflare quick-tunnel URL  ──(HTTP/2; QUIC is blocked on vast hosts)──▶ node
                                                                              │  LiteLLM :4000  (bearer: $LITELLM_MASTER_KEY)
                                                                              │   ├─ szl-evidence-litellm → hash-chained receipts (/root/evidence/receipts.jsonl)
                                                                              │   └─ Ollama :11434 → llama3.1:8b (4.9GB, pulled)
                                                                              ▼
                                                                   chain verifies via verify_sink()
```

State proof on first light: Space health flipped `UNAVAILABLE → REACHABLE_MODEL_MISMATCH
→ REACHABLE_UNRECEIPTED → LIVE_RECEIPTED` as each layer was closed. The Space's own
`/api/a11oy/v1/llm/route` returns a signed `szl.llm_route.lambda_receipt/v1` per call.

## Honest caveats (known, documented — not hidden)

1. **Quick tunnel URLs are ephemeral.** The `*.trycloudflare.com` hostname changes on
   tunnel restart. When it changes: read the new one from `/root/quicktunnel.log` on the
   node and update the Space secret `A11OY_SOVEREIGN_GATEWAY_URL`. The permanent fix is a
   named tunnel (`gpu-cloud.szl…`), which needs an account-scoped Cloudflare token.
2. **Vast public IPs change on reschedule.** The A record `gpu-cloud.a-11-oy.com`
   (currently 137.175.22.196) is only used by the Caddy path; the quick-tunnel path is
   IP-independent. Caddy terminates on container :443 → host port 11325.
3. **The LE cert (CN=gpu-cloud.a-11-oy.com, expires 2026-12-01)** was issued off-box via
   DNS-01 from the ops sandbox (`scripts/mini_acme.py` pattern: CF TXT through the
   credential proxy, LE direct). Renewal: re-run the same flow and scp the pair.
4. **Cost honesty:** the node ran mostly idle for a month (~$71 of credit). Stop it when
   not needed: `vast.ai` instance 49576549 → Stop. Boot is fully re-scripted by
   `scripts/vast_sovereign_node.sh` + the steps in this file.
5. **The laptop path remains**: `gpu.a-11-oy.com` / `gateway.a-11-oy.com` (tunnel
   szl-laptop-mesh) serve the laptop's own Ollama; pull `llama3.1:8b` there for parity
   (`ollama pull llama3.1:8b` on the laptop).

## Hard-won fixes folded back into the product

- `szl-evidence-litellm` sink now self-heals: enqueue on a running loop boots the
  flusher (regression test proven non-vacuous). Before this fix, receipts silently
  never persisted when the proxy didn't call `sink.start()`.
- LiteLLM proxy YAML callbacks must reference the module-level INSTANCE
  `szl_evidence_litellm.plugin.evidence_logger` and set `SZL_EVIDENCE_LOGGER=1`
  (the singleton is intentionally inert without it).
- LiteLLM ≥ current requires Python ≥ 3.11 — the node uses a deadsnakes 3.11 venv at
  `/root/venv` (Ubuntu 22.04's stock 3.10 cannot run it).

## Node facts

| What | Value |
|---|---|
| Instance | vast.ai `49576549` (RTX 4060 Ti 16GB, US) |
| SSH | `ssh -p 16548 root@ssh4.vast.ai` (key attached by ops; rotate if the box is ever shared) |
| Endpoint | quick-tunnel URL (current) → LiteLLM :4000 |
| Model | `sovereign-llm` / `llama3.1:8b` (aliases of ollama/llama3.1:8b) |
| Evidence | `/root/evidence/receipts.jsonl` + `chain_head.json`, `verify_sink()` green |
| Logs | `/root/{setup,ollama,litellm,caddy,quicktunnel}.log` |
