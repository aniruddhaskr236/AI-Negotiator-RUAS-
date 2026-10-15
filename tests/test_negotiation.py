import pytest
from backend.models import Offer, Weights
from backend.negotiation import (
    NegotiationAction,
    NegotiationState,
    next_negotiation_step,
)


def test_rule_greet_starts_with_disclosure():
    """Verify first step is GREET transitioning to COLLECT with disclosure intent."""
    action = next_negotiation_step(
        current_state=NegotiationState.GREET,
        current_offer=None,
        other_offers={},
        user_weights=Weights(),
        turn_count=0,
    )
    assert action.next_state == NegotiationState.COLLECT
    assert action.intent == "greet"


def test_honesty_rule_cannot_cite_uncollected_quote():
    """
    CRITICAL SAFETY TEST:
    Prove that the agent NEVER cites a competing quote if no other call has collected one.
    """
    current_offer = Offer(
        call_id="c_1",
        price=4500,
        warranty_months=6,
        part_type="OEM",
    )
    # No other offers exist in session
    other_offers = {}

    action = next_negotiation_step(
        current_state=NegotiationState.COLLECT,
        current_offer=current_offer,
        other_offers=other_offers,
        user_weights=Weights(),
        turn_count=2,
    )
    # Must NOT have a competing quote
    assert action.competing_quote is None
    # Must only ask for general discount or close, never invent a number
    assert action.intent in ("ask_best_discount", "close")


def test_honesty_rule_cites_genuine_lower_quote():
    """Verify agent only cites quote when a real lower quote exists in other calls."""
    current_offer = Offer(
        call_id="c_1",
        price=4500,
        warranty_months=6,
        part_type="OEM",
    )
    # Shop 2 provided real quote of 3900
    other_offers = {
        "c_2": Offer(call_id="c_2", price=3900, warranty_months=3, part_type="Aftermarket")
    }

    action = next_negotiation_step(
        current_state=NegotiationState.COLLECT,
        current_offer=current_offer,
        other_offers=other_offers,
        user_weights=Weights(),
        turn_count=2,
    )
    assert action.next_state == NegotiationState.COUNTER
    assert action.intent == "counter_with_real_quote"
    assert action.competing_quote == 3900


def test_refusal_limit_stops_countering():
    """Verify agent stops countering after two refusals."""
    current_offer = Offer(
        call_id="c_1",
        price=4500,
        warranty_months=6,
        part_type="OEM",
    )
    other_offers = {
        "c_2": Offer(call_id="c_2", price=3900, warranty_months=3)
    }

    action = next_negotiation_step(
        current_state=NegotiationState.COUNTER,
        current_offer=current_offer,
        other_offers=other_offers,
        user_weights=Weights(),
        turn_count=4,
        refusal_count=2,  # Shop already refused twice
    )
    assert action.next_state == NegotiationState.DECIDE
    assert action.competing_quote is None


def test_conflict_triggers_confirmation():
    """Verify contradiction triggers immediate confirmation request."""
    current_offer = Offer(call_id="c_1", price=4200)
    conflict = {"field": "price", "old_value": "4500", "new_value": "4200"}

    action = next_negotiation_step(
        current_state=NegotiationState.COLLECT,
        current_offer=current_offer,
        other_offers={},
        user_weights=Weights(),
        turn_count=2,
        active_conflict=conflict,
    )
    assert action.intent == "confirm_conflict"
    assert action.conflict_field == "price"
    assert action.conflict_old_value == "4500"


def test_turn_limit_guard():
    """Verify call terminates if 14 turns reached."""
    action = next_negotiation_step(
        current_state=NegotiationState.COUNTER,
        current_offer=Offer(call_id="c_1", price=4500),
        other_offers={},
        user_weights=Weights(),
        turn_count=14,
    )
    assert action.next_state == NegotiationState.CLOSE
    assert action.intent == "close"
