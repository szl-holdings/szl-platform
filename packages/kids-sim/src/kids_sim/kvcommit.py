"""KIDS v0.1 KV-cache per-block Merkle commitment.

The KV cache is a block table of pages, each page = 16 tokens x head_dim
float32 values. Every block gets a leaf digest:

    leaf = sha3_256(DOMAIN_KV || block_bytes)

Blocks form a binary Merkle tree (odd leaves promoted unchanged — the
v0.1 frozen rule). KV_COMMIT returns the root. Inclusion proofs are
generate/verify; tampering with one token embedding changes the leaf,
changes the root, and fails the proof.

This is verifiable inference at the datapath: the root commits the model
to exactly the tokens it attended over.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from .memory import PAGE_TOKENS

DOMAIN_KV: bytes = b"SZL-KIDS-KV-V1"


def leaf_digest(block_bytes: bytes) -> bytes:
    return hashlib.sha3_256(DOMAIN_KV + block_bytes).digest()


def _parent(a: bytes, b: bytes) -> bytes:
    return hashlib.sha3_256(DOMAIN_KV + a + b).digest()


def merkle_root(leaves: list[bytes]) -> bytes:
    """Binary Merkle root; odd leaf promoted unchanged (frozen v0.1 rule)."""
    if not leaves:
        return hashlib.sha3_256(DOMAIN_KV + b"EMPTY").digest()
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(_parent(level[i], level[i + 1]))
            else:
                nxt.append(level[i])  # promote odd leaf
        level = nxt
    return level[0]


@dataclass(frozen=True)
class Block:
    block_id: int
    data: np.ndarray  # shape (PAGE_TOKENS, head_dim) float32, zero-padded

    @property
    def digest(self) -> bytes:
        return leaf_digest(np.ascontiguousarray(self.data, dtype=np.float32).tobytes())


class KVBlockTable:
    """Block-table managed KV cache with per-block commitment."""

    def __init__(self, head_dim: int):
        if head_dim <= 0:
            raise ValueError("head_dim must be > 0")
        self.head_dim = head_dim
        self._blocks: dict[int, np.ndarray] = {}
        self._used: dict[int, int] = {}

    def append_tokens(self, block_id: int, tokens: np.ndarray) -> None:
        """Append token embeddings (n_tokens, head_dim) to a block page.

        Tokens are zero-padded to the 16-token page; the digest commits to
        the full padded page so padding is unambiguous.
        """
        t = np.ascontiguousarray(tokens, dtype=np.float32)
        if t.ndim == 1:
            t = t.reshape(1, -1)
        if t.shape[1] != self.head_dim:
            raise ValueError(f"token head_dim {t.shape[1]} != {self.head_dim}")
        page = self._blocks.get(block_id)
        if page is None:
            page = np.zeros((PAGE_TOKENS, self.head_dim), dtype=np.float32)
            self._blocks[block_id] = page
        # Occupancy tracked by an explicit count (a token may be all-zero).
        used = self._used.get(block_id, 0)
        if used + t.shape[0] > PAGE_TOKENS:
            raise ValueError(f"block {block_id} page full ({PAGE_TOKENS} tokens)")
        page[used : used + t.shape[0]] = t
        self._used[block_id] = used + t.shape[0]

    def block_ids(self) -> list[int]:
        return sorted(self._blocks)

    def block_digest(self, block_id: int) -> bytes:
        return leaf_digest(np.ascontiguousarray(self._blocks[block_id], dtype=np.float32).tobytes())

    def leaves(self) -> list[bytes]:
        return [self.block_digest(b) for b in self.block_ids()]

    def commit(self) -> bytes:
        """KV_COMMIT: Merkle root over all block leaves in block-id order."""
        return merkle_root(self.leaves())

    # --- inclusion proofs ------------------------------------------------
    def generate_proof(self, block_id: int) -> list[tuple[str, bytes]]:
        """Sibling path from leaf to root. Each step: ('L'|'R', sibling)."""
        ids = self.block_ids()
        if block_id not in self._blocks:
            raise KeyError(f"unknown block {block_id}")
        idx = ids.index(block_id)
        level = self.leaves()
        proof: list[tuple[str, bytes]] = []
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    if i == idx:
                        proof.append(("R", level[i + 1]))
                    elif i + 1 == idx:
                        proof.append(("L", level[i]))
                    nxt.append(_parent(level[i], level[i + 1]))
                else:
                    if i == idx:
                        pass  # promoted: no sibling
                    nxt.append(level[i])
            idx //= 2
            level = nxt
        return proof

    @staticmethod
    def verify_proof(block_bytes: bytes, proof: list[tuple[str, bytes]], root: bytes) -> bool:
        digest = leaf_digest(block_bytes)
        for side, sib in proof:
            digest = _parent(digest, sib) if side == "R" else _parent(sib, digest)
        return digest == root

    def block_bytes(self, block_id: int) -> bytes:
        return np.ascontiguousarray(self._blocks[block_id], dtype=np.float32).tobytes()
