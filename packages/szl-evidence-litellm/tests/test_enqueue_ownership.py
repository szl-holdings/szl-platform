"""The enqueue boundary owns the accepted payload while persistence is delayed."""

from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest
from conftest import make_pending
from szl_evidence_litellm import EvidenceSink, verify_sink
from szl_receipts import jcs_canon_bytes


def _handoff_then_drain(sink, lane, pending, mutate):
    if lane == "async":
        async def scenario():
            sink.enqueue(pending)
            # No await: the background task cannot persist before mutation.
            mutate()
            await sink.aclose()

        asyncio.run(scenario())
    else:
        # A stalled worker leaves its queue for the real synchronous drain.
        sink._worker_loop = lambda: None
        sink.enqueue(pending)
        sink._worker.join(timeout=5)
        assert not sink._worker.is_alive()
        mutate()
        sink.drain_thread_lane()


@pytest.mark.parametrize("lane", ["async", "thread"])
@pytest.mark.parametrize("mutation", ["none", "receipt", "nested_receipt", "evidence"])
def test_accepted_payload_survives_caller_mutation(sink_dir, policy, lane, mutation):
    sink = EvidenceSink(sink_dir, policy=policy, flush_interval_s=0.01)
    pending = make_pending(policy)
    expected_receipt = deepcopy(pending.receipt)
    expected_evidence_bytes = jcs_canon_bytes(pending.evidence_doc)
    replacement = make_pending(policy, actor="replacement")

    def mutate():
        if mutation == "receipt":
            # Replace the contents with another valid, content-addressed receipt.
            # Verification alone cannot detect that it was not the accepted one.
            pending.receipt.clear()
            pending.receipt.update(replacement.receipt)
        elif mutation == "nested_receipt":
            pending.receipt["decision"]["rationale"] = "edited after enqueue"
        elif mutation == "evidence":
            pending.evidence_doc["prompt_tokens"] = 999

    _handoff_then_drain(sink, lane, pending, mutate)

    entries = list(sink.iterate())
    assert len(entries) == 1
    assert entries[0]["receipt"] == expected_receipt
    assert (sink.directory / pending.evidence_uri).read_bytes() == expected_evidence_bytes
    assert sink.stats()["queued"] == 0
    assert sink.stats()["dropped_counter"] == 0
    report = verify_sink(sink.directory)
    assert report["ok"], report["findings"]
    assert report["sidecars"] == {"checked": 1, "missing": 0, "mismatched": 0}
