# Phase 10 — PRs

Pull requests are the last phase, not the first: nothing new opens while the
existing queue is unmergeable.

## Safe defaults (verbatim, non-negotiable)

```
AUDIT_ONLY=true DRY_RUN=true MUTATIONS=false TRAINING=false PUBLISHING=false DNS_WRITES=false AUTO_MERGE=false DNS_MUTATION=false CLOUDFLARE_MUTATION=false HF_VISIBILITY_MUTATION=false PRODUCTION_SIGNING=false
```

## Resolve first

Approximately twelve PRs are open across the org and **none is currently
mergeable**. The rule is absolute: **resolve existing open PRs before opening more**. A new PR opened over a red queue is process debt, and the gate
counts open-but-unmergeable PRs as a blocker class.

## V11 verification

The four V11 PRs — **#80, #1529, #20, #5** — are checked with the dedicated
`verify-v11` command: state, head SHA, merge SHA, CI result, and post-merge
regression. Do not recreate merged work; repair only regressions. The
DSSEv1-PAE vs SIGv1 preimage regression test is an explicit CI assertion —
the exact cross-domain bug V11 shipped is the thing CI must keep dead. The
15-row PR task queue maps repo → title → gate so every row has one owner
check.

## Rate-limit discipline

The V11 run was interrupted when a personal access credential (5k
requests/hour) exhausted mid-CI. CI authenticates as a GitHub App
installation (15k/hour) instead; the exchange is part of the doctor
environment check.

## Merge discipline

`AUTO_MERGE=false` always. Every merge is gated behind a printed
authorization packet — head SHA, CI evidence, rollback ref — and the packet
is printed, then the run stops. A merge without its post-merge regression
check is reported UNKNOWN, and UNKNOWN is never PASS.
