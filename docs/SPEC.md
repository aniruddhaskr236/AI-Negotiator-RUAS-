# Bhaav: Shared Contract (SPEC)

## Scoping lines (locked at the checkpoint)

- **User:** A student or young professional in Bengaluru who needs a phone screen replacement and has to call several repair shops one by one.
- **What breaks today:** Each call takes 10-15 minutes, quotes aren't comparable (price, warranty, part quality, time), and she ends up accepting the first price without negotiating.

## HTTP endpoints

| Method | Path | Body / Response |
|---|---|---|
| GET | `/health` | `{ "ok": true }` |
| POST | `/api/jobs` | Body `{ "need": "...", "weights": { "price": 40, "warranty": 25, "speed": 20, "quality": 15 } }`. Returns `{ "job_id": "...", "calls": [{ "call_id": "...", "shop_id": "1", "shop_name": "...", "lang": "en" }] }` |
| POST | `/api/jobs/{job_id}/calls/{call_id}/retry` | Returns `{ "ok": true }` |
| GET | `/api/jobs/{job_id}/report?weights=40,25,20,15` | Returns the Report object below |
| GET | `/api/check` | Returns `{ "checks": [{ "name": "...", "ok": true, "latency_ms": 12, "detail": "..." }] }` for server health, each LLM provider and each speech provider |
| POST | `/api/demo/fail` | Body `{ "kind": "hangup" | "price_change" | "kill_provider" | "unclear_audio", "call_id": "..." }` |

## WebSocket: shop page `/ws/shop/{shop_id}`

Server to shop:
- `{ "type":"ring", "call_id": "...", "caller":"AI assistant calling for a customer" }`
- `{ "type":"agent_text", "call_id": "...", "text": "...", "lang": "..." }`  (shop page speaks this with browser speech; if present, also plays `agent_audio`)
- `{ "type":"agent_audio", "call_id": "...", "mime":"audio/mpeg", "data":"<base64>" }`
- `{ "type":"end", "call_id": "..." }`

Shop to server:
- `{ "type":"answer", "call_id": "..." }`
- `{ "type":"audio", "call_id": "...", "mime":"audio/webm", "data":"<base64>", "ts": 123.4 }` (one message per spoken utterance)
- `{ "type":"text", "call_id": "...", "text": "..." }` (typed fallback)
- `{ "type":"hangup", "call_id": "..." }`
- `{ "type":"ping" }`

## WebSocket: dashboard `/ws/dashboard/{job_id}`

Server to dashboard:
- `{ "type":"call_status", "call_id": "...", "status":"idle|ringing|talking|done|failed|retrying", "error": "..." }`
- `{ "type":"turn", "call_id": "...", "speaker":"agent|shop", "text": "...", "translation": "...", "lang":"en|hi|kn", "ts": 123.4, "confidence": 0.95 }`
- `{ "type":"offer", "call_id": "...", "price": 3800, "first_price": 4500, "warranty_months": 6, "eta_days": 1, "part_type": "OEM", "conditions": "GST extra", "confidence": 0.9, "evidence": { "turn_ts": 123.4 } }`
- `{ "type":"conflict", "call_id": "...", "field": "price", "old_value": "4500", "new_value": "3800", "old_ts": 100.1, "new_ts": 123.4 }`
- `{ "type":"timeline", "call_id": "...", "text": "...", "ts": 123.4 }`
- `{ "type":"health", "provider": "Groq", "ok": true, "active": true }`
- `{ "type":"report_ready", "job_id": "..." }`

Dashboard to server: `{ "type":"ping" }`

## Report object

```json
{
  "job_id": "j1",
  "recommended": { "call_id": "c1", "shop_name": "Sri Ganesh Mobiles", "reason": "..." },
  "weights": { "price": 40, "warranty": 25, "speed": 20, "quality": 15 },
  "rows": [
    {
      "call_id": "c1", "shop_name": "...", "rank": 1, "score": 0.82,
      "first_price": 4500, "final_price": 3800, "saving": 700,
      "warranty_months": 6, "eta_days": 1, "part_type": "OEM", "conditions": "GST extra",
      "evidence": {
        "price": { "turn_ts": 123.4, "text": "...", "translation": "...", "lang": "hi", "audio_url": null },
        "warranty": { "turn_ts": 150.2, "text": "...", "translation": null, "lang": "en", "audio_url": null }
      }
    }
  ],
  "others": [ { "call_id": "c2", "why_not": "One sentence trade-off" } ],
  "caveats": [ "Shop 2 did not confirm GST", "Shop 3 did not answer" ],
  "timeline": [ { "ts": 60.1, "text": "Shop 1 dropped 4500 to 4200 after agent cited another quote" } ]
}
```

## Safety rules (enforced in code)

1. Every call opens by saying the caller is an AI assistant calling for a named customer.
2. The agent only cites quotes actually collected in this session. It never invents a competing price.
3. The agent never commits the user to buy anything.
4. Contradictions are detected and flagged, and the agent asks the shop to confirm.
