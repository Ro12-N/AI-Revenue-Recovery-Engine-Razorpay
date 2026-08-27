import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any

@dataclass
class DecisionBounds:
    max_retries: Optional[int] = None
    window: Optional[str] = None
    max_attempts: Optional[int] = None
    max_discount_pct: int = 0
    escalate_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class DecisionResult:
    chosen_intervention: str
    bounds: DecisionBounds
    decision_reasoning: str
    stopping_rule_triggered: Optional[str] = None
    channel: str = "none"


class DecisionEngine:
    """
    Stage 3: Pure Policy Table & Stopping Rules.
    Zero LLM calls.
    Evaluates stopping rules first per customer, then applies the strict deterministic policy table.
    """

    POLICY_TABLE = {
        "insufficient_funds": {
            "intervention": "retry_48h",
            "bounds": DecisionBounds(max_retries=2, window="48h", max_discount_pct=0),
            "channel": "sms",
            "reason": "Card declined for insufficient funds. Scheduled bounded 48h retry window with max 2 retries.",
        },
        "risk_decline": {
            "intervention": "escalate_review",
            "bounds": DecisionBounds(escalate_only=True, max_discount_pct=0),
            "channel": "none",
            "reason": "Payment blocked by risk/fraud filter. Escalate to fraud ops team; automated outreach prohibited.",
        },
        "expired_card": {
            "intervention": "request_update",
            "bounds": DecisionBounds(max_attempts=1, max_discount_pct=0),
            "channel": "email",
            "reason": "Card expired. Requesting customer payment method update via single bounded email notification.",
        },
        "bank_timeout": {
            "intervention": "retry_immediate",
            "bounds": DecisionBounds(max_retries=1, max_discount_pct=0),
            "channel": "in_app",
            "reason": "Transient gateway/bank timeout. Triggering single immediate in-app retry.",
        },
    }

    def __init__(self):
        # Track customer action counts within the batch
        self.customer_acted_count: Dict[str, int] = {}

    def reset_batch(self):
        self.customer_acted_count.clear()

    def decide(
        self,
        customer_id: str,
        do_not_contact: bool,
        diagnosed_cause: str,
        confidence: float,
        amount: float,
        event_type: str = "payment_event"
    ) -> DecisionResult:
        """
        Evaluates customer stopping rules first, then policy table rules.
        """
        # --- 1. FIRST-CLASS STOPPING RULES ---

        # Stopping Rule A: Customer explicit opt-out / DNC
        if do_not_contact:
            return DecisionResult(
                chosen_intervention="no_action",
                bounds=DecisionBounds(max_discount_pct=0),
                decision_reasoning="Customer has do_not_contact flag enabled. All automated recovery suppressed.",
                stopping_rule_triggered="do_not_contact = true",
                channel="none"
            )

        # Stopping Rule B: Max 2 acted-upon events per customer in the batch
        current_acted = self.customer_acted_count.get(customer_id, 0)
        if current_acted >= 2:
            return DecisionResult(
                chosen_intervention="no_action",
                bounds=DecisionBounds(max_discount_pct=0),
                decision_reasoning=f"Customer already has {current_acted} acted-upon recovery events in this batch. Policy strictly limits contact to 2 attempts.",
                stopping_rule_triggered="max 2 attempts per customer",
                channel="none"
            )

        # --- 2. DETERMINISTIC POLICY LOOKUP ---
        cause = diagnosed_cause.lower().strip()

        # Known deterministic causes
        if cause in self.POLICY_TABLE:
            rule = self.POLICY_TABLE[cause]
            # Increment acted count
            self.customer_acted_count[customer_id] = current_acted + 1
            return DecisionResult(
                chosen_intervention=rule["intervention"],
                bounds=rule["bounds"],
                decision_reasoning=rule["reason"],
                stopping_rule_triggered=None,
                channel=rule["channel"]
            )

        # Ambiguous causes with confidence / amount thresholds
        if cause == "otp_friction" and confidence >= 0.55:
            self.customer_acted_count[customer_id] = current_acted + 1
            return DecisionResult(
                chosen_intervention="resend_otp_simplified",
                bounds=DecisionBounds(max_attempts=1, max_discount_pct=0),
                decision_reasoning=f"OTP friction detected (conf {confidence:.2f} >= 0.55). Triggering single simplified OTP resend via SMS.",
                stopping_rule_triggered=None,
                channel="sms"
            )

        if cause == "price_shock" and confidence >= 0.55:
            if amount > 2000.0:
                self.customer_acted_count[customer_id] = current_acted + 1
                return DecisionResult(
                    chosen_intervention="discount_offer",
                    bounds=DecisionBounds(max_discount_pct=5, window="24h"),
                    decision_reasoning=f"Price shock detected on high cart value ₹{amount:.2f} (> ₹2000, conf {confidence:.2f}). Authorizing bounded 5% discount offer valid 24h.",
                    stopping_rule_triggered=None,
                    channel="whatsapp"
                )
            else:
                self.customer_acted_count[customer_id] = current_acted + 1
                return DecisionResult(
                    chosen_intervention="reminder_only",
                    bounds=DecisionBounds(max_discount_pct=0),
                    decision_reasoning=f"Price shock detected on cart value ₹{amount:.2f} (<= ₹2000, conf {confidence:.2f}). Policy forbids discount for <= ₹2000; sending reminder only.",
                    stopping_rule_triggered=None,
                    channel="whatsapp"
                )

        if cause == "trust_hesitation" and confidence >= 0.55:
            self.customer_acted_count[customer_id] = current_acted + 1
            return DecisionResult(
                chosen_intervention="trust_signal_message",
                bounds=DecisionBounds(max_discount_pct=0),
                decision_reasoning=f"Trust hesitation detected (conf {confidence:.2f} >= 0.55). Sending Razorpay trust & security guarantee message with 0% discount.",
                stopping_rule_triggered=None,
                channel="whatsapp"
            )

        if cause == "technical_error" and confidence >= 0.50:
            self.customer_acted_count[customer_id] = current_acted + 1
            return DecisionResult(
                chosen_intervention="retry_prompt",
                bounds=DecisionBounds(max_attempts=1, max_discount_pct=0),
                decision_reasoning=f"Technical error detected during session (conf {confidence:.2f} >= 0.50). Prompting customer to retry transaction.",
                stopping_rule_triggered=None,
                channel="in_app"
            )

        if cause == "comparison_shopping" and confidence >= 0.55:
            self.customer_acted_count[customer_id] = current_acted + 1
            return DecisionResult(
                chosen_intervention="reminder_urgency",
                bounds=DecisionBounds(max_discount_pct=0),
                decision_reasoning=f"Comparison shopping detected (conf {confidence:.2f} >= 0.55). Sending stock urgency reminder without discount.",
                stopping_rule_triggered=None,
                channel="whatsapp"
            )

        # Fallback / Low confidence
        return DecisionResult(
            chosen_intervention="no_action",
            bounds=DecisionBounds(max_discount_pct=0),
            decision_reasoning=f"Cause '{cause}' with confidence {confidence:.2f} did not meet policy threshold for automated action. Logging for observation.",
            stopping_rule_triggered=None,
            channel="none"
        )
