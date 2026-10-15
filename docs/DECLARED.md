# Bhaav — Declared Dependencies & Integrations

This document declares all external APIs, models, schemas, and dependencies utilized across Bhaav.

---

## 1. External AI Providers & Endpoints

| Provider | Purpose | Model Name | Endpoint URL | Fallback Order |
|---|---|---|---|---|
| **Groq** | Primary LLM | `llama-3.3-70b-versatile` | `https://api.groq.com/openai/v1/chat/completions` | Primary (3s timeout) |
| **NVIDIA NIM** | Secondary LLM | `nvidia/nemotron-3.5-lightning-30b-a3b` | `https://integrate.api.nvidia.com/v1/chat/completions` | Secondary (3s timeout) |
| **Rule Engine** | Offline LLM Fallback | Pure Python Templates | Local in-memory | Tertiary (immediate) |
| **Sarvam AI** | Regional STT | `saaras:v2` | `https://api.sarvam.ai/speech-to-text` | Primary STT |
| **Groq** | Whisper STT | `whisper-large-v3` | `https://api.groq.com/openai/v1/audio/transcriptions` | Secondary STT |
| **Sarvam AI** | Regional TTS | `bulbul:v3` | `https://api.sarvam.ai/text-to-speech` | Primary TTS (1.2s budget) |
| **Web Speech API** | Client Speech | Browser Native (`SpeechSynthesis`) | Local client browser | Final audio fallback |

---

## 2. Core Python Dependencies

All packages are pinned in `backend/requirements.txt`:

```text
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.10.0
httpx>=0.28.0
python-multipart>=0.0.18
websockets>=13.1
pytest>=8.3.0
pytest-asyncio>=0.24.0
```

*Note: No heavy ORMs (pure SQLite3 with standard library), no vector databases, no bloated dependencies.*

---

## 3. Frontend Stack

- **Framework:** React 19 + TypeScript + Vite 8
- **Styling:** TailwindCSS v4 with industrial print-inspired design system
- **Routing:** React Router v7 (`createBrowserRouter`)
- **WebSockets:** Native Reconnecting WebSocket client with 25s keepalive ping
- **Typography:** JetBrains Mono, Archivo Black, Noto Sans Devanagari, Noto Sans Kannada

---

## 4. Concurrency & Rate Limiting Declarations

- **LLM Semaphore:** `asyncio.Semaphore(6)` — Limits concurrent outbound LLM requests to prevent account rate limits.
- **STT Semaphore:** `asyncio.Semaphore(3)` — Limits concurrent audio transcription requests.
- **Connection Pools:** Persistent `httpx.AsyncClient` instances per provider with connection reuse and keepalive.
