import pytest
from app.pipeline.decision_engine import DecisionBounds
from app.pipeline.executor import check_message_guardrails, Executor

class TestGuardrail:

    def test_violating_message_is_rejected_and_fallback_substituted(self):
        """
        Feeds a drafted message with 50% discount against a 5% max bound.
        Asserts rejection (guardrail_ok=False) and safe fallback substitution.
        """
        violating_msg = "Super offer! Complete your pending checkout now to get a huge 50% discount!"
        bounds = DecisionBounds(max_discount_pct=5, window="24h")

        result = check_message_guardrails(
            message=violating_msg,
            bounds=bounds,
            intervention="discount_offer",
            language="English"
        )

        assert result.ok is False
        assert "Bound exceeded" in result.reason
        assert "50" in result.reason
        assert result.sent_message != violating_msg
        assert "5% off" in result.sent_message

    def test_unauthorized_discount_when_bound_is_zero_is_rejected(self):
        """
        Feeds a drafted message with 10% discount against a 0% max bound (e.g. reminder_only or trust_signal).
        Asserts rejection and substitution.
        """
        violating_msg = "We noticed you left! Here is a 10% discount to complete your payment."
        bounds = DecisionBounds(max_discount_pct=0)

        result = check_message_guardrails(
            message=violating_msg,
            bounds=bounds,
            intervention="reminder_only",
            language="English"
        )

        assert result.ok is False
        assert "Policy violation" in result.reason
        assert "0%" in result.reason
        assert result.sent_message != violating_msg
        assert "10%" not in result.sent_message

    def test_compliant_message_passes_unchanged(self):
        """
        Feeds compliant messages and asserts guardrail_ok=True with exact text preserved.
        """
        # Compliant 5% message within 5% bound
        compliant_5pct = "Complete your order within 24h to receive 5% off your cart total."
        bounds_5pct = DecisionBounds(max_discount_pct=5, window="24h")
        res1 = check_message_guardrails(compliant_5pct, bounds_5pct, "discount_offer", "English")
        assert res1.ok is True
        assert res1.reason is None
        assert res1.sent_message == compliant_5pct

        # Compliant 0% reminder message
        compliant_reminder = "Your cart items are reserved for you. Tap here to complete your checkout."
        bounds_0pct = DecisionBounds(max_discount_pct=0)
        res2 = check_message_guardrails(compliant_reminder, bounds_0pct, "reminder_only", "English")
        assert res2.ok is True
        assert res2.reason is None
        assert res2.sent_message == compliant_reminder

    def test_adversarial_self_test_always_intercepts(self):
        """
        Verifies the permanent adversarial self-test structure and execution.
        """
        self_test_res = Executor.run_guardrail_self_test()
        assert self_test_res["guardrail_ok"] is False
        assert "PASSED" in self_test_res["status"]
        assert self_test_res["fallback_substituted"] is not None
        assert "50%" not in self_test_res["fallback_substituted"]
