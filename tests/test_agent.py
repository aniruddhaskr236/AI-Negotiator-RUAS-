import pytest
from unittest.mock import AsyncMock, patch
from backend import agent
from backend.negotiation import NegotiationAction, NegotiationState


@pytest.mark.asyncio
async def test_agent_greet_disclosure():
    """Verify greeting explicitly identifies as AI assistant calling for customer."""
    action = NegotiationAction(next_state=NegotiationState.COLLECT, intent="greet")
    text, trans = await agent.generate_agent_utterance(
        need="iPhone 13 screen fix",
        action=action,
        dialogue_history=[],
        target_lang="en",
    )
    assert "AI assistant calling on behalf of a customer" in text
    assert "iPhone 13 screen fix" in text


@pytest.mark.asyncio
async def test_agent_greet_hindi():
    """Verify Hindi greeting includes AI assistant disclosure and English translation."""
    action = NegotiationAction(next_state=NegotiationState.COLLECT, intent="greet")
    text, trans = await agent.generate_agent_utterance(
        need="iPhone display",
        action=action,
        dialogue_history=[],
        target_lang="hi",
    )
    assert "AI assistant" in text
    assert trans is not None
    assert "AI assistant" in trans


def test_number_guard_accepts_valid_quote():
    """Verify Number Guard passes when cited price matches verified competing quote."""
    action = NegotiationAction(
        next_state=NegotiationState.COUNTER,
        intent="counter_with_real_quote",
        competing_quote=3800,
    )
    candidate = "Another shop offered Rs 3800. Can you match that?"
    assert agent.audit_number_guard(candidate, action, current_shop_price=4500) is True


def test_number_guard_rejects_hallucinated_quote():
    """Verify Number Guard rejects when candidate hallucinates an unauthorized price."""
    action = NegotiationAction(
        next_state=NegotiationState.COUNTER,
        intent="counter_with_real_quote",
        competing_quote=3800,
    )
    candidate = "Another shop offered Rs 2900. Can you match that?"
    # 2900 was never authorized!
    assert agent.audit_number_guard(candidate, action, current_shop_price=4500) is False


def test_number_guard_rejects_quote_when_none_authorized():
    """Verify Number Guard blocks any price citation when no competitor quote exists."""
    action = NegotiationAction(
        next_state=NegotiationState.COUNTER,
        intent="ask_best_discount",
        competing_quote=None,
    )
    candidate = "Can you do it for Rs 3200?"
    assert agent.audit_number_guard(candidate, action, current_shop_price=4000) is False


@pytest.mark.asyncio
async def test_agent_blocks_purchase_agreement():
    """Verify agent blocks output attempting to finalize an order / agree to buy."""
    action = NegotiationAction(next_state=NegotiationState.CLOSE, intent="close")
    with patch("backend.agent.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Great, I will buy it and confirm order right now."
        text, _ = await agent.generate_agent_utterance(
            need="screen fix",
            action=action,
            dialogue_history=[],
            target_lang="en",
        )
        # Must fall back to safe non-committal closing
        assert "confirm order" not in text
        assert "I will share all the details with my customer" in text
