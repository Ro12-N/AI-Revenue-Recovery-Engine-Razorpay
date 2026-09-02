# Build Prompt — AI Revenue Recovery Engine

Paste everything below into Antigravity as the project brief. It's written as one complete spec so the agent can work through it end-to-end without needing to ask you to fill gaps — where a decision was arbitrary, it's stated explicitly so the agent doesn't stall on it.

---

## PROJECT BRIEF

You are building **AI Revenue Recovery Engine**, a submission for Razorpay's "Track 03 — AI Revenue Recovery" hackathon evaluation. The evaluation rubric is: **problem taste, build quality, AI judgment, failure recovery**. Every architectural choice below exists to make one of those four legible to a judge who opens the repo and runs the app. Build to that bar, not just to "it works."

### What this system does

It is a closed-loop agent that watches revenue-losing events (failed/degraded payments, checkout drop-off), diagnoses why they happened, decides a bounded recovery action, executes it, and measures what it actually recovered — with a full audit trail. It runs against **synthetic data only** (no real payment integration required), on a reproducible seeded batch.

### Non-negotiable design constraint (read this twice)

The LLM is used in **exactly two places**:
1. **Diagnosis of ambiguous causes** — classifying why an event happened when there's no clean signal (e.g. checkout drop-off with only behavioral data), against a fixed taxonomy, with a confidence score.
2. **Drafting recovery message copy** — writing the actual customer-facing text, constrained by bounds set upstream.

**Everything else is deterministic code.** Specifically: the detector, the decision engine (which intervention, how much discount, how many retries, when to stop contacting someone), and the guardrail check on drafted messages must be plain rule-based logic — never LLM output. This is the single most heavily scored design decision in the whole project. Do not let the model touch money amounts, retry counts, or contact frequency under any framing.

---

## Architecture

```
backend/
  app/
    main.py                 # FastAPI app, CORS, route registration
    models.py                # SQLModel/pydantic schemas: PaymentEvent, CheckoutEvent, RecoveryAction, BatchRun
    db.py                    # SQLite engine + session
    synthetic_data.py        # seeded generator for payments + checkout sessions + customers
    pipeline/
      detector.py            # stage 1 — pure rules, filters raw events to at-risk
      diagnoser.py           # stage 2 — deterministic lookup + LLM call for ambiguous cases
      decision_engine.py     # stage 3 — pure policy table, stopping rules, bounds
      executor.py            # stage 4 — LLM message drafting + deterministic guardrail check
      outcomes.py            # stage 5 — seeded probabilistic outcome simulation
      pipeline.py             # orchestrates all 5 stages, writes full audit trail to DB
    llm/
      client.py               # thin wrapper around Anthropic SDK, both call sites route through here
      prompts.py               # prompt templates for diagnosis and message drafting, kept separate from logic
    routers/
      batch.py                # POST /batch/run, GET /batch/{id}, GET /batch/{id}/events/{event_id}
  tests/
    test_decision_engine.py   # proves bounds are never exceeded, stopping rules actually stop
    test_guardrail.py         # proves the guardrail catches out-of-bounds drafts
    test_detector.py
    test_pipeline_integration.py   # full run against a mocked LLM client, asserts shape of output
  requirements.txt
  README.md

frontend/
  (vanilla JS + the existing design system, OR React+Tailwind reimplementation — agent's choice,
   but must preserve the design tokens and structure described below)
  index.html
  src/
    api.js                   # fetch wrappers to the backend
    render/                  # stat strip, pipeline rail, ledger table, trace expansion, guardrail card
    styles/tokens.css         # the design tokens below, as CSS variables

README.md                    # root-level, architecture explanation for judges — see "README" section
.env.example
docker-compose.yml            # optional but nice: one command to run backend+frontend together
```

Use **Python 3.11+, FastAPI, SQLModel (or SQLAlchemy + pydantic), SQLite, pytest, the official `anthropic` Python SDK**. Frontend: plain JS + fetch, or React + Tailwind if the agent judges that faster to build well — either is acceptable, but the visual system below is not optional.

---

## Data model

Three tables — keep them boring and correct:

**`customers`**: `id, avg_order_value, do_not_contact (bool), repeat_customer (bool)`

**`payment_events`**: `id, customer_id, amount, currency, method, status (success/failed/degraded), decline_code (nullable), is_subscription (bool), created_at`

