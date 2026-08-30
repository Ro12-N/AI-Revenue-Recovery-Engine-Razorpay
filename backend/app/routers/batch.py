import csv
import io
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlmodel import Session, select
from app.db import get_session
from app.models import (
    BatchRun,
    RecoveryAction,
    Customer,
    PaymentEvent,
    CheckoutSession,
    BatchRunRequest,
    BatchRunSummaryResponse,
    EventTraceResponse
)
from app.pipeline.pipeline import RevenueRecoveryPipeline
from app.pipeline.executor import Executor

router = APIRouter(prefix="/batch", tags=["batch"])
pipeline = RevenueRecoveryPipeline()

@router.post("/run", response_model=BatchRunSummaryResponse)
def run_batch_endpoint(
    req: BatchRunRequest,
    session: Session = Depends(get_session)
):
    """
    Executes a reproducible batch run across the 5-stage pipeline.
    """
    try:
        response = pipeline.run_batch(
            session=session,
            seed=req.seed,
            event_count=req.event_count
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{batch_id}", response_model=BatchRunSummaryResponse)
def get_batch_endpoint(
    batch_id: str,
    session: Session = Depends(get_session)
):
    """
    Retrieves full summary and all recovery action audit records for a batch.
    """
    batch = session.get(BatchRun, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch run not found")

    actions_stmt = select(RecoveryAction).where(RecoveryAction.batch_id == batch_id)
    actions = session.exec(actions_stmt).all()

    self_test = Executor.run_guardrail_self_test()
    summary_text = (
        f"Batch #{batch.seed} processed {batch.event_count} events with {batch.at_risk_count} at-risk items. "
        f"Recovered ₹{batch.total_recovered_gross:,.2f} gross / ₹{batch.total_recovered_net:,.2f} net."
    )

    return BatchRunSummaryResponse(
        batch=batch,
        actions=actions,
        self_test=self_test,
        summary_text=summary_text
    )


@router.get("/{batch_id}/events/{event_id}", response_model=EventTraceResponse)
def get_event_trace_endpoint(
    batch_id: str,
    event_id: str,
    session: Session = Depends(get_session)
):
    """
    Returns full 5-stage trace for an individual event, including customer and raw event metadata.
    """
    action_stmt = select(RecoveryAction).where(
        RecoveryAction.batch_id == batch_id,
        RecoveryAction.trigger_event_id == event_id
    )
    action = session.exec(action_stmt).first()
    if not action:
        raise HTTPException(status_code=404, detail="Event action not found in specified batch")

    payment_event = None
    checkout_session = None
    customer = None

    if action.trigger_type == "payment_event":
        payment_event = session.get(PaymentEvent, event_id)
        if payment_event:
            customer = session.get(Customer, payment_event.customer_id)
    else:
        checkout_session = session.get(CheckoutSession, event_id)
        if checkout_session:
            customer = session.get(Customer, checkout_session.customer_id)

    return EventTraceResponse(
        action=action,
        customer=customer,
        payment_event=payment_event,
        checkout_session=checkout_session
    )


@router.get("/{batch_id}/export")
def export_batch_audit_log(
    batch_id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    session: Session = Depends(get_session)
):
    """
    Exports the complete audit ledger as CSV or JSON.
    """
    actions_stmt = select(RecoveryAction).where(RecoveryAction.batch_id == batch_id)
    actions = session.exec(actions_stmt).all()
    if not actions:
        raise HTTPException(status_code=404, detail="No audit actions found for batch")

    if format == "json":
        data = [a.model_dump() for a in actions]
        return JSONResponse(
            content=data,
            headers={"Content-Disposition": f"attachment; filename={batch_id}_audit_ledger.json"}
        )

    # CSV Export
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    headers = [
        "id", "trigger_event_id", "trigger_type", "diagnosed_cause",
        "diagnosis_confidence", "diagnosis_source", "chosen_intervention",
        "intervention_bounds", "stopping_rule_triggered", "channel",
        "drafted_message", "sent_message", "guardrail_ok", "guardrail_reason",
        "outcome", "amount_recovered", "intervention_cost", "net_recovered", "follow_up_date"
    ]
    writer.writerow(headers)

    for a in actions:
        writer.writerow([
            a.id, a.trigger_event_id, a.trigger_type, a.diagnosed_cause,
            a.diagnosis_confidence, a.diagnosis_source, a.chosen_intervention,
            a.intervention_bounds, a.stopping_rule_triggered or "", a.channel,
            a.drafted_message or "", a.sent_message or "", a.guardrail_ok,
            a.guardrail_reason or "", a.outcome, a.amount_recovered,
            a.intervention_cost, a.net_recovered, a.follow_up_date or ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={batch_id}_audit_ledger.csv"}
    )
