"""
Pure-Python negotiation state machine enforcing honesty and safety rules.

Design decision: Keeping decision logic strictly algorithmic (no LLM in the state
transitions) ensures mathematical guarantees: the agent can NEVER hallucinate a
competing quote, can NEVER commit the user to buy, and strictly obeys the refusal limit.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.bus import publish_event
from backend.models import Offer, TimelineEvent, Weights


class NegotiationState(str, Enum):
    GREET = "GREET"
    COLLECT = "COLLECT"
    PROBE = "PROBE"
    COUNTER = "COUNTER"
    DECIDE = "DECIDE"
    CLOSE = "CLOSE"


class NegotiationAction:
    """Action recommendation emitted by the state machine."""

    def __init__(
        self,
        next_state: NegotiationState,
        intent: str,
        competing_quote: Optional[int] = None,
        competing_warranty: Optional[int] = None,
        conflict_field: Optional[str] = None,
        conflict_old_value: Optional[str] = None,
        conflict_new_value: Optional[str] = None,
        reason: str = "",
    ):
        self.next_state = next_state
        self.intent = intent
        self.competing_quote = competing_quote
        self.competing_warranty = competing_warranty
        self.conflict_field = conflict_field
        self.conflict_old_value = conflict_old_value
        self.conflict_new_value = conflict_new_value
        self.reason = reason


def _find_genuine_competing_offer(
    current_call_id: str,
    current_price: Optional[int],
    other_offers: Dict[str, Offer],
) -> Optional[Offer]:
    """
    Honesty Rule 2: Returns the best competing offer strictly from other calls.
    Returns None if no other call has collected a verified lower price.
    """
    if current_price is None or not other_offers:
        return None

    valid_competitors = []
    for cid, off in other_offers.items():
        if cid != current_call_id and off.price is not None and off.price < current_price:
            valid_competitors.append(off)

    if not valid_competitors:
        return None

    # Pick lowest price among genuine collected competitors
    return min(valid_competitors, key=lambda o: o.price or 999999)


def next_negotiation_step(
    current_state: NegotiationState,
    current_offer: Optional[Offer],
    other_offers: Dict[str, Offer],
    user_weights: Weights,
    turn_count: int,
    refusal_count: int = 0,
    active_conflict: Optional[dict] = None,
    shop_refused_last_turn: bool = False,
    job_id: Optional[str] = None,
    call_id: Optional[str] = None,
    ts: float = 0.0,
) -> NegotiationAction:
    """
    Computes the next negotiation action using pure algorithmic rules.
    Emits timeline events for every significant decision.
    """
    # Safety Check: Guard turn limit (max 14 turns)
    if turn_count >= 14:
        return NegotiationAction(
            next_state=NegotiationState.CLOSE,
            intent="close",
            reason="Maximum turn limit reached.",
        )

    # 1. GREET State -> Open call with mandatory AI disclosure
    if current_state == NegotiationState.GREET:
        return NegotiationAction(
            next_state=NegotiationState.COLLECT,
            intent="greet",
            reason="AI disclosure and asking for initial service quote.",
        )

    # Contradiction Rule: Confirm discrepancies first if detected
    if active_conflict:
        field = active_conflict.get("field", "quote")
        old_v = active_conflict.get("old_value", "")
        new_v = active_conflict.get("new_value", "")
        if job_id and call_id:
            publish_event(
                job_id,
                TimelineEvent(
                    call_id=call_id,
                    text=f"Agent noticed {field} changed from {old_v} to {new_v} and asks to confirm.",
                    ts=ts,
                ),
            )
        return NegotiationAction(
            next_state=NegotiationState.PROBE,
            intent="confirm_conflict",
            conflict_field=field,
            conflict_old_value=old_v,
            conflict_new_value=new_v,
            reason=f"Shop gave conflicting values for {field}: was {old_v}, now {new_v}.",
        )

    # 2. COLLECT State -> Collect price if missing
    if current_offer is None or current_offer.price is None:
        return NegotiationAction(
            next_state=NegotiationState.COLLECT,
            intent="ask_price",
            reason="Waiting for initial price quote.",
        )

    # 3. PROBE State -> Inquire warranty or part type if missing
    if current_offer.warranty_months is None:
        return NegotiationAction(
            next_state=NegotiationState.PROBE,
            intent="ask_warranty",
            reason="Price known, checking warranty period.",
        )

    if current_offer.part_type == "Unknown":
        return NegotiationAction(
            next_state=NegotiationState.PROBE,
            intent="ask_part_type",
            reason="Checking whether part is original (OEM) or aftermarket.",
        )

    # 4. COUNTER State -> Honesty & Refusal Rules
    # If shop already refused twice, stop countering
    if refusal_count >= 2:
        if job_id and call_id:
            publish_event(
                job_id,
                TimelineEvent(
                    call_id=call_id,
                    text=f"Shop held firm on Rs {current_offer.price} after multiple requests.",
                    ts=ts,
                ),
            )
        return NegotiationAction(
            next_state=NegotiationState.DECIDE,
            intent="decide",
            reason="Shop held firm; proceeding to decision.",
        )

    # Honesty Rule 2: Only cite quotes actually collected in other calls
    competing_offer = _find_genuine_competing_offer(
        current_call_id=current_offer.call_id,
        current_price=current_offer.price,
        other_offers=other_offers,
    )

    if competing_offer and competing_offer.price is not None:
        if job_id and call_id:
            publish_event(
                job_id,
                TimelineEvent(
                    call_id=call_id,
                    text=f"Agent countered citing genuine Rs {competing_offer.price} quote from another shop.",
                    ts=ts,
                ),
            )
        return NegotiationAction(
            next_state=NegotiationState.COUNTER,
            intent="counter_with_real_quote",
            competing_quote=competing_offer.price,
            competing_warranty=competing_offer.warranty_months or 3,
            reason=f"Citing verified competing offer of Rs {competing_offer.price}.",
        )

    # If no lower competing quote exists, ask if any discount is possible without inventing a quote
    if current_state != NegotiationState.COUNTER and refusal_count == 0:
        return NegotiationAction(
            next_state=NegotiationState.COUNTER,
            intent="ask_best_discount",
            reason="Asking for best possible price without citing fake competitors.",
        )

    # 5. DECIDE & CLOSE -> Never commit to buy; close politely
    return NegotiationAction(
        next_state=NegotiationState.CLOSE,
        intent="close",
        reason="Information complete; thanking shop and ending call.",
    )
