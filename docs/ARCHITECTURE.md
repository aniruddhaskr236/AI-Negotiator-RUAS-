# Bhaav (भाव) — System Architecture

> **Autonomous Multilingual Voice Negotiation Agent with Verifiable Evidence Receipts**

---

## 1. High-Level System Overview

Bhaav is an autonomous voice AI agent designed to phone local repair shops simultaneously, converse in the shopkeeper's preferred language (Hindi, Kannada, or English), negotiate prices using verified competing offers, and generate a mathematically weighted, evidence-backed decision report.

```mermaid
flowchart TD
    subgraph Frontend ["Frontend (React 19 + TypeScript + Vite)"]
        UI_Dash["Dashboard (Live Calls & Timeline)"]
        UI_Shop["Shop Simulator / Phone Interface (Audio & Mic)"]
        UI_Rep["Decision Sheet (Weighted Scoring & Evidence)"]
        UI_Check["Pre-Flight System Check"]
    end

    subgraph Gateway ["FastAPI Gateway & Real-Time Bus"]
        HTTP_API["HTTP Endpoints (/api/jobs, /report, /check)"]
        WS_Shop["Shop WebSocket (/ws/shop/{id})"]
        WS_Dash["Dashboard WebSocket (/ws/dashboard/{job_id})"]
        EventBus["Async Pub/Sub Bus (200-event Replay Buffer)"]
    end

    subgraph CoreEngine ["Autonomous Negotiation Core"]
        CallMgr["Call Manager (Parallel Async Loops)"]
        FSM["Negotiation State Machine (6 Phases)"]
        Guard["Safety & Truth Guard (Anti-Hallucination)"]
        Extractor["Entity Extraction & Conflict Detection"]
        Scorer["Weighted Min-Max Scoring Engine"]
    end

    subgraph AIProviders ["Resilient Provider Fallback Chain"]
        LLM_Chain["LLM Chain: Groq (Llama 3.3 70B) ➔ NVIDIA Nemotron ➔ Rules"]
        STT_Chain["STT: Sarvam Saaras ➔ Groq Whisper ➔ Browser Speech"]
        TTS_Chain["TTS: Sarvam Bulbul ➔ Browser SpeechSynthesis"]
    end

    subgraph Persistence ["Dual-Layer Storage"]
        SQLite[("SQLite3 Store (WAL Mode)")]
        MemStore[("In-Memory Backup Cache")]
    end

    UI_Dash <-->|WebSocket / HTTP| Gateway
    UI_Shop <-->|WebSocket Audio| Gateway
    UI_Rep <-->|HTTP| HTTP_API
    UI_Check <-->|HTTP Diagnostic| HTTP_API

    Gateway <--> EventBus
    EventBus <--> CallMgr
    CallMgr --> FSM
    FSM --> Guard
    Guard --> LLM_Chain
    CallMgr --> STT_Chain
    CallMgr --> TTS_Chain
    CallMgr --> Extractor
    Extractor --> Persistence
    CallMgr --> Scorer
    Scorer --> Persistence
    Persistence --- SQLite
    Persistence --- MemStore
```

---

## 2. Real-Time Voice & Audio Pipeline

Every phone call operates with strict time-budget guarantees to prevent dead air and maintain natural conversational cadence.

```mermaid
sequenceDiagram
    autonumber
    actor Shop as Shopkeeper (Browser/Phone)
    participant WS as WebSocket (/ws/shop/{id})
    participant CM as Call Manager
    participant STT as STT Pipeline
    participant AG as Negotiation Agent
    participant TTS as TTS Pipeline
    participant Bus as Event Bus (/ws/dashboard)

    Shop->>WS: Speaks (WebM Audio Chunk / 700ms silence)
    WS->>CM: Forward Base64 Audio
    CM->>STT: Transcribe (Sarvam / Groq Whisper)
    STT-->>CM: Verbatim Text + Language + Confidence Score
    CM->>Bus: Emit "turn" (Shop utterance)

    rect rgb(240, 248, 255)
        Note over CM,AG: Strict Real-Time Budget (< 4.0s Total)
        CM->>AG: Process Turn (FSM + Truth Guard)
        AG->>AG: Enforce Safety (AI Disclosure, No Fake Quotes, <25 Words)
        AG-->>CM: Safe Agent Utterance
    end

    par Parallel TTS & Bus Broadcast
        CM->>TTS: Synthesize Audio (Timeout: 1.2s)
        CM->>Bus: Emit "turn" (Agent reply)
    end

    alt TTS finishes within 1.2s
        TTS-->>CM: Audio Base64 (MP3)
        CM->>WS: Send {"type": "agent_audio", "data": "..."} FIRST
        CM->>WS: Send {"type": "agent_text", "text": "..."}
    else TTS timed out or unavailable
        CM->>WS: Send {"type": "agent_text", "text": "..."} only (Browser voices it)
    end
    Shop->>Shop: Hear response / View transcript
```

---

## 3. Negotiation State Machine (FSM)

The agent moves strictly through six deterministic states, preventing loops and infinite negotiations:

