"""
Environment check and provider connectivity diagnostic script.

Hard rule: NEVER prints or reveals API key values. Only indicates presence (SET / NOT SET)
and ping latencies.
"""

import asyncio
import os
import sys
import time
import httpx

# Add parent directory to path so backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.config import settings


async def ping_groq() -> tuple[bool, int, str]:
    """Test Groq API connectivity with a minimal completion."""
    if not settings.groq_api_key:
        return False, 0, "GROQ_API_KEY not set"
    t0 = time.time()
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": settings.groq_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            lat = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return True, lat, "OK"
            return False, lat, f"HTTP {resp.status_code}"
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return False, lat, f"Error: {e}"


async def ping_mistral() -> tuple[bool, int, str]:
    """Test Mistral API connectivity with a minimal completion."""
    if not settings.mistral_api_key:
        return False, 0, "MISTRAL_API_KEY not set"
    t0 = time.time()
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.mistral_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": settings.mistral_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            lat = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return True, lat, "OK"
            return False, lat, f"HTTP {resp.status_code}"
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return False, lat, f"Error: {e}"


async def ping_nvidia() -> tuple[bool, int, str]:
    """Test NVIDIA Nemotron NIM API connectivity with a minimal completion."""
    if not settings.nvidia_api_key:
        return False, 0, "NVIDIA_API_KEY not set"
    t0 = time.time()
    try:
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.nvidia_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": settings.nvidia_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            lat = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return True, lat, "OK"
            return False, lat, f"HTTP {resp.status_code}"
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return False, lat, f"Error: {e}"


async def ping_sarvam() -> tuple[bool, int, str]:
    """Test Sarvam API connectivity with a minimal translation call."""
    if not settings.sarvam_api_key:
        return False, 0, "SARVAM_API_KEY not set"
    t0 = time.time()
    try:
        url = "https://api.sarvam.ai/translate"
        headers = {"api-subscription-key": settings.sarvam_api_key, "Content-Type": "application/json"}
        payload = {
            "input": "test",
            "source_language_code": "en-IN",
            "target_language_code": "hi-IN",
            "model": settings.sarvam_translate_model,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            lat = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return True, lat, "OK"
            return False, lat, f"HTTP {resp.status_code}"
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return False, lat, f"Error: {e}"


async def main():
    print("=" * 65)
    print(" BHAAV SYSTEM & API KEY DIAGNOSTIC")
    print("=" * 65)
    print(f"{'Provider':<15} | {'Key Status':<12} | {'Ping Status':<12} | {'Latency':<8} | {'Detail'}")
    print("-" * 65)

    checks = [
        ("Groq", bool(settings.groq_api_key), ping_groq),
        ("Mistral", bool(settings.mistral_api_key), ping_mistral),
        ("NVIDIA", bool(settings.nvidia_api_key), ping_nvidia),
        ("Sarvam", bool(settings.sarvam_api_key), ping_sarvam),
    ]

    for name, is_set, ping_func in checks:
        key_str = "SET" if is_set else "NOT SET"
        if is_set:
            ok, lat, detail = await ping_func()
            ping_str = "SUCCESS" if ok else "FAILED"
            lat_str = f"{lat}ms"
        else:
            ping_str = "SKIPPED"
            lat_str = "-"
            detail = "Key missing in environment"

        print(f"{name:<15} | {key_str:<12} | {ping_str:<12} | {lat_str:<8} | {detail}")

    print("-" * 65)
    print(f"Database Path : {settings.db_path}")
    print(f"Scripted Shops: {'ENABLED' if settings.scripted_shops else 'DISABLED'}")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
