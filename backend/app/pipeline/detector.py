from dataclasses import dataclass
from typing import List, Dict, Union, Optional
from datetime import datetime
from app.models import Customer, PaymentEvent, CheckoutSession
from app.synthetic_data import generate_synthetic_batch

@dataclass
class AtRiskEvent:
    event_id: str
    event_type: str  # "payment_event" | "checkout_session"
    customer_id: str
    amount: float
    detected_at: datetime
    raw_status: str
    decline_code: Optional[str] = None
    funnel_stage: Optional[str] = None
    device: Optional[str] = None
    time_on_page_seconds: Optional[int] = None
    is_subscription: bool = False
    payment_method: Optional[str] = None
    
    # Attached customer metadata
    customer_avg_order_value: float = 0.0
    customer_do_not_contact: bool = False
    customer_repeat: bool = False


class Detector:
    """
    Stage 1: Pure rule-based detection.
    Zero LLM calls.
    Filters raw generated synthetic data down to the at-risk set.
    """
    
    @staticmethod
    def detect_at_risk(
        customers: List[Customer],
        payments: List[PaymentEvent],
        checkouts: List[CheckoutSession]
    ) -> List[AtRiskEvent]:
        customer_map: Dict[str, Customer] = {c.id: c for c in customers}
        at_risk: List[AtRiskEvent] = []
        
        # 1. Filter Payment Events: failed or degraded
        for p in payments:
            if p.status in ("failed", "degraded"):
                cust = customer_map.get(p.customer_id)
                at_risk.append(
                    AtRiskEvent(
                        event_id=p.id,
                        event_type="payment_event",
                        customer_id=p.customer_id,
                        amount=p.amount,
                        detected_at=p.created_at,
                        raw_status=p.status,
                        decline_code=p.decline_code,
                        is_subscription=p.is_subscription,
                        payment_method=p.method,
                        customer_avg_order_value=cust.avg_order_value if cust else 0.0,
                        customer_do_not_contact=cust.do_not_contact if cust else False,
                        customer_repeat=cust.repeat_customer if cust else False
                    )
                )
                
        # 2. Filter Checkout Sessions: anything not completed (otp, payment_page, cart, landed, abandoned)
        for cs in checkouts:
            if cs.funnel_stage_reached != "completed":
                cust = customer_map.get(cs.customer_id)
                at_risk.append(
                    AtRiskEvent(
                        event_id=cs.id,
                        event_type="checkout_session",
                        customer_id=cs.customer_id,
                        amount=cs.cart_value,
                        detected_at=cs.created_at,
                        raw_status=cs.funnel_stage_reached,
                        funnel_stage=cs.funnel_stage_reached,
                        device=cs.device,
                        time_on_page_seconds=cs.time_on_page_seconds,
                        customer_avg_order_value=cust.avg_order_value if cust else 0.0,
                        customer_do_not_contact=cust.do_not_contact if cust else False,
                        customer_repeat=cust.repeat_customer if cust else False
                    )
                )
                
        # Sort chronologically by detected_at
        at_risk.sort(key=lambda x: x.detected_at)
        return at_risk