```mermaid
stateDiagram-v2
    [*] --> GREET: Call Connected
    GREET --> COLLECT: AI Disclosure + Stating Customer Need
    COLLECT --> PROBE: First Price Collected
    COLLECT --> COLLECT: Evasive response / Request clarification
    PROBE --> COUNTER: Details captured (Warranty, Part Type, Turnaround)
    COUNTER --> DECIDE: Leverage lowest competing quote
    COUNTER --> PROBE: Shop shifts quote / Introduces new terms
    DECIDE --> CLOSE: Conclude without committing to buy
    CLOSE --> [*]: Hang up gracefully
```

### State Definitions & Constraints:
1. **GREET:** Introduces the AI caller clearly: *"Hello, I am Bhaav, an AI assistant calling on behalf of a customer in Bengaluru."*
2. **COLLECT:** Asks for initial diagnostic quote and timeline for the specific phone model and issue.
3. **PROBE:** Inquires about part authenticity (OEM vs Aftermarket), warranty duration, and turnaround time.
4. **COUNTER:** Pushes back with actual verified lower quotes from competing shops in the current session.
5. **DECIDE:** Summarizes the final terms without ever committing the customer to buy.
6. **CLOSE:** Politely thanks the shopkeeper, concludes the call, and records final receipts.

---

## 4. Anti-Hallucination & Safety Guardrails

```mermaid
flowchart LR
    TurnInput[Shop Utterance] --> Parse[Extract Numbers & Terms]
    Parse --> ConflictCheck{Discrepancy with earlier offer?}
    ConflictCheck -- Yes --> FlagConflict[Emit Conflict Event to Dashboard]
    FlagConflict --> PromptConfirm[Agent asks Shop to confirm change]
    ConflictCheck -- No --> QuoteCheck{Cite Competing Quote?}
    QuoteCheck -- Yes --> StoreLookup[Verify session quotes in SQLite]
    StoreLookup --> CiteVerified[Cite lowest ACTUAL quote]
    QuoteCheck -- No --> DirectReply[Proceed with FSM]
    CiteVerified --> SafePrompt[LLM Response Template]
    PromptConfirm --> SafePrompt
    DirectReply --> SafePrompt
    SafePrompt --> StrictLength[Word Cap: <= 25 words]
    StrictLength --> OutputUtterance[Send to Shop]
```

- **Rule 1 (AI Disclosure):** The caller explicitly states it is an AI assistant on the opening turn.
- **Rule 2 (Receipt-Backed Counters):** The agent **never** invents prices. It strictly queries verified quotes recorded in `store.py` for the current job session.
- **Rule 3 (No Purchase Commitment):** The agent never accepts or finalizes a purchase, only gathers offers for the customer.
- **Rule 4 (Contradiction Detection):** If a shopkeeper changes price (e.g. from ₹4500 to ₹3800, or vice versa), a `conflict` event is broadcast and the agent prompts confirmation.

---

## 5. Multi-Provider Fallback Architecture

To survive hackathon rate limits and API outages, Bhaav implements an asynchronous tiered fallback:

```mermaid
graph TD
    subgraph LLMExecution ["LLM Generation Pipeline"]
        A[Agent Utterance Request] --> B{Groq API<br/>Llama 3.3 70B<br/>3s timeout}
        B -- Success --> Z[Return Generated Text]
        B -- 429 / Timeout / Error --> C{NVIDIA Nemotron API<br/>3.5 Lightning 30B<br/>3s timeout}
        C -- Success --> Z
        C -- 429 / Timeout / Error --> D[Rule-Based FSM Fallback Templates]
        D --> Z
    end

    subgraph SpeechExecution ["Speech Recognition Pipeline"]
        S1[Audio WebM Chunk] --> S2{Sarvam Saaras STT<br/>2s timeout}
        S2 -- Success --> S_OUT[Transcribed Text]
        S2 -- Error / Unavailable --> S3{Groq Whisper Large v3<br/>2s timeout}
        S3 -- Success --> S_OUT
        S3 -- Error / Unavailable --> S4[Browser Web Speech API Fallback]
        S4 --> S_OUT
    end
```

---

## 6. Mathematical Scoring Engine

The recommendation report evaluates each shop $i$ using a weighted normalized score:

$$
\text{Score}_i = \left( w_{\text{price}} \cdot S_{\text{price}, i} \right) + \left( w_{\text{warranty}} \cdot S_{\text{warranty}, i} \right) + \left( w_{\text{speed}} \cdot S_{\text{speed}, i} \right) + \left( w_{\text{quality}} \cdot S_{\text{quality}, i} \right)
$$

Where weights sum to $100$ ($w_p + w_w + w_s + w_q = 100$), and normalized sub-scores ($0 \le S \le 100$) are calculated as:

- **Price Score:** 
  $$S_{\text{price}, i} = \frac{\min_{j} (\text{Price}_j)}{\text{Price}_i} \times 100$$
- **Warranty Score:** 
  $$S_{\text{warranty}, i} = \frac{\min(\text{WarrantyMonths}_i, 6)}{6} \times 100$$
- **Speed Score:** 
  $$S_{\text{speed}, i} = \frac{1}{\text{ETADays}_i} \times 100$$
- **Part Quality Score:** 
  $$\text{OEM} \to 100, \quad \text{Aftermarket} \to 60, \quad \text{Unknown} \to 0$$

Failed calls (no answer or hangup before first quote) receive a score of $0.0$.
