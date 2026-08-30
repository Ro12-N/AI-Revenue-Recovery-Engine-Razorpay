import uuid
from datetime import datetime
from typing import List, Dict, Any, Tuple
from sqlmodel import Session, select
from app.models import (
    Customer,
    PaymentEvent,
    CheckoutSession,
    RecoveryAction,
    BatchRun,
    BatchRunSummaryResponse
)
from app.synthetic_data import generate_synthetic_batch
from app.pipeline.detector import Detector
from app.pipeline.diagnoser import Diagnoser
from app.pipeline.decision_engine import DecisionEngine
from app.pipeline.executor import Executor
from app.pipeline.outcomes import OutcomeSimulator
from app.llm.client import LLMClient


class RevenueRecoveryPipeline:
    """
    Orchestrates the 5-stage closed-loop AI Revenue Recovery Pipeline:
    1. Detector (Rules)
    2. Diagnoser (Rules + LLM tool-use for ambiguous)
    3. Decision Engine (Pure Policy Table + Stopping Rules)
    4. Executor (LLM Drafting + Pure Regex Guardrail)
    5. Outcomes (Probabilistic Seeded Simulator + Net Channel Costs)
    """

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
        self.diagnoser = Diagnoser(self.llm_client)
        self.decision_engine = DecisionEngine()
        self.executor = Executor(self.llm_client)

    def run_batch(
        self,
        session: Session,
        seed: int = 42,
        event_count: int = 70
    ) -> BatchRunSummaryResponse:
        batch_id = f"batch_{seed}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # 0. Generate synthetic data
        customers, payments, checkouts = generate_synthetic_batch(seed=seed, event_count=event_count)
        
        # Persist raw synthetic records
        for c in customers:
            session.merge(c)
        for p in payments:
            session.merge(p)
        for cs in checkouts:
            session.merge(cs)
        session.commit()

        # 1. Stage 1: Detector
        at_risk_events = Detector.detect_at_risk(customers, payments, checkouts)

        # 2. Stage 2: Diagnoser
        diagnosed_events = self.diagnoser.diagnose_batch(at_risk_events)

        # 3. Stage 3: Decision Engine
        self.decision_engine.reset_batch()
        decision_results = []
        for diag in diagnosed_events:
            dec = self.decision_engine.decide(
                customer_id=diag.event.customer_id,
                do_not_contact=diag.event.customer_do_not_contact,
                diagnosed_cause=diag.cause,
                confidence=diag.confidence,
                amount=diag.event.amount,
                event_type=diag.event.event_type
            )
            decision_results.append(dec)

        # 4. Stage 4: Executor + Guardrails
        executed_actions = self.executor.execute_batch(diagnosed_events, decision_results, seed=seed)

        # 5. Stage 5: Outcomes
        outcome_sim = OutcomeSimulator(seed=seed)
        outcome_results = []
        for diag, dec, exec_act in zip(diagnosed_events, decision_results, executed_actions):
            out = outcome_sim.simulate(
                intervention=dec.chosen_intervention,
                channel=exec_act.channel,
                amount=diag.event.amount,
                stopping_rule_triggered=dec.stopping_rule_triggered,
                guardrail_ok=exec_act.guardrail_ok
            )
            outcome_results.append(out)

        # Assemble full audit trail rows
        recovery_actions: List[RecoveryAction] = []
        total_at_risk = sum(e.amount for e in at_risk_events)
        total_gross = 0.0
        total_net = 0.0
        recovered_count = 0
        escalated_count = 0
        stopped_count = 0

        for i in range(len(at_risk_events)):
            ev = at_risk_events[i]
            diag = diagnosed_events[i]
            dec = decision_results[i]
            exec_act = executed_actions[i]
            out = outcome_results[i]

            action_id = f"act_{batch_id}_{i+1:04d}"
            
            if out.outcome == "recovered":
                recovered_count += 1
            elif out.outcome == "escalated":
                escalated_count += 1
            elif out.outcome == "stopped":
                stopped_count += 1

            total_gross += out.amount_recovered
            total_net += out.net_recovered

            action_row = RecoveryAction(
                id=action_id,
                batch_id=batch_id,
                trigger_event_id=ev.event_id,
                trigger_type=ev.event_type,
                detected_at=ev.detected_at,
                diagnosed_cause=diag.cause,
                diagnosis_confidence=round(diag.confidence, 3),
                diagnosis_reasoning=diag.reasoning,
                diagnosis_source=diag.source,
                chosen_intervention=dec.chosen_intervention,
                intervention_bounds=dec.bounds.to_json(),
                decision_reasoning=dec.decision_reasoning,
                stopping_rule_triggered=dec.stopping_rule_triggered,
                executed_at=datetime.utcnow(),
                channel=exec_act.channel,
                drafted_message=exec_act.drafted_message,
                sent_message=exec_act.sent_message,
                guardrail_ok=exec_act.guardrail_ok,
                guardrail_reason=exec_act.guardrail_reason,
                outcome=out.outcome,
                amount_recovered=out.amount_recovered,
                intervention_cost=out.intervention_cost,
                net_recovered=out.net_recovered,
                follow_up_date=out.follow_up_date
            )
            session.add(action_row)
            recovery_actions.append(action_row)

        total_gross = round(total_gross, 2)
        total_net = round(total_net, 2)
        total_at_risk = round(total_at_risk, 2)
        agent_off_lost = total_at_risk

        batch_row = BatchRun(
            id=batch_id,
            seed=seed,
            event_count=event_count,
            created_at=datetime.utcnow(),
            total_at_risk=total_at_risk,
            total_recovered_gross=total_gross,
            total_recovered_net=total_net,
            agent_off_total_lost=agent_off_lost,
            at_risk_count=len(at_risk_events),
            recovered_count=recovered_count,
            escalated_count=escalated_count,
            stopped_count=stopped_count,
            status="completed"
        )
        session.add(batch_row)
        session.commit()

        # Run guardrail adversarial self-test
        self_test = Executor.run_guardrail_self_test()

        # Generate concise plain-English non-technical narrative summary
        summary_text = (
            f"Batch #{seed} analyzed {event_count} raw checkout & payment events, flagging {len(at_risk_events)} at-risk transactions "
            f"totaling ₹{total_at_risk:,.2f}. The deterministic policy engine intervened on actionable drop-offs while strictly enforcing "
            f"stopping rules on {stopped_count} events and escalating {escalated_count} fraud/risk events. "
            f"The engine recovered ₹{total_gross:,.2f} gross revenue (₹{total_net:,.2f} net of communication fees) "
            f"across {recovered_count} successfully re-engaged customers — preventing revenue leakage that would have been 100% lost without the agent."
        )

        return BatchRunSummaryResponse(
            batch=batch_row,
            actions=recovery_actions,
            self_test=self_test,
            summary_text=summary_text
        )
