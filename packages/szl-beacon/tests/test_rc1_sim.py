"""RC1 governance-boundary simulation tests: RC1-01..04 and envelope rules."""

from __future__ import annotations

import pytest
from szl_beacon import log as eventlog
from szl_beacon.rc1_sim import (
    RC1,
    ActionEnvelope,
    BypassAttempt,
    EnvelopError,
    RC1Decision,
    build_valid_envelope,
    run_acceptance_fixtures,
)

NOW = 1_800_000_000
KEY = b"test-hmac-key"


@pytest.fixture()
def rc1(tmp_path):
    return RC1(tmp_path / "rc1log", target_id="RC1-TEST", hmac_key=KEY, now=NOW)


class TestEnvelope:
    def test_valid_envelope_constructs(self, rc1) -> None:
        ActionEnvelope(build_valid_envelope(rc1, nonce=1, expiry=NOW + 60))

    def test_missing_field_refused(self, rc1) -> None:
        fields = build_valid_envelope(rc1, nonce=1, expiry=NOW + 60)
        del fields["nonce"]
        with pytest.raises(EnvelopError):
            ActionEnvelope(fields)

    def test_wrong_schema_version_refused(self, rc1) -> None:
        fields = build_valid_envelope(rc1, nonce=1, expiry=NOW + 60)
        fields["schema_version"] = 99
        with pytest.raises(EnvelopError):
            ActionEnvelope(fields)

    def test_unknown_command_refused(self, rc1) -> None:
        fields = build_valid_envelope(rc1, nonce=1, expiry=NOW + 60, command="SELF_DESTRUCT")
        with pytest.raises(EnvelopError):
            ActionEnvelope(fields)


class TestReceive:
    def test_valid_envelope_accepted(self, rc1) -> None:
        result = rc1.receive(build_valid_envelope(rc1, nonce=1, expiry=NOW + 60))
        assert result["decision"] == RC1Decision.ACCEPTED.value
        assert result["output_energized"] is True
        assert result["simulation"] is True

    def test_expired_rejected_nothing_energized(self, rc1) -> None:
        result = rc1.receive(build_valid_envelope(rc1, nonce=1, expiry=NOW - 1))
        assert result["decision"] == RC1Decision.REJECTED.value
        assert result["output_energized"] is False
        assert rc1.output_energized is False

    def test_replay_rejected(self, rc1) -> None:
        envelope = build_valid_envelope(rc1, nonce=1, expiry=NOW + 60)
        assert rc1.receive(dict(envelope))["decision"] == RC1Decision.ACCEPTED.value
        result = rc1.receive(dict(envelope))
        assert result["decision"] == RC1Decision.REJECTED.value
        assert "replay" in result["reason"]

    def test_bad_auth_tag_rejected(self, rc1) -> None:
        envelope = build_valid_envelope(rc1, nonce=1, expiry=NOW + 60)
        envelope["auth_tag"] = "0" * 64
        result = rc1.receive(envelope)
        assert result["decision"] == RC1Decision.REJECTED.value

    def test_wrong_target_rejected(self, rc1) -> None:
        envelope = build_valid_envelope(rc1, nonce=1, expiry=NOW + 60)
        envelope["target_id"] = "OTHER-DEVICE"
        result = rc1.receive(envelope)
        assert result["decision"] == RC1Decision.REJECTED.value

    def test_malformed_envelope_rejected_not_exception(self, rc1) -> None:
        result = rc1.receive({"schema_version": "nonsense"})
        assert result["decision"] == RC1Decision.REJECTED.value
        result = rc1.receive("not-even-a-dict")
        assert result["decision"] == RC1Decision.REJECTED.value

    def test_anti_replay_persists_across_instances(self, tmp_path) -> None:
        """Nonce ceiling survives a simulated reset (log is protected NV)."""

        logdir = tmp_path / "shared"
        first = RC1(logdir, target_id="RC1-TEST", hmac_key=KEY, now=NOW)
        assert first.receive(build_valid_envelope(first, nonce=5, expiry=NOW + 60))[
            "decision"
        ] == RC1Decision.ACCEPTED.value
        # Simulated reset: brand-new instance over the same log.
        second = RC1(logdir, target_id="RC1-TEST", hmac_key=KEY, now=NOW)
        assert second.receive(build_valid_envelope(second, nonce=5, expiry=NOW + 60))[
            "decision"
        ] == RC1Decision.REJECTED.value
        # But a fresh nonce passes.
        assert second.receive(build_valid_envelope(second, nonce=6, expiry=NOW + 60))[
            "decision"
        ] == RC1Decision.ACCEPTED.value

    def test_every_decision_receipted_on_chain(self, tmp_path) -> None:
        logdir = tmp_path / "rc1log"
        rc1 = RC1(logdir, target_id="RC1-TEST", hmac_key=KEY, now=NOW)
        rc1.receive(build_valid_envelope(rc1, nonce=1, expiry=NOW + 60))
        rc1.receive({"bogus": True})
        report = eventlog.verify(logdir)
        assert report.ok, report.to_dict()
        events = eventlog.read_events(logdir)
        assert all(e["payload"]["type"] == "RC1_DECISION" for e in events)
        assert all(e["payload"]["simulation"] for e in events)


class TestBypass:
    def test_bypass_attempt_raises_and_energizes_nothing(self, rc1) -> None:
        rc1.output_energized = True  # pretend output was on
        with pytest.raises(BypassAttempt):
            rc1.bypass_output()
        assert rc1.output_energized is False

    def test_bypass_is_receipted(self, tmp_path) -> None:
        logdir = tmp_path / "rc1log"
        rc1 = RC1(logdir, target_id="RC1-TEST", hmac_key=KEY, now=NOW)
        with pytest.raises(BypassAttempt):
            rc1.bypass_output(origin="application_processor")
        events = eventlog.read_events(logdir)
        assert events[-1]["payload"]["decision"] == RC1Decision.BYPASS_REFUSED.value


class TestSafeState:
    def test_safe_state_event_explicit(self, tmp_path) -> None:
        logdir = tmp_path / "rc1log"
        rc1 = RC1(logdir, target_id="RC1-TEST", hmac_key=KEY, now=NOW)
        rc1.receive(build_valid_envelope(rc1, nonce=1, expiry=NOW + 60))
        assert rc1.output_energized is True
        event = rc1.safe_state_event(reason="watchdog expiry (simulated)")
        assert rc1.output_energized is False
        assert rc1.safe_state is True
        assert event["state_to"] == "SAFE_STATE"
        assert event["payload"]["simulation"] is True
        assert eventlog.verify(logdir).ok


class TestAcceptanceFixtures:
    def test_rc1_01_through_04_all_pass(self, tmp_path) -> None:
        results = run_acceptance_fixtures(tmp_path / "fixtures")
        assert len(results) == 4
        by_name = {r["test"]: r for r in results}
        for name in ("RC1-01", "RC1-02", "RC1-03", "RC1-04"):
            assert by_name[name]["passed"], by_name[name]

    def test_fixture_chain_verifies(self, tmp_path) -> None:
        logdir = tmp_path / "fixtures"
        run_acceptance_fixtures(logdir)
        assert eventlog.verify(logdir).ok
