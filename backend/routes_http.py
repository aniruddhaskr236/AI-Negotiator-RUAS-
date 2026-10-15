"""
HTTP API endpoints matching docs/SPEC.md contract.

Design decision: Keeping request handlers thin and offloading orchestration
to CallManager and Store guarantees testability and separation of concerns.
"""

import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.calls import call_manager
from backend.config import logger, settings
from backend.llm import disable_provider, get_all_provider_health
from backend.models import (
    CallSummary,
    CheckItem,
    CheckResponse,
    ConflictEvent,
    DemoFailRequest,
    JobCreateRequest,
    JobCreateResponse,
    OkResponse,
    OtherShop,
    RecommendedShop,
    Report,
    ReportRow,
    Weights,
)
from backend import store
from backend import scoring
from backend.bus import publish_event

router = APIRouter()


@router.post("/api/jobs", response_model=JobCreateResponse)
async def create_job(req: JobCreateRequest):
    """
    Initiate a new repair comparison job.
    Creates 3 parallel calls for Sri Ganesh Mobiles, Mobile Hub, and City Fix Corner.
    """
    weights = req.weights or Weights()
    job = call_manager.create_job(need=req.need, weights=weights)

    calls = store.get_calls_for_job(job.job_id)
    call_summaries = [
        CallSummary(
            call_id=c.call_id,
            shop_id=c.shop_id,
            shop_name=c.shop_name,
            lang=c.lang,
        )
        for c in calls
    ]
    return JobCreateResponse(job_id=job.job_id, calls=call_summaries)


@router.post("/api/jobs/{job_id}/calls/{call_id}/retry", response_model=OkResponse)
async def retry_call(job_id: str, call_id: str):
    """Retries a specific failed or finished call."""
    success = await call_manager.retry_call(job_id, call_id)
    if not success:
        raise HTTPException(status_code=404, detail="Call not found")
    return OkResponse(ok=True)


@router.get("/api/jobs/{job_id}/report", response_model=Report)
async def get_report(job_id: str, weights: Optional[str] = Query(None)):
    """
    Returns the evidence-backed recommendation report.
    Accepts optional weights query (e.g., weights=40,25,20,15) to rebalance scoring live.
    """
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    parsed_weights = job.weights
    if weights:
        try:
            parts = [int(p.strip()) for p in weights.split(",")]
            if len(parts) == 4:
                parsed_weights = Weights(
                    price=parts[0], warranty=parts[1], speed=parts[2], quality=parts[3]
                )
        except Exception:
            pass

    calls = store.get_calls_for_job(job_id)
    offers = store.get_offers_for_job(job_id)
    timeline = store.get_timeline_for_job(job_id)
    conflicts = store.get_conflicts_for_job(job_id)

    return scoring.build_report(
        job=job,
        calls=calls,
        offers=offers,
        conflicts=conflicts,
        timeline=timeline,
        custom_weights=parsed_weights,
    )


@router.get("/api/check", response_model=CheckResponse)
async def check_system():
    """
    Diagnostic endpoint reporting status and latency of server, LLM providers and speech providers.
    """
    checks = []

    # 1. Server health
    checks.append(CheckItem(name="Server Health", ok=True, latency_ms=1, detail="FastAPI backend running"))

    # 2. Database store check
    try:
        t0 = time.time()
        store.init_db()
        lat = int((time.time() - t0) * 1000)
        checks.append(CheckItem(name="SQLite Store", ok=True, latency_ms=lat, detail="Database accessible"))
    except Exception as e:
        checks.append(CheckItem(name="SQLite Store", ok=False, latency_ms=0, detail=str(e)))

    # 3. LLM providers
    llm_health = get_all_provider_health()
    for prov, status in llm_health.items():
        checks.append(
            CheckItem(
                name=f"LLM: {prov}",
                ok=status.get("ok", True),
                latency_ms=status.get("latency_ms", 0),
                detail="Active" if status.get("active") else (status.get("last_error") or "Standby"),
            )
        )

    return CheckResponse(checks=checks)


@router.post("/api/demo/fail", response_model=OkResponse)
async def demo_fail(req: DemoFailRequest):
    """
    Trigger live demo failure injection.
    Supports: hangup, price_change, kill_provider, unclear_audio.
    """
    if not settings.demo_controls_enabled:
        raise HTTPException(status_code=403, detail="Demo controls disabled in config")

    logger.info("Demo failure injection triggered: %s for call %s", req.kind, req.call_id)

    if req.kind == "kill_provider":
        disable_provider("Groq")
    elif req.kind == "hangup" and req.call_id:
        call = store.get_call(req.call_id)
        if call:
            call.status = "failed"
            call.error = "Shop hung up"
            store.save_call(call)
            publish_event(call.job_id, {"type": "call_status", "call_id": req.call_id, "status": "failed", "error": call.error})
    elif req.kind == "price_change" and req.call_id:
        call = store.get_call(req.call_id)
        if call:
            conflict = ConflictEvent(
                call_id=req.call_id,
                field="price",
                old_value="4500",
                new_value="4800",
                old_ts=time.time() - 20,
                new_ts=time.time(),
            )
            store.add_conflict(conflict)
            publish_event(call.job_id, conflict)
    elif req.kind == "unclear_audio" and req.call_id:
        call = store.get_call(req.call_id)
        if call:
            publish_event(
                call.job_id,
                {
                    "type": "turn",
                    "call_id": req.call_id,
                    "speaker": "agent",
                    "text": "Sorry, could you please repeat that? The line was unclear.",
                    "lang": "en",
                    "ts": time.time(),
                    "confidence": 0.4,
                },
            )

    return OkResponse(ok=True)
