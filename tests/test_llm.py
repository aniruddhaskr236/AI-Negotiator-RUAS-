import pytest
from unittest.mock import AsyncMock, patch
from pydantic import BaseModel
from backend import llm


class SampleSchema(BaseModel):
    message: str = "fallback message"
    price: int = 0


@pytest.mark.asyncio
async def test_llm_groq_success():
    """Verify Groq is used when available."""
    with patch("backend.llm._call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = "Hello from Groq"
        res = await llm.call_llm("test prompt")
        assert res == "Hello from Groq"
        mock_groq.assert_called_once()


@pytest.mark.asyncio
async def test_llm_fallback_to_mistral_when_groq_fails():
    """Verify fallback to Mistral when Groq throws an error."""
    with patch("backend.llm._call_groq", new_callable=AsyncMock) as mock_groq, \
         patch("backend.llm._call_mistral", new_callable=AsyncMock) as mock_mistral:
        mock_groq.side_effect = Exception("Groq rate limit 429")
        mock_mistral.return_value = "Hello from Mistral"

        res = await llm.call_llm("test prompt")
        assert res == "Hello from Mistral"
        mock_groq.assert_called_once()
        mock_mistral.assert_called_once()


@pytest.mark.asyncio
async def test_llm_all_fail_returns_rule_based_fallback():
    """Verify when all providers fail, a safe string is returned without crashing."""
    with patch("backend.llm._call_groq", new_callable=AsyncMock) as mock_groq, \
         patch("backend.llm._call_mistral", new_callable=AsyncMock) as mock_mistral, \
         patch("backend.llm._call_nemotron", new_callable=AsyncMock) as mock_nemotron:
        mock_groq.side_effect = Exception("Groq down")
        mock_mistral.side_effect = Exception("Mistral down")
        mock_nemotron.side_effect = Exception("Nemotron down")

        res = await llm.call_llm("test prompt")
        assert isinstance(res, str)
        assert len(res) > 0


@pytest.mark.asyncio
async def test_llm_schema_validation_and_fallback():
    """Verify that invalid JSON response triggers next provider."""
    with patch("backend.llm._call_groq", new_callable=AsyncMock) as mock_groq, \
         patch("backend.llm._call_mistral", new_callable=AsyncMock) as mock_mistral:
        # Groq returns invalid JSON for SampleSchema
        mock_groq.return_value = "Not a json"
        # Mistral returns valid JSON
        mock_mistral.return_value = '{"message": "Valid response", "price": 4200}'

        res = await llm.call_llm("test prompt", schema=SampleSchema)
        assert isinstance(res, SampleSchema)
        assert res.message == "Valid response"
        assert res.price == 4200


def test_provider_disable_and_enable():
    """Verify manual disable and re-enable of providers."""
    llm.disable_provider("Groq")
    assert not llm.is_provider_enabled("Groq")
    llm.enable_provider("Groq")
    assert llm.is_provider_enabled("Groq")


def test_health_listener_emits_event():
    """Verify registered listener receives health events."""
    events = []
    llm.add_health_listener(lambda ev: events.append(ev))
    llm.disable_provider("Mistral")
    assert any(e["provider"] == "Mistral" and e["ok"] is False for e in events)
    llm.enable_provider("Mistral")
    assert any(e["provider"] == "Mistral" and e["ok"] is True for e in events)
