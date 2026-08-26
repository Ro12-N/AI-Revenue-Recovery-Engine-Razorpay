from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlmodel import SQLModel, Field
from pydantic import BaseModel

# Database Models

class Customer(SQLModel, table=True):
    __tablename__ = "customers"
    
    id: str = Field(primary_key=True)
    avg_order_value: float = Field(default=0.0)
    do_not_contact: bool = Field(default=False)
    repeat_customer: bool = Field(default=False)


class PaymentEvent(SQLModel, table=True):
    __tablename__ = "payment_events"
    
    id: str = Field(primary_key=True)
    customer_id: str = Field(foreign_key="customers.id", index=True)
    amount: float
    currency: str = Field(default="INR")
    method: str = Field(default="card")  # card, upi, netbanking, wallet
    status: str  # success, failed, degraded
    decline_code: Optional[str] = Field(default=None)  # INSUFFICIENT_FUNDS, RISK_BLOCK, CARD_EXPIRED, GATEWAY_TIMEOUT
    is_subscription: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CheckoutSession(SQLModel, table=True):
    __tablename__ = "checkout_sessions"
    
    id: str = Field(primary_key=True)
    customer_id: str = Field(foreign_key="customers.id", index=True)
    cart_value: float
    funnel_stage_reached: str  # landed, cart, payment_page, otp, abandoned, completed
    device: str = Field(default="mobile_android")
    time_on_page_seconds: int = Field(default=30)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RecoveryAction(SQLModel, table=True):
    __tablename__ = "recovery_actions"
    
    id: str = Field(primary_key=True)
    batch_id: str = Field(index=True)
    trigger_event_id: str = Field(index=True)
    trigger_type: str  # payment_event, checkout_session
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Stage 2 - Diagnoser
    diagnosed_cause: str
    diagnosis_confidence: float
    diagnosis_reasoning: str
    diagnosis_source: str  # rules, llm, llm-fallback
    
    # Stage 3 - Decision Engine
    chosen_intervention: str
    intervention_bounds: str  # JSON string
    decision_reasoning: str
    stopping_rule_triggered: Optional[str] = None
    
    # Stage 4 - Executor
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    channel: str = Field(default="none")  # sms, whatsapp, email, in_app, none
    drafted_message: Optional[str] = None
    sent_message: Optional[str] = None
    guardrail_ok: bool = Field(default=True)
    guardrail_reason: Optional[str] = None
    
    # Stage 5 - Outcomes
    outcome: str  # recovered, promise_to_pay, no_response, escalated, no_action, stopped, rejected
    amount_recovered: float = Field(default=0.0)
    intervention_cost: float = Field(default=0.0)
    net_recovered: float = Field(default=0.0)
    follow_up_date: Optional[str] = None


class BatchRun(SQLModel, table=True):
    __tablename__ = "batch_runs"
    
    id: str = Field(primary_key=True)
    seed: int
    event_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    total_at_risk: float = Field(default=0.0)
    total_recovered_gross: float = Field(default=0.0)
    total_recovered_net: float = Field(default=0.0)
    agent_off_total_lost: float = Field(default=0.0)
    at_risk_count: int = Field(default=0)
    recovered_count: int = Field(default=0)
    escalated_count: int = Field(default=0)
    stopped_count: int = Field(default=0)
    status: str = Field(default="completed")


# Pydantic Request / Response schemas

class BatchRunRequest(BaseModel):
    seed: int = 42
    event_count: int = 70


class EventTraceResponse(BaseModel):
    action: RecoveryAction
    customer: Optional[Customer] = None
    payment_event: Optional[PaymentEvent] = None
    checkout_session: Optional[CheckoutSession] = None


class BatchRunSummaryResponse(BaseModel):
    batch: BatchRun
    actions: List[RecoveryAction]
    self_test: Dict[str, Any]
    summary_text: str
