import pytest
from unittest.mock import AsyncMock, patch
from backend.config import Settings
from scripts import check_env


@pytest.mark.asyncio
async def test_ping_groq_not_set():
    """Verify ping returns not set when key is empty."""
    mock_settings = Settings(groq_api_key="")
    with patch("scripts.check_env.settings", mock_settings):
        ok, lat, detail = await check_env.ping_groq()
        assert not ok
        assert "not set" in detail


@pytest.mark.asyncio
async def test_ping_groq_mock_success():
    """Verify ping groq succeeds on 200 response."""
    mock_settings = Settings(groq_api_key="mock_key")
    with patch("scripts.check_env.settings", mock_settings), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, lat, detail = await check_env.ping_groq()
        assert ok
        assert detail == "OK"
