import os
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CLASSIFY_TOOL_SCHEMA = {
    "name": "classify_causes",
    "description": "Output root cause classifications for a batch of payment and checkout failure events.",
    "input_schema": {
        "type": "object",
        "properties": {
            "diagnoses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The event ID being classified"},
                        "cause": {
                            "type": "string",
                            "enum": [
                                "otp_friction",
                                "price_shock",
                                "trust_hesitation",
                                "technical_error",
                                "comparison_shopping",
                                "unknown"
                            ],
                            "description": "Root cause classification"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score between 0.0 and 1.0"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief 1-sentence diagnostic explanation"
                        }
                    },
                    "required": ["id", "cause", "confidence", "reasoning"]
                }
            }
        },
        "required": ["diagnoses"]
    }
}

DRAFT_MESSAGES_TOOL_SCHEMA = {
    "name": "draft_messages",
    "description": "Output drafted message copies for a batch of recovery actions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "drafts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The action or event ID"},
                        "message": {"type": "string", "description": "Drafted message copy (under 280 chars)"},
                        "language": {"type": "string", "enum": ["English", "Hinglish"]}
                    },
                    "required": ["id", "message", "language"]
                }
            }
        },
        "required": ["drafts"]
    }
}


class LLMClient:
    """
    Thin, robust wrapper around the Anthropic SDK.
    Provides structured output calls for Stage 2 (Diagnoser) and Stage 4 (Executor).
    Includes intelligent deterministic fallback when API key is not present or on network failure.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = None
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}. Using fallback mode.")

    def is_live(self) -> bool:
        return self.client is not None

    def classify_ambiguous_batch(
        self,
        events: List[Dict[str, Any]],
        system_prompt: str
    ) -> List[Dict[str, Any]]:
        """
        Calls Claude with structured tool-use to classify ambiguous events.
        Falls back gracefully if client is offline or encounters an error.
        """
        if self.client:
            try:
                prompt_content = "Please classify root causes for these events:\n" + json.dumps(events, indent=2)
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt_content}],
                    tools=[CLASSIFY_TOOL_SCHEMA],
                    tool_choice={"type": "tool", "name": "classify_causes"}
                )

                for block in response.content:
                    if block.type == "tool_use" and block.name == "classify_causes":
                        diagnoses = block.input.get("diagnoses", [])
                        return diagnoses
            except Exception as e:
                logger.error(f"Anthropic API call failed during diagnosis: {e}. Using fallback heuristics.")

        # Deterministic Fallback Logic (used when no API key is provided or on failure)
        return self._heuristic_diagnosis_fallback(events)

    def draft_messages_batch(
        self,
        draft_requests: List[Dict[str, Any]],
        system_prompt: str
    ) -> List[Dict[str, Any]]:
        """
        Calls Claude with structured tool-use to draft SMS/WhatsApp recovery copy.
        Falls back gracefully if client is offline or encounters an error.
        """
        if self.client:
            try:
                prompt_content = "Draft recovery messages for these interventions respecting their hard bounds:\n" + json.dumps(draft_requests, indent=2)
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt_content}],
                    tools=[DRAFT_MESSAGES_TOOL_SCHEMA],
                    tool_choice={"type": "tool", "name": "draft_messages"}
                )

                for block in response.content:
                    if block.type == "tool_use" and block.name == "draft_messages":
                        drafts = block.input.get("drafts", [])
                        return drafts
            except Exception as e:
                logger.error(f"Anthropic API call failed during message drafting: {e}. Using fallback heuristics.")

        return self._heuristic_draft_fallback(draft_requests)

    def _heuristic_diagnosis_fallback(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Smart deterministic heuristic classifier for offline tests or when API key is not present.
        """
        results = []
        for ev in events:
            ev_id = ev["id"]
            stage = ev.get("funnel_stage", "")
            time_on_page = ev.get("time_on_page_seconds", 30)
            amount = ev.get("amount", 0.0)
            device = ev.get("device", "")
            raw_status = ev.get("raw_status", "")

            if raw_status == "degraded":
                results.append({
                    "id": ev_id,
                    "cause": "technical_error",
                    "confidence": 0.88,
                    "reasoning": "Payment gateway reported degraded status without explicit bank decline code."
                })
            elif stage == "otp":
                if time_on_page > 90:
                    results.append({
                        "id": ev_id,
                        "cause": "otp_friction",
                        "confidence": 0.82,
                        "reasoning": f"Customer stalled on OTP verification step for {time_on_page}s indicating delivery delay or SMS issue."
                    })
                else:
                    results.append({
                        "id": ev_id,
                        "cause": "otp_friction",
                        "confidence": 0.65,
                        "reasoning": "Abandoned at OTP submission stage."
                    })
            elif stage == "payment_page":
                if amount > 2500 and time_on_page > 80:
                    results.append({
                        "id": ev_id,
                        "cause": "price_shock",
                        "confidence": 0.78,
                        "reasoning": f"High cart value (₹{amount}) abandoned after {time_on_page}s review on payment screen."
                    })
                elif "mobile" in device and time_on_page < 40:
                    results.append({
                        "id": ev_id,
                        "cause": "trust_hesitation",
                        "confidence": 0.72,
                        "reasoning": "Drop-off on mobile payment screen with rapid exit suggesting security or payment method hesitation."
                    })
                else:
                    results.append({
                        "id": ev_id,
                        "cause": "price_shock",
                        "confidence": 0.60,
                        "reasoning": f"Cart total ₹{amount} abandoned on payment options selector."
                    })
            elif stage == "cart":
                if time_on_page < 45:
                    results.append({
                        "id": ev_id,
                        "cause": "comparison_shopping",
                        "confidence": 0.74,
                        "reasoning": f"Quick bounce from cart ({time_on_page}s) typical of comparative price checking."
                    })
                else:
                    results.append({
                        "id": ev_id,
                        "cause": "price_shock",
                        "confidence": 0.58,
                        "reasoning": "Extended cart review followed by drop-off prior to checkout initiation."
                    })
            elif stage in ("landed", "abandoned"):
                results.append({
                    "id": ev_id,
                    "cause": "comparison_shopping",
                    "confidence": 0.56,
                    "reasoning": "Early funnel exit with minimal page dwell time."
                })
            else:
                results.append({
                    "id": ev_id,
                    "cause": "unknown",
                    "confidence": 0.30,
                    "reasoning": "Insufficient behavioral data to identify specific drop-off cause."
                })

        return results

    def _heuristic_draft_fallback(self, draft_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        High-quality heuristic templates for offline runs and tests.
        """
        results = []
        for req in draft_requests:
            req_id = req["id"]
            intervention = req["intervention"]
            lang = req.get("language", "English")
            bounds = req.get("bounds", {})
            max_disc = bounds.get("max_discount_pct", 0)
            amount = req.get("amount", 0.0)

            if lang == "Hinglish":
                if intervention == "discount_offer" and max_disc > 0:
                    msg = f"Aapka cart wait kar raha hai! Complete order karein aur paayein {max_disc}% off (valid 24h). Tap to checkout."
                elif intervention == "resend_otp_simplified":
                    msg = "Aapka transaction OTP receive nahi hua? Yahan tap karke simplified 1-click verify karein."
                elif intervention == "retry_48h":
                    msg = f"Aapka payment process nahi ho paya. Humne aapka slot 48h ke liye hold kiya hai. Retry karein."
                elif intervention == "request_update":
                    msg = "Aapka card expire ho gaya hai. Seamless shopping ke liye payment details update karein."
                elif intervention == "trust_signal_message":
                    msg = "Aapka checkout safe hai! 100% Razorpay Secure Payment & Instant Refund Guarantee ke sath complete karein."
                elif intervention == "reminder_urgency":
                    msg = "Aapka cart items fast sell ho rahe hain! Stock khatam hone se pehle order confirm karein."
                elif intervention == "retry_prompt":
                    msg = "Technical issue ki wajah se payment pause ho gaya. Dobara try karne ke liye yahan tap karein."
                else:
                    msg = "Aapka order complete nahi ho paya. Complete karne ke liye yahan click karein."
            else:
                if intervention == "discount_offer" and max_disc > 0:
                    msg = f"Complete your pending order today and enjoy {max_disc}% off! Valid for the next 24 hours. Tap to claim."
                elif intervention == "resend_otp_simplified":
                    msg = "Had trouble receiving your OTP? Tap here for instant 1-click verification to complete your order."
                elif intervention == "retry_48h":
                    msg = f"Your payment of ₹{amount:.0f} was interrupted. We've reserved your order for 48 hours. Tap to retry."
                elif intervention == "request_update":
                    msg = "Your card on file has expired. Please update your payment method to ensure uninterrupted service."
                elif intervention == "trust_signal_message":
                    msg = "Shop with peace of mind: All orders are protected by 256-bit Razorpay Security & Buyer Protection."
                elif intervention == "reminder_urgency":
                    msg = "Items in your cart are in high demand! Complete your order before items sell out."
                elif intervention == "retry_prompt":
                    msg = "A temporary network glitch interrupted your payment. Tap to instantly retry."
                else:
                    msg = "Your order is waiting for you. Tap here to complete your checkout smoothly."

            results.append({
                "id": req_id,
                "message": msg[:280],
                "language": lang
            })

        return results
