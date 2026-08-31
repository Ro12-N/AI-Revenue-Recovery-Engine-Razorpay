import pytest
from app.pipeline.decision_engine import DecisionEngine, DecisionBounds

ALL_CAUSES = [
    "insufficient_funds",
    "risk_decline",
    "expired_card",
    "bank_timeout",
    "otp_friction",
    "price_shock",
    "trust_hesitation",
    "technical_error",
    "comparison_shopping",
    "unknown",
    "random_unmapped_cause"
]

CONFIDENCE_LEVELS = [0.1, 0.4, 0.5, 0.55, 0.7, 0.95, 1.0]
AMOUNTS = [100.0, 1999.99, 2000.0, 2000.01, 5000.0, 50000.0]


class TestDecisionEngine:
    
    @pytest.mark.parametrize("cause", ALL_CAUSES)
    @pytest.mark.parametrize("confidence", CONFIDENCE_LEVELS)
    @pytest.mark.parametrize("amount", AMOUNTS)
    def test_bounds_max_discount_never_exceeds_policy_limit(self, cause, confidence, amount):
        """
        Proves that for EVERY possible combination of (cause, confidence, amount),
        the resulting bounds.max_discount_pct NEVER exceeds 5%.
        """
        engine = DecisionEngine()
        result = engine.decide(
            customer_id="cust_test",
            do_not_contact=False,
            diagnosed_cause=cause,
            confidence=confidence,
            amount=amount
        )
        assert result.bounds.max_discount_pct <= 5, (
            f"Policy violation: {cause} (conf={confidence}, amt={amount}) yielded {result.bounds.max_discount_pct}% discount"
        )
        assert result.bounds.max_discount_pct >= 0
        assert result.decision_reasoning is not None and len(result.decision_reasoning) > 0

    def test_stopping_rule_prevents_third_action_per_customer(self):
        """
        Proves the stopping rule strictly prevents a 3rd action for a customer
        who already has 2 acted-upon events within the same batch.
        """
        engine = DecisionEngine()
        cust_id = "cust_repeat_offender"

        # 1st Action: Should succeed
        res1 = engine.decide(cust_id, False, "insufficient_funds", 0.98, 1500.0)
        assert res1.chosen_intervention == "retry_48h"
        assert res1.stopping_rule_triggered is None

        # 2nd Action: Should succeed
        res2 = engine.decide(cust_id, False, "price_shock", 0.80, 3500.0)
        assert res2.chosen_intervention == "discount_offer"
        assert res2.stopping_rule_triggered is None

        # 3rd Action: MUST be suppressed by stopping rule
        res3 = engine.decide(cust_id, False, "otp_friction", 0.90, 5000.0)
        assert res3.chosen_intervention == "no_action"
        assert res3.stopping_rule_triggered == "max 2 attempts per customer"
        assert "limits contact to 2 attempts" in res3.decision_reasoning

        # 4th Action: MUST also be suppressed
        res4 = engine.decide(cust_id, False, "bank_timeout", 0.98, 1000.0)
        assert res4.chosen_intervention == "no_action"
        assert res4.stopping_rule_triggered == "max 2 attempts per customer"

    def test_do_not_contact_always_results_in_no_action(self):
        """
        Proves do_not_contact=True ALWAYS yields no_action regardless of cause, confidence, or amount.
        """
        engine = DecisionEngine()
        for cause in ALL_CAUSES:
            for conf in [0.2, 0.6, 0.99]:
                res = engine.decide(
                    customer_id=f"cust_dnc_{cause}",
                    do_not_contact=True,
                    diagnosed_cause=cause,
                    confidence=conf,
                    amount=8000.0
                )
                assert res.chosen_intervention == "no_action"
                assert res.stopping_rule_triggered == "do_not_contact = true"
                assert res.bounds.max_discount_pct == 0
                assert res.channel == "none"

    def test_price_shock_threshold_enforcement(self):
        """
        Proves price shock gives discount_offer only if amount > 2000 and confidence >= 0.55.
        Below or equal to 2000 gives reminder_only with 0% discount.
        """
        engine = DecisionEngine()
        
        # High value (> 2000)
        res_high = engine.decide("cust_1", False, "price_shock", 0.60, 2500.0)
        assert res_high.chosen_intervention == "discount_offer"
        assert res_high.bounds.max_discount_pct == 5
        assert res_high.bounds.window == "24h"

        # Low value (<= 2000)
        res_low = engine.decide("cust_2", False, "price_shock", 0.60, 1500.0)
        assert res_low.chosen_intervention == "reminder_only"
        assert res_low.bounds.max_discount_pct == 0

        # Exact boundary 2000
        res_edge = engine.decide("cust_3", False, "price_shock", 0.60, 2000.0)
        assert res_edge.chosen_intervention == "reminder_only"
        assert res_edge.bounds.max_discount_pct == 0

        # Low confidence (< 0.55) -> no_action
        res_low_conf = engine.decide("cust_4", False, "price_shock", 0.50, 4000.0)
        assert res_low_conf.chosen_intervention == "no_action"

    def test_risk_decline_escalation_only(self):
        """
        Proves risk_decline only escalates internally and never assigns a customer contact channel.
        """
        engine = DecisionEngine()
        res = engine.decide("cust_fraud", False, "risk_decline", 0.98, 10000.0)
        assert res.chosen_intervention == "escalate_review"
        assert res.bounds.escalate_only is True
        assert res.bounds.max_discount_pct == 0
        assert res.channel == "none"
