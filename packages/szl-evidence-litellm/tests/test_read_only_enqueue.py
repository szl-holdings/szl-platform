"""Inspection sinks reject receipt admission in every execution lane."""

from __future__ import annotations

import asyncio

import pytest
from conftest import make_pending
from szl_evidence_litellm import EvidenceSink


def _files(directory):
    if not directory.exists():
        return None
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("lane", ["async", "thread"])
@pytest.mark.parametrize("existing", ["missing", "empty", "populated"])
def test_read_only_enqueue_preserves_files_and_queue(sink_dir, policy, lane, existing):
    if existing == "empty":
        sink_dir.mkdir()
    elif existing == "populated":
        writer = EvidenceSink(sink_dir, policy=policy)
        writer._persist_batch([make_pending(policy, call_id="existing")])
    before = _files(sink_dir)
    sink = EvidenceSink(sink_dir, policy=policy, read_only=True)
    pending = make_pending(policy, call_id="rejected")

    async def attempt():
        try:
            with pytest.raises(RuntimeError, match="read-only sinks inspect"):
                sink.enqueue(pending)
        finally:
            await sink.aclose()

    if lane == "async":
        asyncio.run(attempt())
    else:
        try:
            with pytest.raises(RuntimeError, match="read-only sinks inspect"):
                sink.enqueue(pending)
        finally:
            sink.drain_thread_lane()

    assert sink.stats()["queued"] == 0
    assert sink.stats()["dropped_counter"] == 0
    assert _files(sink_dir) == before
    assert sink._queue is None
    assert sink._tqueue is None
    assert sink._flusher is None
    assert sink._worker is None


@pytest.mark.parametrize("lane", ["async", "thread"])
def test_read_only_rejection_precedes_payload_copy(sink_dir, policy, lane):
    class DoNotCopy:
        def __deepcopy__(self, memo):
            raise AssertionError("read-only enqueue must not inspect or copy payloads")

    sink = EvidenceSink(sink_dir, policy=policy, read_only=True)

    def attempt():
        with pytest.raises(RuntimeError, match="read-only sinks inspect"):
            sink.enqueue(DoNotCopy())

    async def run():
        attempt()

    if lane == "async":
        asyncio.run(run())
    else:
        attempt()
    assert not sink_dir.exists()
