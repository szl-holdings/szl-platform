"""KIDS v0.1 memory model.

Flat address space with four regions:

* AP_REGION      — application-processor read/write.
* WEIGHT_REGION  — read-only at runtime (weights are sealed after load).
* RC1_MAILBOX    — hard partition. Writes from AP context raise
  HardPartitionFault. This is the "Linux bypass" property: in the golden
  simulator it is modeled as an access-context check; in RTL it is a
  physical mux the AP cannot drive. ONLY the RC1 engine context may write.
* KV_REGION      — block-table managed, page = 16 tokens x head_dim.

The model tracks a monotonic_sequence_counter incremented on every DMA,
and hardware_timestamp which is a CYCLE COUNT, never wall time. The
simulator has no wall clock in its semantics.
"""

from __future__ import annotations

import enum

import numpy as np

PAGE_TOKENS = 16  # KV block page: 16 tokens x head_dim


class HardPartitionFault(Exception):
    """AP context attempted to write the RC1 hard partition (or otherwise

    bypass the RC1 path). Fail-closed: the write never happens."""


class AddressFault(Exception):
    """Out-of-range or region-crossing access."""


class AccessContext(enum.Enum):
    AP = "ap"  # application processor ("Linux")
    RC1 = "rc1"  # governance microcontroller — the only writer of RC1_MAILBOX


class Region(enum.Enum):
    AP_REGION = "ap"
    WEIGHT_REGION = "weights"
    RC1_MAILBOX = "rc1"
    KV_REGION = "kv"


# Fixed memory map (byte addresses). Sizes are the v0.1 sim budget.
REGION_MAP: dict[Region, tuple[int, int]] = {
    Region.AP_REGION: (0x0000_0000, 1 << 24),  # 16 MiB
    Region.WEIGHT_REGION: (0x0100_0000, 1 << 24),  # 16 MiB
    Region.RC1_MAILBOX: (0x0200_0000, 1 << 16),  # 64 KiB
    Region.KV_REGION: (0x0300_0000, 1 << 24),  # 16 MiB
}


def region_of(addr: int) -> Region:
    for region, (base, size) in REGION_MAP.items():
        if base <= addr < base + size:
            return region
    raise AddressFault(f"address 0x{addr:08x} not in any region")


class Memory:
    """Flat byte-addressable memory with region access rules."""

    def __init__(self) -> None:
        self._regions: dict[Region, np.ndarray] = {
            r: np.zeros(size, dtype=np.uint8) for r, (_, size) in REGION_MAP.items()
        }
        self._weights_sealed = False
        self.monotonic_sequence_counter = 0
        self.cycle_count = 0  # hardware_timestamp: CYCLES, never wall time
        self.partition_fault_log: list[dict] = []

    # --- region helpers -------------------------------------------------
    def _slice(self, addr: int, nbytes: int) -> tuple[Region, slice]:
        region = region_of(addr)
        base, size = REGION_MAP[region]
        if nbytes < 0 or addr - base + nbytes > size:
            raise AddressFault(f"access [{addr:#x}, +{nbytes}) crosses region {region.value}")
        return region, slice(addr - base, addr - base + nbytes)

    def seal_weights(self) -> None:
        """Weights become read-only for the remainder of the run."""
        self._weights_sealed = True

    # --- byte access ----------------------------------------------------
    def read(self, addr: int, nbytes: int, ctx: AccessContext = AccessContext.AP) -> bytes:
        region, sl = self._slice(addr, nbytes)
        return self._regions[region][sl].tobytes()

    def write(self, addr: int, data: bytes, ctx: AccessContext = AccessContext.AP) -> None:
        region, sl = self._slice(addr, nbytes=len(data))
        if region is Region.RC1_MAILBOX and ctx is not AccessContext.RC1:
            self.partition_fault_log.append(
                {"addr": addr, "bytes": len(data), "ctx": ctx.value, "kind": "BYPASS_ATTEMPT"}
            )
            raise HardPartitionFault(
                f"{ctx.value} context cannot write RC1_MAILBOX at 0x{addr:08x} — hard partition"
            )
        if region is Region.WEIGHT_REGION and self._weights_sealed:
            raise HardPartitionFault("WEIGHT_REGION is sealed read-only at runtime")
        self._regions[region][sl] = np.frombuffer(data, dtype=np.uint8)

    # --- DMA ------------------------------------------------------------
    def dma(self, src: int, dst: int, nbytes: int, ctx: AccessContext = AccessContext.AP) -> int:
        """Copy bytes src->dst; bumps the monotonic sequence counter.

        Returns the sequence number assigned to this DMA.
        """
        data = self.read(src, nbytes, ctx=ctx)
        self.write(dst, data, ctx=ctx)
        self.monotonic_sequence_counter += 1
        return self.monotonic_sequence_counter

    # --- typed tensor views (AP region) ---------------------------------
    def store_array(self, addr: int, arr: np.ndarray, ctx: AccessContext = AccessContext.AP) -> None:
        self.write(addr, np.ascontiguousarray(arr).tobytes(), ctx=ctx)

    def load_array(self, addr: int, shape: tuple[int, ...], dtype: np.dtype,
                   ctx: AccessContext = AccessContext.AP) -> np.ndarray:
        dtype = np.dtype(dtype)
        nbytes = int(np.prod(shape)) * dtype.itemsize
        buf = self.read(addr, nbytes, ctx=ctx)
        return np.frombuffer(buf, dtype=dtype).reshape(shape).copy()

    # --- time -----------------------------------------------------------
    @property
    def hardware_timestamp(self) -> int:
        """Cycle count. Deterministic; never wall-clock."""
        return self.cycle_count