**`checkout_sessions`**: `id, customer_id, cart_value, funnel_stage_reached (landed/cart/payment_page/otp/abandoned/completed), device, time_on_page_seconds, created_at`

**`recovery_actions`** (this table *is* the audit trail — get it right):
`id, batch_id, trigger_event_id, trigger_type, detected_at, diagnosed_cause, diagnosis_confidence, diagnosis_reasoning, diagnosis_source (rules|llm|llm-fallback), chosen_intervention, intervention_bounds (json), decision_reasoning, stopping_rule_triggered (nullable), executed_at, channel, drafted_message, sent_message, guardrail_ok (bool), guardrail_reason (nullable), outcome, amount_recovered, intervention_cost, net_recovered, follow_up_date (nullable)`

**`batch_runs`**: `id, seed, event_count, created_at, total_at_risk, total_recovered_gross, total_recovered_net, agent_off_total_lost (for the counterfactual — see below)`

---

## Pipeline stages — exact logic

### Stage 1 — Detector (`detector.py`, zero LLM calls)
Generate synthetic data via a seeded RNG (Python's `random.Random(seed)`, so batches are reproducible). ~60% payment events, ~40% checkout events, out of a total count the caller specifies (default 70, configurable). Payments: ~42% chance of failure; of those, ~70% get a known `decline_code` from `{INSUFFICIENT_FUNDS, RISK_BLOCK, CARD_EXPIRED, GATEWAY_TIMEOUT}`, the rest are `degraded` with no code. Checkout: weighted funnel stages so ~60% never complete. Filter to `status in (failed, degraded, abandoned)` — that's the at-risk set that flows downstream.

### Stage 2 — Diagnoser (`diagnoser.py`, LLM call #1)
- If `decline_code` is present, map it directly (`INSUFFICIENT_FUNDS → insufficient_funds`, `RISK_BLOCK → risk_decline`, `CARD_EXPIRED → expired_card`, `GATEWAY_TIMEOUT → bank_timeout`) — confidence 0.98, `diagnosis_source = "rules"`. No LLM call.
- Otherwise, batch the ambiguous events (chunks of ~12) into a single Claude call per chunk. **Use tool-use / structured output** (a `classify_cause` tool with a strict JSON schema: `id`, `cause` (enum of `otp_friction, price_shock, trust_hesitation, technical_error, comparison_shopping, unknown`), `confidence` (0-1), `reasoning` (string, short)) rather than parsing free text — this is a meaningful build-quality upgrade over naive prompt-and-parse.
- On any API error or malformed response for an event: default to `cause=unknown, confidence=0.3`, log the reason. Never let a parsing failure silently drop an event or crash the batch.

### Stage 3 — Decision engine (`decision_engine.py`, zero LLM calls — this is the file the pytest suite in the "Non-negotiable" section is really about)
Pure policy table. Implement stopping rules as a first-class check, evaluated before cause-based logic, per customer, within the batch:
- `do_not_contact = true` → `no_action`, log reason, stop.
- Customer already has 2+ acted-upon events this batch → `no_action`, `stopping_rule_triggered = "max 2 attempts per customer"`.
Then map cause → intervention + hard bounds:
| cause | condition | intervention | bounds |
|---|---|---|---|
| insufficient_funds | — | retry_48h | max_retries=2, window=48h |
| risk_decline | — | escalate_review | escalate only, no automated contact |
| expired_card | — | request_update | max_attempts=1 |
| bank_timeout | — | retry_immediate | max_retries=1 |
| otp_friction | conf ≥ 0.55 | resend_otp_simplified | max_attempts=1 |
| price_shock | conf ≥ 0.55, amount > ₹2000 | discount_offer | max_discount_pct=5, window=24h |
| price_shock | conf ≥ 0.55, amount ≤ ₹2000 | reminder_only | max_discount_pct=0 |
| trust_hesitation | conf ≥ 0.55 | trust_signal_message | max_discount_pct=0 |
| technical_error | conf ≥ 0.5 | retry_prompt | max_attempts=1 |
| comparison_shopping | conf ≥ 0.55 | reminder_urgency | max_discount_pct=0 |
| anything else / low confidence | — | no_action (logged) | — |

Every decision writes a `decision_reasoning` string — this field is not optional, it's the core of your "explainable" story.

### Stage 4 — Executor (`executor.py`, LLM call #2 + deterministic guardrail)
For every event with an actionable intervention, batch a Claude call (chunks of ~10) to draft the actual message: SMS/WhatsApp-style, under 300 chars, English or Hinglish (alternate/randomize per event, deterministically from the seed), constrained by the bounds computed in stage 3 (pass the bound explicitly into the prompt as a hard constraint, e.g. "you may mention a discount of at most 5%, valid 24h" or "you must not mention any discount").

After drafting, run a **separate, deterministic guardrail function** — regex-scan the message for `\d+%` and compare against the bound. If it violates the bound (mentions a discount when none is allowed, or exceeds the max %), reject it, log `guardrail_ok=false` + reason, and substitute a safe fallback template. This must be pure code, not another LLM call.

**Include a permanent guardrail self-test**: a hardcoded adversarial example (a fabricated over-bound draft, e.g. "50% off!" against a 5% bound) run through the same guardrail function on every batch, displayed separately from live metrics, so a passing failure-recovery demo doesn't depend on the live LLM happening to misbehave.

### Stage 5 — Outcomes (`outcomes.py`, zero LLM calls)
Seeded probabilistic simulation per intervention type (same probability table as the earlier artifact — retry_48h: 45% recovered/20% promise-to-pay/35% no-response, discount_offer: 30/15/55, etc. — the agent can carry these forward or adjust slightly, but they must be declared in code, not invented ad hoc at runtime, so a reviewer can see the assumptions).

Compute **net recovered**, not just gross: subtract a per-channel intervention cost (`sms=₹0.50, whatsapp-sim=₹2, email=₹0.10, in-app=₹0`) from gross recovered amount per event. Report both, but headline the net figure.

**Counterfactual**: alongside the real batch, compute what total loss would look like with `agent_off` (i.e., sum of all at-risk amounts with zero recovery) and store it on the `batch_runs` row, so the frontend can show "with agent" vs "without agent" side by side.

---

## API

- `POST /batch/run` — body `{seed: int, event_count: int}`. Runs the full pipeline synchronously (or as a background task with polling if the agent judges the LLM calls will make this too slow for a single request — agent's call, but keep total wall-clock under ~30s for a default-size batch). Returns the full batch summary + all `recovery_actions` rows.
- `GET /batch/{batch_id}` — batch summary + stats.
- `GET /batch/{batch_id}/events/{event_id}` — single event's full trace, for the expand-on-click UI.
- `GET /batch/{batch_id}/export` — optional CSV/JSON export of the audit log, for judges who want to inspect it outside the UI.

---

## Frontend — design system (carry this forward exactly, don't reinterpret it)

This has already been designed — implement it, don't redesign it. It intentionally avoids the generic "cream background + terracotta accent" and "black background + neon accent" AI-demo clichés in favor of a **ledger/audit aesthetic** — the visual language of a financial ledger crossed with an audit trail.

**Palette** (as CSS variables):
```css
--bg:#EDF0E7; --panel:#FFFFFF; --ink:#16211B; --ink-soft:#5B685E; --ink-faint:#8B978C;
--money:#1F7A5C; --money-soft:#E3F0E9; --amber:#AD7530; --amber-soft:#F4EADA;
--red:#A6443C; --red-soft:#F5E3E0; --slate:#4C5A71; --slate-soft:#E6EAF1;
--hairline:#D5D9CE; --hairline-strong:#B9C0B2;
```

**Type**: display headline in **Fraunces** (serif, used sparingly — the hero line only), body in **Inter**, all data/ids/numbers/audit-trail text in **IBM Plex Mono**. The mono-for-data convention should hold everywhere — event IDs, confidence scores, ₹ amounts, timestamps.

**Signature elements** (keep these, they're what makes it memorable, not generic):
- **Outcome "stamps"** — small rotated (-3deg) bordered mono labels (RECOVERED / ESCALATED / STOPPED / REJECTED etc.), like ink rubber stamps on a ledger page.
- **Pipeline rail** — a horizontal dotted-line flow diagram showing counts moving through Detected → Diagnosed → Decided → Executed → Outcome.
- **Expandable trace rows** — click any event in the ledger table to reveal its full 5-stage trace inline, left-bordered in the money-green accent.
- **AI-vs-rules disclosure table** — a collapsible table naming every pipeline component and tagging it `AI` or `RULES`, with one sentence of justification each. This directly answers the AI-judgment rubric line and should stay prominent, not buried.
- **Guardrail self-test card** — always visible, red-tinted panel showing the adversarial example and its rejection.

**New for this build** (additions since the last version, both should get real visual weight, not be afterthoughts):
- **Counterfactual comparison** — a two-column "With agent / Without agent" block near the top of the stats strip, showing the ₹ delta prominently. This is the single highest-impact addition — don't undersell it visually.
- **Batch playback / ticker** — on a fresh run, animate events resolving over ~15-20 seconds (stagger via timeouts or an animation queue) with the recovered-₹ counter ticking upward live, plus a "skip to results" control for impatient viewers.
- **Hinglish voice** — for events with a Hinglish drafted message, add a small speaker-icon button that plays it via the browser's native `SpeechSynthesis` API (`hi-IN` or `en-IN` voice if available, fallback to default). No backend cost, purely client-side.
- **Plain-English summary tab** — one short paragraph, no jargon, sitting above the audit table, explaining what happened in this batch for a non-technical reader/judge.

Keep the layout otherwise as-is: eyebrow label → serif hero line → controls (seed input, event count, run button) → stats strip → pipeline rail with AI-vs-rules disclosure → guardrail self-test → filters → ledger table with expandable traces → exceptions panel → footer note.

---

## Tests (do not skip this — it's disproportionately high-value for "build quality")

`tests/test_decision_engine.py` must include, at minimum:
- A property-style or parametrized test asserting that for every possible `(cause, confidence, amount)` combination the engine can reach, the resulting `bounds.max_discount_pct` never exceeds the policy table's stated maximum (5%).
- A test proving the stopping rule actually prevents a 3rd action for a customer who already has 2 acted-upon events in the same batch.
- A test proving `do_not_contact=true` always results in `no_action` regardless of cause/confidence.

`tests/test_guardrail.py` must include:
- A test feeding the guardrail function a message that violates its bound and asserting it's rejected with a fallback substituted.
- A test feeding a compliant message and asserting it passes unchanged.

`tests/test_pipeline_integration.py`: run the full pipeline with the Anthropic client mocked (don't hit the real API in CI), assert the output batch has the expected shape (every event has a diagnosis, a decision, an outcome) and that `net_recovered <= gross_recovered` always holds.

---

## README (root level — write this like a judge is going to read it first)

Structure:
1. One-paragraph plain-English description of what the system does and why (revenue leaks in discrete moments — a payment degrades, a checkout abandons, a subscription fails — this closes the loop from detection to recovered money).
2. The AI-vs-rules table (same one as in the UI) — reproduced in the README so it's visible before anyone runs anything.
3. Architecture diagram (ASCII is fine) matching the pipeline stages above.
4. How to run it locally (`docker-compose up`, or the manual `pip install -r requirements.txt && uvicorn ...` + frontend serve steps).
5. How to run the tests, and what they prove.
6. One paragraph on what's *not* built (be honest — e.g. "this uses synthetic data and a simulated outcome model rather than live Razorpay webhooks; the pipeline architecture is designed to swap in real webhook triggers and real channel-send integrations without changing the decision engine or guardrail logic").

---

## Build order (for the agent to sequence its own work)

1. `synthetic_data.py` + `models.py` + `db.py` — get data generation and storage right first, everything depends on it.
2. `detector.py` + `decision_engine.py` — pure logic, no LLM, get these fully unit-tested before touching the API.
3. `llm/client.py` + `diagnoser.py` — wire in the real Anthropic SDK call with structured output, test against a handful of hand-written ambiguous cases before running a full batch.
4. `executor.py` + guardrail — message drafting + the deterministic check + the self-test.
5. `outcomes.py` — seeded simulation, net-recovered calculation, counterfactual.
6. `pipeline.py` + `routers/batch.py` — wire the stages together end to end, get one full batch running through the API before touching the frontend at all.
7. Frontend: stats strip + pipeline rail + ledger table + trace expansion first (the core legibility of the demo), then layer on counterfactual, ticker/playback, Hinglish voice, plain-English summary.
8. Full pytest suite, README, docker-compose.
9. Reserve real time at the end for: running the full thing fresh, checking the numbers are sane and reproducible, and rehearsing what gets shown live.

Do not build the receivables chaser, mandate retry sequencer, or promise-to-pay tracker as separate systems — those are folded into this engine's existing intervention set (a promise-to-pay outcome is already a first-class outcome type in stage 5). Depth on one coherent loop beats breadth across disconnected sub-features.
