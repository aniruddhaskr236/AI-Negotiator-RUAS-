"""
Speech-to-text (STT) and text-to-speech (TTS) pipeline.

Design decision: Groq Whisper provides low-latency speech transcription with
Sarvam as a clean Indic-first option when configured. If audio is garbled or
providers are unreachable, it flags needs_repeat so the agent politely asks the
shopkeeper to repeat or use the typed input box.
"""

import base64
import time
from typing import Any, Callable, Optional, Tuple
import httpx

from backend.config import logger, settings

# Optional listener for speech health events
_speech_health_listeners: list[Callable[[dict[str, Any]], Any]] = []


def add_speech_health_listener(listener: Callable[[dict[str, Any]], Any]) -> None:
    """Register callback for speech provider health updates."""
    _speech_health_listeners.append(listener)


def _publish_speech_health(provider: str, ok: bool, active: bool) -> None:
    event = {
        "type": "health",
        "provider": provider,
        "ok": ok,
        "active": active,
    }
    for listener in _speech_health_listeners:
        try:
            listener(event)
        except Exception:
            pass


async def transcribe_sarvam(
    audio_bytes: bytes,
    mime: str = "audio/webm",
    lang_hint: Optional[str] = None,
    timeout: float = 6.0,
) -> str:
    """Transcribe using Sarvam AI Saaras model (active if key is configured)."""
    if not settings.sarvam_api_key:
        raise ValueError("SARVAM_API_KEY is not configured")

    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": settings.sarvam_api_key}
    files = {"file": ("audio.webm", audio_bytes, mime)}
    data = {"model": "saaras:v2", "language_code": f"{lang_hint}-IN" if lang_hint and lang_hint != "en" else "hi-IN"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        res_json = resp.json()
        return res_json.get("transcript", "")


async def transcribe_groq_whisper(
    audio_bytes: bytes,
    mime: str = "audio/webm",
    timeout: float = 6.0,
) -> str:
    """Transcribe using Groq Whisper API (whisper-large-v3)."""
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured")

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    files = {"file": ("audio.webm", audio_bytes, mime)}
    data = {
        "model": settings.groq_whisper_model,
        "temperature": 0.0,
        "response_format": "json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        res_json = resp.json()
        return res_json.get("text", "")


async def transcribe(
    audio_bytes: bytes,
    mime: str = "audio/webm",
    lang_hint: Optional[str] = None,
    timeout: float = 6.0,
) -> Tuple[str, float, bool]:
    """
    Transcribes audio bytes with fallback chain:
    1. Sarvam (Indic first, if configured)
    2. Groq Whisper (production default)
    3. Failure flag (needs_repeat=True)
    Returns: (text, confidence, needs_repeat)
    """
    if not audio_bytes or len(audio_bytes) < 100:
        logger.warning("Empty or truncated audio payload received")
        return "", 0.0, True

    # 1. Try Sarvam if configured
    if settings.sarvam_api_key:
        try:
            text = await transcribe_sarvam(audio_bytes, mime, lang_hint, timeout)
            if text and text.strip():
                _publish_speech_health("Sarvam-STT", ok=True, active=True)
                return text.strip(), 0.95, False
        except Exception as exc:
            logger.warning("Sarvam STT failed (%s), falling back to Groq: %s", type(exc).__name__, exc)
            _publish_speech_health("Sarvam-STT", ok=False, active=False)

    # 2. Try Groq Whisper
    if settings.groq_api_key:
        try:
            text = await transcribe_groq_whisper(audio_bytes, mime, timeout)
            if text and text.strip():
                _publish_speech_health("Groq-Whisper", ok=True, active=True)
                return text.strip(), 0.90, False
        except Exception as exc:
            logger.warning("Groq Whisper STT failed (%s): %s", type(exc).__name__, exc)
            _publish_speech_health("Groq-Whisper", ok=False, active=False)

    # 3. Audio failed or unclear
    logger.info("Speech transcription unavailable or unclear. Requesting repeat.")
    return "", 0.0, True


async def synthesize(
    text: str,
    lang: str = "en",
    timeout: float = 5.0,
) -> Optional[Tuple[str, str]]:
    """
    Synthesize speech for agent text.
    Returns: (mime, base64_data) or None (allowing shop page browser speech synthesis).
    """
    if not text:
        return None

    # Try Sarvam TTS if configured
    if settings.sarvam_api_key:
        try:
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {"api-subscription-key": settings.sarvam_api_key, "Content-Type": "application/json"}
            lang_code = f"{lang}-IN" if lang in ("hi", "kn") else "en-IN"
            payload = {
                "inputs": [text],
                "target_language_code": lang_code,
                "model": settings.sarvam_tts_model,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    audios = data.get("audios", [])
                    if audios:
                        _publish_speech_health("Sarvam-TTS", ok=True, active=True)
                        return "audio/mpeg", audios[0]
        except Exception as exc:
            logger.warning("Sarvam TTS failed, relying on browser speech: %s", exc)
            _publish_speech_health("Sarvam-TTS", ok=False, active=False)

    # Return None so client browser uses speech synthesis
    return None
