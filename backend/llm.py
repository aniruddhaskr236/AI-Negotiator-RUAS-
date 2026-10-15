"""
LLM calling layer with sequential provider fallback and health tracking.

Design decision: Groq -> Nemotron fallback chain guarantees that
rate limits, downtime, or bad JSON responses from any single provider will
never crash the live call or server. If all fail, a deterministic fallback
is returned.
"""

import asyncio
import json
import time
from typing import Any, Callable, Optional, Type
import httpx
from pydantic import BaseModel

from backend.config import settings, logger

# Active disabled providers for live demo failure injection
_disabled_providers: set[str] = set()

# Health state per provider
_provider_health: dict[str, dict[str, Any]] = {
    "Groq": {"ok": True, "active": True, "latency_ms": 0, "last_error": None},
    "Nemotron": {"ok": True, "active": False, "latency_ms": 0, "last_error": None},
}

# Optional listener for health events (e.g. event bus)
_health_listeners: list[Callable[[dict[str, Any]], Any]] = []


def add_health_listener(listener: Callable[[dict[str, Any]], Any]) -> None:
    """Register a callback for health state updates."""
    _health_listeners.append(listener)


def _publish_health(provider: str, ok: bool, active: bool, error: Optional[str] = None) -> None:
    """Updates health cache and notifies subscribers of provider status."""
    _provider_health[provider] = {
        "ok": ok,
        "active": active,
        "last_error": error,
    }
    event = {
        "type": "health",
        "provider": provider,
        "ok": ok,
        "active": active,
    }
    for listener in _health_listeners:
        try:
            listener(event)
        except Exception as e:
            logger.warning("Error notifying health listener: %s", e)


def disable_provider(name: str) -> None:
    """Force disable a provider (used by POST /api/demo/fail)."""
    normalized = _normalize_provider_name(name)
    _disabled_providers.add(normalized)
    _publish_health(normalized, ok=False, active=False, error="Force disabled by demo")
    logger.info("Provider %s disabled by demo control", normalized)


def enable_provider(name: str) -> None:
    """Re-enable a provider."""
    normalized = _normalize_provider_name(name)
    _disabled_providers.discard(normalized)
    _publish_health(normalized, ok=True, active=True)
    logger.info("Provider %s re-enabled", normalized)


def is_provider_enabled(name: str) -> bool:
    """Check if provider is currently allowed to run."""
    return _normalize_provider_name(name) not in _disabled_providers


def get_all_provider_health() -> dict[str, dict[str, Any]]:
    """Return snapshot of provider health statuses."""
    return dict(_provider_health)


def _normalize_provider_name(name: str) -> str:
    lower = name.lower()
    if "groq" in lower:
        return "Groq"
    if "nemotron" in lower or "nvidia" in lower:
        return "Nemotron"
    return name


# Concurrency limit: maximum 6 concurrent LLM requests
_llm_semaphore = asyncio.Semaphore(6)

_groq_client: Optional[httpx.AsyncClient] = None
_nemotron_client: Optional[httpx.AsyncClient] = None


def _get_groq_client() -> httpx.AsyncClient:
    global _groq_client
    if _groq_client is None or _groq_client.is_closed:
        _groq_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0))
    return _groq_client


def _get_nemotron_client() -> httpx.AsyncClient:
    global _nemotron_client
    if _nemotron_client is None or _nemotron_client.is_closed:
        _nemotron_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0))
    return _nemotron_client


async def _call_groq(prompt: str, system: Optional[str], timeout: float) -> str:
    """Call Groq API using official chat completions endpoint."""
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not set")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 80,
    }

    client = _get_groq_client()
    resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


async def _call_nemotron(prompt: str, system: Optional[str], timeout: float) -> str:
    """Call NVIDIA-hosted Nemotron NIM API."""
    if not settings.nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY is not set")

    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.nvidia_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 80,
    }

    client = _get_nemotron_client()
    resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _clean_json_markdown(text: str) -> str:
    """Strip markdown code fence blocks if returned by the model."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


async def call_llm(
    prompt: str,
    system: Optional[str] = None,
    schema: Optional[Type[BaseModel]] = None,
    timeout: float = 3.0,
) -> Any:
    """
    Calls providers in priority order: Groq -> Nemotron -> rule-based fallback.
    Validates output against schema if provided.
    Falls back gracefully to the next provider on any error or timeout (including immediate on 429).
    Returns deterministic fallback if all providers fail.
    """
    providers = [
        ("Groq", _call_groq),
        ("Nemotron", _call_nemotron),
    ]

    async with _llm_semaphore:
        for name, func in providers:
            if not is_provider_enabled(name):
                continue

            start_time = time.time()
            try:
                logger.debug("Attempting LLM call with provider %s", name)
                raw_text = await func(prompt, system, timeout)
                latency = int((time.time() - start_time) * 1000)

                # If schema validation is required, validate JSON format
                if schema is not None:
                    cleaned = _clean_json_markdown(raw_text)
                    parsed_json = json.loads(cleaned)
                    result = schema.model_validate(parsed_json)
                else:
                    result = raw_text

                # Mark successful provider active
                _publish_health(name, ok=True, active=True)
                _provider_health[name]["latency_ms"] = latency
                return result

            except httpx.HTTPStatusError as exc:
                latency = int((time.time() - start_time) * 1000)
                if exc.response.status_code == 429:
                    logger.warning("Provider %s rate-limited (HTTP 429). Falling back immediately.", name)
                else:
                    logger.warning("Provider %s HTTP error %s: %s", name, exc.response.status_code, exc)
                _publish_health(name, ok=False, active=False, error=f"HTTP {exc.response.status_code}")
                _provider_health[name]["latency_ms"] = latency
                continue
            except Exception as exc:
                latency = int((time.time() - start_time) * 1000)
                logger.warning("Provider %s failed (%s): %s", name, type(exc).__name__, exc)
                _publish_health(name, ok=False, active=False, error=str(exc))
                _provider_health[name]["latency_ms"] = latency
                continue

    logger.error("All LLM providers failed or are disabled. Returning rule-based fallback.")
    if schema is not None:
        try:
            return schema()
        except Exception:
            return schema.model_construct()

    return "Hello, I am calling on behalf of a customer regarding screen replacement."
