"""
Unit and integration tests for speech-to-text (STT) and text-to-speech (TTS) pipeline.
Tests Groq Whisper path, Sarvam fallback/exceptions, needs_repeat flag, and WebSocket audio handling.
"""

import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.config import settings
from backend import speech
from backend.models import Call, Job, Weights
from backend import store
from backend.calls import call_manager


@pytest.fixture(autouse=True)
def clean_store():
    store.init_db()
    call_manager.shop_sockets.clear()
    call_manager.answer_events.clear()
    call_manager.call_tasks.clear()
    call_manager.shop_queues.clear()
    yield


@pytest.mark.asyncio
async def test_transcribe_empty_or_truncated_audio():
    """Short or empty audio payloads should immediately return needs_repeat=True."""
    text, conf, needs_repeat = await speech.transcribe(b"")
    assert text == ""
    assert conf == 0.0
    assert needs_repeat is True

    text, conf, needs_repeat = await speech.transcribe(b"small_junk_data")
    assert text == ""
    assert conf == 0.0
    assert needs_repeat is True


@pytest.mark.asyncio
async def test_transcribe_sarvam_unconfigured_error():
    """Sarvam direct transcription raises ValueError if key is not configured."""
    original_key = settings.sarvam_api_key
    try:
        settings.sarvam_api_key = ""
        with pytest.raises(ValueError, match="SARVAM_API_KEY is not configured"):
            await speech.transcribe_sarvam(b"a" * 200)
    finally:
        settings.sarvam_api_key = original_key


@pytest.mark.asyncio
async def test_transcribe_groq_whisper_unconfigured_error():
    """Groq Whisper direct transcription raises ValueError if key is not configured."""
    original_key = settings.groq_api_key
    try:
        settings.groq_api_key = ""
        with pytest.raises(ValueError, match="GROQ_API_KEY is not configured"):
            await speech.transcribe_groq_whisper(b"a" * 200)
    finally:
        settings.groq_api_key = original_key


@pytest.mark.asyncio
async def test_transcribe_sarvam_success():
    """When Sarvam is configured and succeeds, returns transcript with high confidence."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"transcript": "स्क्रीन बदलवाने का चार हज़ार लगेगा"}
    mock_resp.raise_for_status = MagicMock()

    original_key = settings.sarvam_api_key
    try:
        settings.sarvam_api_key = "test_sarvam_key"
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            text, conf, needs_repeat = await speech.transcribe(b"x" * 200, lang_hint="hi")
            assert text == "स्क्रीन बदलवाने का चार हज़ार लगेगा"
            assert conf == 0.95
            assert needs_repeat is False
    finally:
        settings.sarvam_api_key = original_key


@pytest.mark.asyncio
async def test_transcribe_sarvam_fallback_to_groq():
    """When Sarvam fails, gracefully falls back to Groq Whisper."""
    groq_resp = MagicMock()
    groq_resp.status_code = 200
    groq_resp.json.return_value = {"text": "Screen price is 3500 rupees"}
    groq_resp.raise_for_status = MagicMock()

    original_sarvam = settings.sarvam_api_key
    original_groq = settings.groq_api_key
    try:
        settings.sarvam_api_key = "test_sarvam_key"
        settings.groq_api_key = "test_groq_key"

        # Sarvam fails with HTTP 500, Groq succeeds
        async def mock_post(url, **kwargs):
            if "sarvam.ai" in url:
                raise RuntimeError("Sarvam 500 internal error")
            return groq_resp

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            text, conf, needs_repeat = await speech.transcribe(b"x" * 200)
            assert text == "Screen price is 3500 rupees"
            assert conf == 0.90
            assert needs_repeat is False
    finally:
        settings.sarvam_api_key = original_sarvam
        settings.groq_api_key = original_groq


@pytest.mark.asyncio
async def test_transcribe_all_providers_fail_needs_repeat():
    """When all providers fail or are unconfigured, flags needs_repeat=True."""
    original_sarvam = settings.sarvam_api_key
    original_groq = settings.groq_api_key
    try:
        settings.sarvam_api_key = ""
        settings.groq_api_key = ""
        text, conf, needs_repeat = await speech.transcribe(b"x" * 200)
        assert text == ""
        assert conf == 0.0
        assert needs_repeat is True
    finally:
        settings.sarvam_api_key = original_sarvam
        settings.groq_api_key = original_groq


@pytest.mark.asyncio
async def test_synthesize_sarvam_and_fallback():
    """Synthesize returns audio if Sarvam TTS works, else None for browser speech."""
    # 1. Unconfigured -> returns None
    original_sarvam = settings.sarvam_api_key
    try:
        settings.sarvam_api_key = ""
        res = await speech.synthesize("Hello shopkeeper")
        assert res is None

        # 2. Configured and succeeds
        settings.sarvam_api_key = "test_key"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"audios": ["base64encodedmp3data"]}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            res = await speech.synthesize("Hello shopkeeper", lang="en")
            assert res == ("audio/mpeg", "base64encodedmp3data")
    finally:
        settings.sarvam_api_key = original_sarvam


@pytest.mark.asyncio
async def test_speech_health_listener():
    """Registered speech health listeners receive provider status events."""
    events = []
    speech.add_speech_health_listener(lambda ev: events.append(ev))

    # Trigger a health event
    speech._publish_speech_health("Groq-Whisper", ok=True, active=True)
    assert len(events) >= 1
    assert events[-1] == {
        "type": "health",
        "provider": "Groq-Whisper",
        "ok": True,
        "active": True,
    }


def test_shop_websocket_audio_message():
    """Verify audio message sent over /ws/shop/{shop_id} is transcribed and enqueued."""
    import asyncio
    from fastapi.testclient import TestClient
    from backend.main import app

    job = Job(job_id="test_audio_job", need="screen", weights=Weights(), created_at=100.0)
    store.save_job(job)
    call = Call(
        call_id="call_audio_1",
        job_id="test_audio_job",
        shop_id="1",
        shop_name="Sri Ganesh",
        lang="en",
        status="talking",
    )
    store.save_call(call)
    call_manager.shop_queues["call_audio_1"] = asyncio.Queue()

    client = TestClient(app)
    with patch("backend.routes_ws.transcribe", new_callable=AsyncMock) as mock_trans:
        mock_trans.return_value = ("Original screen 3800 rupees", 0.95, False)
        with client.websocket_connect("/ws/shop/1") as ws:
            fake_b64 = base64.b64encode(b"dummy_audio_bytes" * 10).decode("utf-8")
            ws.send_json({
                "type": "audio",
                "call_id": "call_audio_1",
                "mime": "audio/webm",
                "data": fake_b64,
                "ts": 123.45,
            })
            q = call_manager.shop_queues["call_audio_1"]
            import time
            for _ in range(50):
                if not q.empty():
                    break
                time.sleep(0.05)
            assert not q.empty(), "Audio message was not enqueued in time"
            msg = q.get_nowait()
            assert msg["type"] == "audio"
            assert msg["call_id"] == "call_audio_1"
            assert msg["text"] == "Original screen 3800 rupees"
            assert msg["confidence"] == 0.95
            assert msg["needs_repeat"] is False
