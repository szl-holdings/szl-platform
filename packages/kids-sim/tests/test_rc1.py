"""RC1 mailbox tests: RC1-01..04 analogues.

RC1-01 unauthorized: bad/missing auth => rejected, output not energized.
RC1-02 replay: a previously accepted nonce is never accepted again.
RC1-03 expiry: expired envelope rejected.
RC1-04 Linux bypass: AP cannot touch the mailbox outside the RC1 path.
"""

import numpy as np
import pytest

from kids_sim.engine import Engine
from kids_sim.isa import DmaStore, KvAppend, Rc1Recv, Rc1Send
from kids_sim.lgate import PolicyRule
from kids_sim.memory import REGION_MAP, AccessContext, HardPartitionFault, Region
from kids_sim.rc1 import RC1Controller, RC1Reject, compute_auth_tag

DEVICE = "KHIPU-X1-TEST"
KEY = b"\x02" * 32
POLICY = PolicyRule(allowed_opcodes=frozenset({"KV_APPEND", "KV_COMMIT", "DMA_STORE"}))
PDIG = POLICY.digest().hex()
RC1_BASE = REGION_MAP[Region.RC1_MAILBOX][0]
AP_BASE = REGION_MAP[Region.AP_REGION][0]


def envelope(**over):
    env = {
        "schema_version": "1",
        "target_id": DEVICE,
        "command_type": "KV_APPEND",
        "bounds": {},
        "nonce": 1,
        "expiry_cycle": 10**6,
        "policy_digest": PDIG,
    }
    env.update(over)
    env["auth_tag"] = compute_auth_tag(env, KEY)
    return env


def make_rc1():
    return RC1Controller(DEVICE, KEY, {PDIG})


class TestValidation:
    def test_valid_envelope_accepted(self):
        rc1 = make_rc1()
        rc1.send(0, envelope(), current_cycle=0)
        assert rc1.recv(0)["nonce"] == 1

    def test_rc1_02_replay_rejected(self):
        rc1 = make_rc1()
        rc1.send(0, envelope(nonce=5), current_cycle=0)
        with pytest.raises(RC1Reject, match="replayed"):
            rc1.send(0, envelope(nonce=5), current_cycle=1)  # same nonce again
        with pytest.raises(RC1Reject, match="replayed"):
            rc1.send(0, envelope(nonce=4), current_cycle=2)  # stale nonce

    def test_rc1_03_expiry_rejected(self):
        rc1 = make_rc1()
        with pytest.raises(RC1Reject, match="expired"):
            rc1.send(0, envelope(expiry_cycle=100), current_cycle=101)

    def test_malformed_envelope_rejected(self):
        rc1 = make_rc1()
        bad = envelope()
        del bad["nonce"]
        with pytest.raises(RC1Reject, match="malformed"):
            rc1.send(0, bad, current_cycle=0)
        with pytest.raises(RC1Reject, match="malformed"):
            rc1.send(0, {"schema_version": "1"}, current_cycle=0)
        with pytest.raises(RC1Reject, match="not an object"):
            rc1.send(0, "not-a-dict", current_cycle=0)

    def test_rc1_01_unauthorized_rejected(self):
        rc1 = make_rc1()
        env = envelope()
        env["auth_tag"] = "00" * 32  # forged tag
        with pytest.raises(RC1Reject, match="auth_tag"):
            rc1.send(0, env, current_cycle=0)
        with pytest.raises(RC1Reject, match="target_id"):
            rc1.send(0, envelope(target_id="OTHER-DEVICE"), current_cycle=0)
        with pytest.raises(RC1Reject, match="policy_digest"):
            rc1.send(0, envelope(policy_digest="ff" * 32), current_cycle=0)
        with pytest.raises(RC1Reject, match="schema_version"):
            rc1.send(0, envelope(schema_version="99"), current_cycle=0)

    def test_reject_log_records_failures(self):
        rc1 = make_rc1()
        for bad in ({"x": 1}, envelope(nonce=1, expiry_cycle=1)):
            try:
                rc1.send(0, bad, current_cycle=10**9)
            except RC1Reject:
                pass
        assert len(rc1.reject_log) == 2


class TestBypass:
    def test_rc1_04_ap_write_to_mailbox_raises(self):
        eng = Engine(head_dim=8, rc1=make_rc1(), policy=POLICY)
        with pytest.raises(HardPartitionFault):
            eng.memory.write(RC1_BASE, b"\xde\xad", ctx=AccessContext.AP)
        assert eng.memory.partition_fault_log[-1]["kind"] == "BYPASS_ATTEMPT"

    def test_rc1_04_dma_store_into_mailbox_logged_bypass(self):
        eng = Engine(head_dim=8, rc1=make_rc1(), policy=POLICY)
        # even WITH a valid RC1 token, the AP-context DMA cannot write the
        # hard partition — the partition is physical, not policy
        env = envelope(command_type="DMA_STORE")
        eng.submit_envelope(0, env)
        eng.execute(Rc1Send(mailbox=0))
        eng.execute(Rc1Recv(mailbox=0))
        eng.memory.write(AP_BASE, b"\x41" * 8)
        eng.execute(DmaStore(descriptor_id=0, src=AP_BASE, dst=RC1_BASE, bytes=8, seq=1))
        ev = eng.events[-1]
        assert ev["status"] == "BYPASS_ATTEMPT"
        assert eng.memory.read(RC1_BASE, 8, ctx=AccessContext.RC1) == b"\x00" * 8

    def test_privileged_op_without_rc1_token_denied(self):
        eng = Engine(head_dim=8, rc1=make_rc1(), policy=POLICY)
        eng.push(np.ones((4, 8), np.float32))
        eng.execute(KvAppend(block_id=0, tokens=4))
        assert eng.events[-1]["status"] == "DENIED"
        assert "no RC1 authorization" in eng.events[-1]["detail"]
        assert len(eng.stack) == 1  # state unchanged

    def test_one_token_authorizes_exactly_one_op(self):
        eng = Engine(head_dim=8, rc1=make_rc1(), policy=POLICY)
        eng.submit_envelope(0, envelope(nonce=1))
        eng.execute(Rc1Send(mailbox=0))
        eng.execute(Rc1Recv(mailbox=0))
        eng.push(np.ones((4, 8), np.float32))
        eng.execute(KvAppend(block_id=0, tokens=4))
        assert eng.events[-1]["status"] == "EXECUTED"
        eng.push(np.ones((4, 8), np.float32))
        eng.execute(KvAppend(block_id=1, tokens=4))  # token consumed -> deny
        assert eng.events[-1]["status"] == "DENIED"
