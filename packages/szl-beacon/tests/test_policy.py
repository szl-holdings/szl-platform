"""Policy engine tests: Rev A scope enforcement, receipted refusals."""

from __future__ import annotations

from szl_beacon.policy import (
    ActionClass,
    classify_action,
    evaluate_action_class,
    rev_a_scope_check,
)


class TestRevAScope:
    def test_translation_allowed(self) -> None:
        decision = rev_a_scope_check({"proposal_type": "translation"})
        assert decision["decision"] == "ALLOWED"

    def test_summarization_allowed(self) -> None:
        decision = rev_a_scope_check({"proposal_type": "summarization"})
        assert decision["decision"] == "ALLOWED"

    def test_triage_assistance_allowed(self) -> None:
        decision = rev_a_scope_check({"proposal_type": "triage_assistance"})
        assert decision["decision"] == "ALLOWED"

    def test_matching_proposal_allowed(self) -> None:
        decision = rev_a_scope_check({"proposal_type": "matching_proposal"})
        assert decision["decision"] == "ALLOWED"

    def test_diagnosis_refused(self) -> None:
        decision = rev_a_scope_check({"proposal_type": "diagnosis"})
        assert decision["decision"] == "REFUSED"
        assert decision["category"] == "diagnosis"
        assert "Rev A" in decision["reason"]

    def test_diagnosis_refused_from_free_text(self) -> None:
        decision = rev_a_scope_check({"text": "Can you diagnose what illness I have?"})
        assert decision["decision"] == "REFUSED"
        assert decision["category"] == "diagnosis"

    def test_prescription_refused(self) -> None:
        decision = rev_a_scope_check({"text": "What medication dosage should I take?"})
        assert decision["decision"] == "REFUSED"
        assert decision["category"] == "prescription"

    def test_scarce_lifecritical_allocation_refused(self) -> None:
        decision = rev_a_scope_check(
            {"proposal_type": "scarce_lifecritical_allocation"}
        )
        assert decision["decision"] == "REFUSED"
        assert "life-critical" in decision["reason"]

    def test_lifesafety_control_refused_from_text(self) -> None:
        decision = rev_a_scope_check({"text": "Energize the ventilator pump now"})
        assert decision["decision"] == "REFUSED"
        assert decision["category"] == "lifesafety_control"

    def test_empty_request_refused_fail_closed(self) -> None:
        decision = rev_a_scope_check({})
        assert decision["decision"] == "REFUSED"

    def test_refusal_carries_policy_version(self) -> None:
        decision = rev_a_scope_check({"proposal_type": "prescription"})
        assert decision["policy_version"].startswith("rev-a")


class TestClassifyAction:
    def test_declared_class_respected(self) -> None:
        assert classify_action({"action_class": "OBSERVE"}) is ActionClass.OBSERVE
        assert classify_action({"action_class": "notify"}) is ActionClass.NOTIFY

    def test_undeclared_defaults_consequential(self) -> None:
        assert classify_action({}) is ActionClass.CONSEQUENTIAL

    def test_unknown_declared_class_fails_closed_to_consequential(self) -> None:
        assert classify_action({"action_class": "FIRE_ZE_MISSILES"}) is (
            ActionClass.CONSEQUENTIAL
        )


class TestEvaluateActionClass:
    def test_observe_needs_no_authorization(self) -> None:
        gate = evaluate_action_class(ActionClass.OBSERVE, None)
        assert gate["ok"]

    def test_notify_needs_no_authorization(self) -> None:
        assert evaluate_action_class(ActionClass.NOTIFY, None)["ok"]

    def test_consequential_needs_authorization(self) -> None:
        gate = evaluate_action_class(ActionClass.CONSEQUENTIAL, None)
        assert not gate["ok"]
        assert "explicit authorization" in gate["reason"]

    def test_consequential_incomplete_auth_refused(self) -> None:
        gate = evaluate_action_class(ActionClass.CONSEQUENTIAL, {"authorizer_id": "op"})
        assert not gate["ok"]

    def test_consequential_full_auth_passes(self) -> None:
        gate = evaluate_action_class(
            ActionClass.CONSEQUENTIAL,
            {"authorizer_id": "op-1", "authorization_digest": "ab" * 32},
        )
        assert gate["ok"]


class TestRefusalReceipted:
    """Policy refusals land on the chain as failure events (fail closed)."""

    def test_diagnosis_request_via_transaction_refused_and_receipted(
        self, tx, logdir
    ) -> None:
        import pytest
        from conftest import human, machine
        from szl_beacon import log as eventlog
        from szl_beacon.labels import Label
        from szl_beacon.protocol import State, TransitionRefused

        tx.open_intent(
            actor=human("resident-1"),
            summary="medical question",
            request={"proposal_type": "diagnosis"},
            label=Label.COMMUNITY_REPORT,
        )
        tx.advance(State.EVIDENCE, actor=human("resident-1"), label=Label.COMMUNITY_REPORT)
        # The machine layer checks scope before proposing: refused.
        decision = rev_a_scope_check({"proposal_type": "diagnosis"})
        assert decision["decision"] == "REFUSED"
        with pytest.raises(TransitionRefused):
            tx.advance(
                State.PROPOSAL,
                actor=machine("a11oy-1"),
                label=Label.VERIFIED_SOURCE,  # machine + authority label = violation
            )
        events = eventlog.read_events(logdir)
        assert events[-1]["payload"]["type"] == "TRANSITION_REFUSED"
        assert eventlog.verify(logdir).ok
