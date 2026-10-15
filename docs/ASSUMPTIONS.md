# Bhaav — Hackathon Design Decisions & Assumptions

This document records all explicit engineering assumptions and trade-offs made during the 8-hour hackathon implementation.

---

## 1. Concurrency & Event Bus
- **Assumption:** In-memory async pub/sub is sufficient for a single-node deployment (e.g. Render Web Service with single worker).
- **Design Decision:** The event bus maintains a 200-event ring buffer per job. When a client reconnects or a second browser opens the dashboard, the replay buffer instantly synchronizes the state without querying SQLite repeatedly.

## 2. Audio Ordering & Low Latency
- **Assumption:** Waiting too long for neural TTS introduces unacceptable dead air during live telephone calls.
- **Design Decision:** The agent enforces a strict **1.2-second budget** for server-side TTS. If the TTS provider finishes within 1.2s, the server sends `agent_audio` FIRST, followed immediately by `agent_text`. If the TTS exceeds 1.2s or fails, only `agent_text` is transmitted, and the shopkeeper's browser speaks it locally using the Web Speech API. Audio is never sent after text.

## 3. Anti-Hallucination Mechanism
- **Assumption:** LLMs cannot be trusted to self-police numerical claims during competitive negotiation.
- **Design Decision:** The LLM prompt is strictly constrained by a deterministic Python guard (`agent.py`). Competing quotes are injected directly from SQLite session records. If no competing quote exists, the agent is strictly prohibited from citing any price.

## 4. Multi-Language Audio Normalization
- **Assumption:** Shopkeepers in Bengaluru switch fluidly between English, Hindi, and Kannada, often mixing number words (e.g. "teen hazaar paanch sau", "four thousand five hundred", "nālku sāvira").
- **Design Decision:** `backend/normalize.py` implements a hybrid parser supporting digit strings, English word forms, Hindi numerals, and Kannada phrases. Extracted values are normalized into canonical integer rupee amounts.

## 5. Storage Durability
- **Assumption:** Disk I/O failures or temporary file locks on cloud instances must not crash active calls.
- **Design Decision:** `backend/store.py` utilizes SQLite with WAL mode (`PRAGMA journal_mode=WAL;`), complemented by an in-memory dictionary backup. If a disk write fails, the in-memory cache preserves all call turns and offers without downtime.
