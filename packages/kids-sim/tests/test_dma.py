"""DMA / memory-region tests."""

import numpy as np
import pytest

from kids_sim.memory import (
    REGION_MAP,
    AccessContext,
    AddressFault,
    HardPartitionFault,
    Memory,
    Region,
)

AP_BASE = REGION_MAP[Region.AP_REGION][0]
W_BASE = REGION_MAP[Region.WEIGHT_REGION][0]
RC1_BASE = REGION_MAP[Region.RC1_MAILBOX][0]


def test_dma_load_store_roundtrip():
    mem = Memory()
    data = bytes(range(256))
    mem.write(AP_BASE, data)
    mem.dma(AP_BASE, AP_BASE + 0x1000, 256)
    assert mem.read(AP_BASE + 0x1000, 256) == data


def test_monotonic_counter_increments_per_dma():
    mem = Memory()
    assert mem.monotonic_sequence_counter == 0
    mem.dma(AP_BASE, AP_BASE + 0x100, 16)
    mem.dma(AP_BASE, AP_BASE + 0x200, 16)
    assert mem.monotonic_sequence_counter == 2


def test_hardware_timestamp_is_cycle_count():
    mem = Memory()
    assert mem.hardware_timestamp == 0
    mem.cycle_count = 12345
    assert mem.hardware_timestamp == 12345  # cycles, never wall time


def test_weights_sealed_read_only():
    mem = Memory()
    mem.write(W_BASE, b"\x01" * 8)
    mem.seal_weights()
    with pytest.raises(HardPartitionFault):
        mem.write(W_BASE, b"\x02" * 8)
    assert mem.read(W_BASE, 8) == b"\x01" * 8


def test_rc1_mailbox_ap_write_raises_and_logs():
    mem = Memory()
    with pytest.raises(HardPartitionFault):
        mem.write(RC1_BASE, b"\x41" * 4, ctx=AccessContext.AP)
    assert mem.partition_fault_log[0]["kind"] == "BYPASS_ATTEMPT"
    assert mem.read(RC1_BASE, 4, ctx=AccessContext.RC1) == b"\x00" * 4  # unchanged


def test_rc1_mailbox_rc1_write_ok():
    mem = Memory()
    mem.write(RC1_BASE, b"\x41" * 4, ctx=AccessContext.RC1)
    assert mem.read(RC1_BASE, 4, ctx=AccessContext.AP) == b"\x41" * 4  # AP may READ


def test_ap_dma_into_mailbox_fails_closed():
    mem = Memory()
    mem.write(AP_BASE, b"\x99" * 8)
    with pytest.raises(HardPartitionFault):
        mem.dma(AP_BASE, RC1_BASE, 8, ctx=AccessContext.AP)


def test_address_out_of_range():
    mem = Memory()
    with pytest.raises(AddressFault):
        mem.read(0x7FFF_0000, 4)
    with pytest.raises(AddressFault):
        mem.read(AP_BASE + REGION_MAP[Region.AP_REGION][1] - 2, 4)  # crosses region


def test_tensor_store_load():
    mem = Memory()
    arr = np.arange(12, dtype=np.float32).reshape(3, 4)
    mem.store_array(AP_BASE, arr)
    np.testing.assert_array_equal(mem.load_array(AP_BASE, (3, 4), np.float32), arr)
