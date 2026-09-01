# AI Revenue Recovery Engine — Razorpay Track 03

An autonomous, closed-loop revenue recovery system for Razorpay merchants. Revenue leaks at discrete, high-friction moments: a debit card declines due to temporary insufficient funds, a customer abandons checkout due to price shock on shipping/taxes, or a mobile payment session stalls at the OTP verification step. Instead of treating these failures as dead ends or blasting users with arbitrary, unconstrained marketing emails, this engine detects revenue-losing events, diagnoses the root cause using bounded AI, evaluates strict deterministic policy tables & stopping rules, drafts empathetic recovery copy under financial constraints, and validates every message through a deterministic regex guardrail before sending — providing a transparent, auditable ledger with net revenue accounting.

---

## AI-vs-Rules Architecture Disclosure

To ensure zero financial hallucination and strict regulatory compliance, LLMs are used in **exactly two bounded places**. All amounts, retry windows, discount bounds, stopping rules, and guardrail validations are deterministic code.

| Pipeline Component | Engine Type | Architectural Justification |
| :--- | :--- | :--- |
| **01. Event Detector** | `RULES` | High-throughput, deterministic filtering of raw payment declines and checkout drop-off sessions without LLM latency. |
| **02. Explicit Decline Mapping** | `RULES` | Bank decline codes (`INSUFFICIENT_FUNDS`, `RISK_BLOCK`, `CARD_EXPIRED`, `GATEWAY_TIMEOUT`) map directly to recovery causes with 100% precision. |
| **03. Ambiguous Drop-off Diagnoser** | `AI (Claude 3.5)` | Multi-variable behavioral inference across dwell times, device types, funnel stages, and cart values using strict JSON tool schemas. |
| **04. Stopping Rules & Contact Policy** | `RULES` | First-class customer opt-out (`do_not_contact=true`) and batch contact caps (max 2 attempts per customer) enforced in code prior to cause action. |
| **05. Policy & Bounds Engine** | `RULES` | Pure policy lookup table assigns bounded actions (e.g. max discount <= 5%, 48h hold windows); LLM never touches financial amounts. |
| **06. Recovery Message Copywriting** | `AI (Claude 3.5)` | Generates empathetic, brand-safe recovery copy in English & Hinglish, strictly bounded by upstream policy constraints. |
| **07. Message Guardrail Validator** | `RULES` | Pure regex scanner (`\d+%`) catches and rejects out-of-bounds discount promises, automatically substituting a certified safe template. |
| **08. Outcome & Net ROI Simulator** | `RULES` | Seeded probabilistic conversion model deducting per-channel messaging costs (SMS ₹0.50, WhatsApp ₹2.00, Email ₹0.10) to report real net recovered revenue. |

---

## 5-Stage Pipeline Architecture

```
                                  [ RAW EVENT STREAM ]
                        (Payments: ~60% | Checkout Funnels: ~40%)
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: DETECTOR (Pure Rules)                                                    │
│ Filters raw event stream down to at-risk set (failed, degraded, abandoned)        │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: DIAGNOSER (Rules + Constrained Claude 3.5 Tool-Use)                     │
│ ├─ Explicit Decline Code? ──► [Direct Rule Mapping: conf=0.98, source=rules]     │
│ └─ Ambiguous Drop-off?    ──► [Claude Tool: classify_causes with strict schema]  │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: DECISION ENGINE (Pure Policy Table + Stopping Rules)                    │
│ ├─ Check: do_not_contact == True? ──────────► [NO ACTION / Logged]               │
│ ├─ Check: Customer Action Count >= 2? ─────► [NO ACTION / Max Attempts Cap]     │
│ └─ Cause-to-Policy Table: Assign intervention + hard bounds (max discount <= 5%) │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: EXECUTOR (Claude 3.5 Drafting + Deterministic Regex Guardrail)          │
│ ├─ Drafts SMS / WhatsApp copy in English or Hinglish under 280 chars              │
│ ├─ Regex Guardrail scans message for \d+% against policy discount bound          │
│ └─ Out-of-bounds? ────────► [REJECT & SUBSTITUTE CERTIFIED SAFE FALLBACK]        │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: OUTCOMES & NET ROI (Seeded Probabilistic Simulator)                     │
│ ├─ Evaluates conversion: Recovered vs Promise-to-Pay vs No-Response              │
│ ├─ Deducts delivery fees (SMS=₹0.50, WhatsApp=₹2.00, Email=₹0.10)                │
│ └─ Writes full audit ledger row + computes Counterfactual ("Without Agent" loss)  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- (Optional) Anthropic API Key (if not provided, the engine runs in seamless deterministic heuristic mode for 100% offline reproducibility)

### 1. Clone & Install
```bash
git clone <repo-url>
cd RazorPay
pip install -r backend/requirements.txt
```

### 2. Configure Environment (Optional)
```bash
cp .env.example .env
# Edit .env and insert your ANTHROPIC_API_KEY if desired
```

### 3. Run the Full Application Server
```bash
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## Docker Compose Setup

Run both backend and frontend in a single isolated container:

```bash
docker-compose up --build
```
Access the application at `http://localhost:8000`.

---

## Verification & Test Suite

The test suite validates core safety invariants and policy boundaries:

```bash
python -m pytest backend/tests -v
```

### What the 473 Tests Prove:
1. **`test_decision_engine.py`**:
   - **Discount Bounds Invariant**: Proves that for *every* possible permutation of `(cause, confidence, amount)`, `bounds.max_discount_pct` **never exceeds 5%**.
   - **Stopping Rule Invariant**: Proves that a customer with 2 acted-upon events in a batch is strictly prevented from receiving a 3rd message.
   - **Opt-Out Invariant**: Proves `do_not_contact=True` *always* produces `no_action` with 0% discount and 0 outreach.
2. **`test_guardrail.py`**:
   - **Adversarial Interception**: Proves messages exceeding authorized discount caps (e.g. 50% discount against 5% cap) are rejected (`guardrail_ok=False`) and replaced with safe fallback templates.
   - **Compliance Passthrough**: Proves compliant messages pass with unmodified text.
   - **Live Self-Test**: Proves the permanent adversarial self-test correctly executes on every batch run.
3. **`test_detector.py`**:
   - **Reproducibility**: Proves identical integer seeds generate bit-for-bit identical event streams and at-risk detections.
   - **Event Mix**: Proves target 60/40 payment/checkout distributions.
4. **`test_pipeline_integration.py`**:
   - **End-to-End Invariant**: Proves `net_recovered <= gross_recovered` holds for every individual action and aggregate batch summary.
   - **Counterfactual Invariant**: Proves `agent_off_total_lost == total_at_risk`.

---

## What Is Not Built (Scope & Production Transition)

This project operates on **seeded synthetic data** and a **probabilistic outcome conversion model** to allow judges to execute reproducible, deterministic batches with zero payment credentials required.

In a live production environment:
1. **Trigger Ingestion**: The `Detector` would be hooked directly to Razorpay Webhooks (`payment.failed`, `order.paid`, `checkout.session.abandoned`).
2. **Communication Gateways**: The `Executor` would route sanitized messages to production Twilio / WhatsApp Business Cloud API / Gupshup webhooks.
3. **Outcome Tracking**: Instead of simulated probabilistic conversion, the database would listen for subsequent `order.paid` webhooks tagged with the recovery campaign ID.

Because the **Decision Engine**, **Guardrail Regex Validator**, and **Audit Ledger Data Model** are decoupled from the synthetic layer, they can be deployed directly into production without altering core recovery logic.
