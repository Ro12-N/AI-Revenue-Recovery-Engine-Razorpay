from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from app.pipeline.detector import AtRiskEvent
from app.llm.client import LLMClient
from app.llm.prompts import DIAGNOSIS_SYSTEM_PROMPT

DECLINE_CODE_MAP = {
    "INSUFFICIENT_FUNDS": "insufficient_funds",
    "RISK_BLOCK": "risk_decline",
    "CARD_EXPIRED": "expired_card",
    "GATEWAY_TIMEOUT": "bank_timeout",
}

DECLINE_REASON_MAP = {
    "INSUFFICIENT_FUNDS": "Bank returned explicit decline code INSUFFICIENT_FUNDS.",
    "RISK_BLOCK": "Issuer or gateway flagged transaction as RISK_BLOCK.",
    "CARD_EXPIRED": "Card validity check failed with CARD_EXPIRED.",
    "GATEWAY_TIMEOUT": "Bank or acquiring gateway timed out during processing (GATEWAY_TIMEOUT).",
}

@dataclass
class DiagnosedEvent:
    event: AtRiskEvent
    cause: str
    confidence: float
    reasoning: str
    source: str  # "rules" | "llm" | "llm-fallback"


class Diagnoser:
    """
    Stage 2: Diagnoser.
    - Rule-based deterministic mapping for explicit decline codes (confidence=0.98, zero LLM calls).
    - Batched Claude 3.5 Sonnet tool-use for ambiguous payment/checkout events.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def diagnose_batch(self, at_risk_events: List[AtRiskEvent]) -> List[DiagnosedEvent]:
        diagnosed: List[DiagnosedEvent] = []
        ambiguous_events: List[AtRiskEvent] = []

        # 1. Separate deterministic decline codes from ambiguous events
        for ev in at_risk_events:
            if ev.decline_code and ev.decline_code in DECLINE_CODE_MAP:
                cause = DECLINE_CODE_MAP[ev.decline_code]
                reason = DECLINE_REASON_MAP.get(ev.decline_code, f"Explicit decline code {ev.decline_code}.")
                diagnosed.append(
                    DiagnosedEvent(
                        event=ev,
                        cause=cause,
                        confidence=0.98,
                        reasoning=reason,
                        source="rules"
                    )
                )
            else:
                ambiguous_events.append(ev)

        # 2. Batch ambiguous events in chunks of ~12
        if ambiguous_events:
            chunk_size = 12
            for i in range(0, len(ambiguous_events), chunk_size):
                chunk = ambiguous_events[i : i + chunk_size]
                chunk_payload = [
                    {
                        "id": ev.event_id,
                        "type": ev.event_type,
                        "amount": ev.amount,
                        "raw_status": ev.raw_status,
                        "funnel_stage": ev.funnel_stage,
                        "device": ev.device,
                        "time_on_page_seconds": ev.time_on_page_seconds,
                        "is_subscription": ev.is_subscription,
                        "payment_method": ev.payment_method,
                        "customer_avg_order_value": ev.customer_avg_order_value,
                        "customer_repeat": ev.customer_repeat
                    }
                    for ev in chunk
                ]

                raw_diagnoses = self.llm.classify_ambiguous_batch(chunk_payload, DIAGNOSIS_SYSTEM_PROMPT)
                diag_by_id = {d["id"]: d for d in raw_diagnoses if "id" in d}

                source_label = "llm" if self.llm.is_live() else "llm-fallback"

                for ev in chunk:
                    if ev.event_id in diag_by_id:
                        d = diag_by_id[ev.event_id]
                        diagnosed.append(
                            DiagnosedEvent(
                                event=ev,
                                cause=d.get("cause", "unknown"),
                                confidence=float(d.get("confidence", 0.3)),
                                reasoning=d.get("reasoning", "Classified via behavioral inference."),
                                source=source_label
                            )
                        )
                    else:
                        # Malformed or missing response fallback
                        diagnosed.append(
                            DiagnosedEvent(
                                event=ev,
                                cause="unknown",
                                confidence=0.30,
                                reasoning="Classifier did not return a valid structured diagnosis for event.",
                                source="llm-fallback"
                            )
                        )

        # Re-sort to maintain original order
        event_order = {ev.event_id: idx for idx, ev in enumerate(at_risk_events)}
        diagnosed.sort(key=lambda x: event_order.get(x.event.event_id, 0))
        return diagnosed
