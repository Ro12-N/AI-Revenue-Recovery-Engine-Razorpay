import random
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

CHANNEL_COSTS: Dict[str, float] = {
    "sms": 0.50,
    "whatsapp": 2.00,
    "email": 0.10,
    "in_app": 0.0,
    "none": 0.0,
}

# Explicit outcome probability distribution table: (recovered, promise_to_pay, no_response)
PROBABILITY_TABLE = {
    "retry_48h": {"recovered": 0.45, "promise_to_pay": 0.20, "no_response": 0.35},
    "request_update": {"recovered": 0.40, "promise_to_pay": 0.15, "no_response": 0.45},
    "retry_immediate": {"recovered": 0.65, "promise_to_pay": 0.00, "no_response": 0.35},
    "resend_otp_simplified": {"recovered": 0.55, "promise_to_pay": 0.00, "no_response": 0.45},
    "discount_offer": {"recovered": 0.35, "promise_to_pay": 0.15, "no_response": 0.50},
    "reminder_only": {"recovered": 0.25, "promise_to_pay": 0.20, "no_response": 0.55},
    "trust_signal_message": {"recovered": 0.30, "promise_to_pay": 0.15, "no_response": 0.55},
    "retry_prompt": {"recovered": 0.45, "promise_to_pay": 0.00, "no_response": 0.55},
    "reminder_urgency": {"recovered": 0.35, "promise_to_pay": 0.15, "no_response": 0.50},
}

@dataclass
class OutcomeResult:
    outcome: str  # recovered, promise_to_pay, no_response, escalated, no_action, stopped, rejected
    amount_recovered: float
    intervention_cost: float
    net_recovered: float
    follow_up_date: Optional[str] = None


class OutcomeSimulator:
    """
    Stage 5: Deterministic / Seeded Probabilistic Outcome Simulator.
    Zero LLM calls.
    Computes gross and net recovered figures subtracting explicit channel intervention costs.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def simulate(
        self,
        intervention: str,
        channel: str,
        amount: float,
        stopping_rule_triggered: Optional[str] = None,
        guardrail_ok: bool = True
    ) -> OutcomeResult:
        # Determine cost based on channel contacted
        cost = CHANNEL_COSTS.get(channel, 0.0)

        # If guardrail failed and couldn't even send fallback (handled in executor), or rejected:
        if not guardrail_ok:
            return OutcomeResult(
                outcome="rejected",
                amount_recovered=0.0,
                intervention_cost=0.0,
                net_recovered=0.0,
                follow_up_date=None
            )

        # Stopping rules or no_action
        if stopping_rule_triggered:
            return OutcomeResult(
                outcome="stopped",
                amount_recovered=0.0,
                intervention_cost=0.0,
                net_recovered=0.0,
                follow_up_date=None
            )

        if intervention == "no_action":
            return OutcomeResult(
                outcome="no_action",
                amount_recovered=0.0,
                intervention_cost=0.0,
                net_recovered=0.0,
                follow_up_date=None
            )

        if intervention == "escalate_review":
            return OutcomeResult(
                outcome="escalated",
                amount_recovered=0.0,
                intervention_cost=0.0,
                net_recovered=0.0,
                follow_up_date=None
            )

        # For actionable interventions, sample from probability table
        dist = PROBABILITY_TABLE.get(
            intervention,
            {"recovered": 0.30, "promise_to_pay": 0.20, "no_response": 0.50}
        )

        roll = self.rng.random()
        p_rec = dist["recovered"]
        p_ptp = dist["promise_to_pay"]

        if roll < p_rec:
            # Recovered!
            # If discount was applied (e.g. 5% on discount_offer), compute recovered amount net of discount
            if intervention == "discount_offer":
                gross = round(amount * 0.95, 2)
            else:
                gross = round(amount, 2)
            
            net = round(gross - cost, 2)
            return OutcomeResult(
                outcome="recovered",
                amount_recovered=gross,
                intervention_cost=cost,
                net_recovered=net,
                follow_up_date=None
            )
        elif roll < (p_rec + p_ptp):
            # Promise to pay - schedule follow up in 48-72 hours
            follow_up = (datetime.utcnow() + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M UTC")
            net = round(0.0 - cost, 2)
            return OutcomeResult(
                outcome="promise_to_pay",
                amount_recovered=0.0,
                intervention_cost=cost,
                net_recovered=net,
                follow_up_date=follow_up
            )
        else:
            # No response
            net = round(0.0 - cost, 2)
            return OutcomeResult(
                outcome="no_response",
                amount_recovered=0.0,
                intervention_cost=cost,
                net_recovered=net,
                follow_up_date=None
            )
