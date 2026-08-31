# PR #6 — Python 3.11 cancellation repair receipt

- Pull request: `szl-holdings/szl-platform#6`
- Diagnosed runtime: CPython `3.11.16`
- Affected package: `packages/szl-evidence-litellm`
- Reproducer: `TestBackpressure::test_drain_after_stall_recovers`
- Root cause: `asyncio.wait_for(queue.get(), timeout=...)` could remain in a cancelling state when external shutdown cancellation raced the internal queue timeout.
- Production repair: use `asyncio.timeout(...)` around `queue.get()` and bound the flusher await during `aclose()`.
- Regression bound: sink shutdown must complete within `2.0s` in the recovery test.
- Temporary diagnostic workflow removed: `yes`
- CI protections weakened: `no`

Evidence captured before repair showed the flusher task stuck in `cancelling`, with its child `Queue.get` still pending. This signed receipt also retriggers PR CI from a user-authored commit because GitHub does not execute ordinary workflows from a commit pushed by `GITHUB_TOKEN`.
