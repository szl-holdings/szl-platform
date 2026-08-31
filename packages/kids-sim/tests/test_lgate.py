"""LGATE policy gate tests: allow/deny, 1-cycle charge, fail-closed state."""

import numpy as np

from kids_sim.engine import Engine
from kids_sim.isa import KvAppend
from kids_sim.lgate import Decision, LGate, PolicyRule
from kids_sim.rc1 import RC1Controller, compute_auth_tag

DEVICE = "KHIPU-X1-TEST"
KEY = b"\x01" * 32
POLICY = PolicyRule(allowed_opcodes=frozenset({"KV_APPEND", "KV_COMMIT"}),
                    bounds={"tokens": (1, 16)}, required_receipts=0)
_nonce = [0]


def make_engine(policy=POLICY):
    rc1 = RC1Controller(DEVICE, KEY, {policy.digest().hex() if policy else "x"})
    return Engine(head_dim=8, policy=policy, rc1=rc1)


def authorize(eng, command_type, policy_digest=None):
    _nonce[0] += 1
    env = {
        "schema_version": "1",
        "target_id": DEVICE,
        "command_type": command_type,
        "bounds": {},
        "nonce": _nonce[0],
        "expiry_cycle": 10**12,
        "policy_digest": policy_digest or POLICY.digest().hex(),
    }
    env["auth_tag"] = compute_auth_tag(env, KEY)
    eng.submit_envelope(0, env)
    from kids_sim.isa import Rc1Recv, Rc1Send

    eng.execute(Rc1Send(mailbox=0))
    eng.execute(Rc1Recv(mailbox=0))


def test_lgate_allow():
    gate = LGate(POLICY)
    v = gate.check({"op": "KV_APPEND", "block_id": 0, "tokens": 8}, receipt_count=0)
    assert v.decision is Decision.ALLOW
    assert v.cycles == 1  # single-cycle spec target


def test_lgate_deny_opcode_not_allowed():
    gate = LGate(POLICY)
    v = gate.check({"op": "DMA_STORE", "bytes": 4}, receipt_count=0)
    assert v.decision is Decision.DENY
    assert "allow-list" in v.reason


def test_lgate_deny_out_of_bounds():
    gate = LGate(POLICY)
    v = gate.check({"op": "KV_APPEND", "block_id": 0, "tokens": 64}, receipt_count=0)
    assert v.decision is Decision.DENY
    assert "outside bound" in v.reason


def test_lgate_required_receipts():
    gate = LGate(PolicyRule(allowed_opcodes=frozenset({"KV_COMMIT"}), required_receipts=3))
    assert gate.check({"op": "KV_COMMIT"}, receipt_count=2).decision is Decision.DENY
    assert gate.check({"op": "KV_COMMIT"}, receipt_count=3).decision is Decision.ALLOW


def test_lgate_deny_leaves_state_unchanged():
    eng = make_engine()
    authorize(eng, "KV_APPEND")
    tokens = np.ones((64, 8), np.float32)  # 64 > policy bound 16 -> LGATE DENY
    eng.push(tokens)
    kv_root_before = eng.kv.commit()
    depth_before = len(eng.stack)
    dma_before = eng.memory.monotonic_sequence_counter

    eng.execute(KvAppend(block_id=0, tokens=64))

    ev = eng.events[-1]
    assert ev["status"] == "DENIED" and "LGATE" in ev["detail"]
    # fail closed: architectural state unchanged (receipt log grows — it is the log)
    assert eng.kv.commit() == kv_root_before
    assert len(eng.stack) == depth_before  # tokens NOT consumed
    assert eng.memory.monotonic_sequence_counter == dma_before


def test_lgate_check_charges_exactly_one_cycle():
    eng = make_engine()
    c0 = eng.memory.cycle_count
    authorize(eng, "KV_APPEND")
    eng.push(np.ones((4, 8), np.float32))
    c1 = eng.memory.cycle_count
    eng.execute(KvAppend(block_id=0, tokens=4))
    # KV_APPEND charge = LGATE 1 cycle + tokens*head_dim stores
    assert eng.memory.cycle_count - c1 == 1 + 4 * 8
    assert c1 > c0  # RC1 path charged its envelope-validation cycles
