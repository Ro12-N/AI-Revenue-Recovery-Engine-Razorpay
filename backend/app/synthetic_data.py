import random
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from app.models import Customer, PaymentEvent, CheckoutSession

DECLINE_CODES = ["INSUFFICIENT_FUNDS", "RISK_BLOCK", "CARD_EXPIRED", "GATEWAY_TIMEOUT"]
PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
DEVICES = ["mobile_android", "mobile_ios", "desktop_chrome", "desktop_safari"]
CHECKOUT_STAGES = ["landed", "cart", "payment_page", "otp", "abandoned", "completed"]

def generate_synthetic_batch(
    seed: int = 42,
    event_count: int = 70
) -> Tuple[List[Customer], List[PaymentEvent], List[CheckoutSession]]:
    """
    Deterministically generates synthetic customers, payment events, and checkout sessions
    based on the provided integer seed.
    """
    rng = random.Random(seed)
    
    # 1. Generate customer pool (~30% of event_count, min 15)
    num_customers = max(15, int(event_count * 0.35))
    customers: List[Customer] = []
    
    for i in range(num_customers):
        cust_id = f"cust_{seed}_{i+1:03d}"
        avg_ov = round(rng.uniform(500.0, 8500.0), 2)
        # ~10% are marked do_not_contact
        dnc = (rng.random() < 0.10)
        # ~45% repeat customers
        repeat = (rng.random() < 0.45)
        customers.append(
            Customer(
                id=cust_id,
                avg_order_value=avg_ov,
                do_not_contact=dnc,
                repeat_customer=repeat
            )
        )
    
    # Target counts: ~60% payments, ~40% checkouts
    num_payments = int(event_count * 0.60)
    num_checkouts = event_count - num_payments
    
    now = datetime.utcnow()
    
    # 2. Generate Payment Events
    payment_events: List[PaymentEvent] = []
    for i in range(num_payments):
        pay_id = f"pay_{seed}_{i+1:04d}"
        customer = rng.choice(customers)
        # realistic amounts, varying between ₹250 and ₹18,000
        amount = round(rng.choice([
            rng.uniform(250.0, 1900.0),   # under 2k
            rng.uniform(2100.0, 6500.0),  # mid range
            rng.uniform(7000.0, 18000.0)  # high ticket
        ]), 2)
        
        method = rng.choice(PAYMENT_METHODS)
        is_sub = (rng.random() < 0.25)
        
        # ~42% failure rate
        is_failed = (rng.random() < 0.42)
        if is_failed:
            # 70% get a known decline code, 30% degraded with no code
            if rng.random() < 0.70:
                status = "failed"
                decline_code = rng.choice(DECLINE_CODES)
            else:
                status = "degraded"
                decline_code = None
        else:
            status = "success"
            decline_code = None
            
        created_at = now - timedelta(minutes=rng.randint(5, 1440))
        
        payment_events.append(
            PaymentEvent(
                id=pay_id,
                customer_id=customer.id,
                amount=amount,
                currency="INR",
                method=method,
                status=status,
                decline_code=decline_code,
                is_subscription=is_sub,
                created_at=created_at
            )
        )
        
    # 3. Generate Checkout Sessions
    checkout_sessions: List[CheckoutSession] = []
    for i in range(num_checkouts):
        cs_id = f"cs_{seed}_{i+1:04d}"
        customer = rng.choice(customers)
        cart_value = round(rng.choice([
            rng.uniform(350.0, 1850.0),   # under 2k
            rng.uniform(2200.0, 8500.0),  # over 2k
            rng.uniform(9000.0, 24000.0)  # premium
        ]), 2)
        
        device = rng.choice(DEVICES)
        
        # Funnel stage weights: ~40% completed, ~60% incomplete/abandoned
        # Incomplete distribution: otp (20%), payment_page (20%), cart (10%), landed (5%), abandoned (5%)
        stage_roll = rng.random()
        if stage_roll < 0.40:
            stage = "completed"
            time_on_page = rng.randint(45, 200)
        elif stage_roll < 0.60:
            stage = "otp"
            time_on_page = rng.randint(80, 320)
        elif stage_roll < 0.80:
            stage = "payment_page"
            time_on_page = rng.randint(60, 450)
        elif stage_roll < 0.90:
            stage = "cart"
            time_on_page = rng.randint(25, 180)
        elif stage_roll < 0.95:
            stage = "abandoned"
            time_on_page = rng.randint(15, 90)
        else:
            stage = "landed"
            time_on_page = rng.randint(5, 45)
            
        created_at = now - timedelta(minutes=rng.randint(5, 1440))
        
        checkout_sessions.append(
            CheckoutSession(
                id=cs_id,
                customer_id=customer.id,
                cart_value=cart_value,
                funnel_stage_reached=stage,
                device=device,
                time_on_page_seconds=time_on_page,
                created_at=created_at
            )
        )
        
    return customers, payment_events, checkout_sessions
