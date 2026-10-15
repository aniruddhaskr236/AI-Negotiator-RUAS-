"""
Pydantic data models for Bhaav.

Design decision: Exact field-name matching against docs/SPEC.md contract.
Pydantic v2 ensures fast serialization and strict validation for both HTTP
and WebSocket payloads.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core Weights & Sub-models
# ---------------------------------------------------------------------------

class Weights(BaseModel):
    """User-configured prioritization weights summing to 100."""
    price: int = Field(default=40, ge=0, le=100)
    warranty: int = Field(default=25, ge=0, le=100)
    speed: int = Field(default=20, ge=0, le=100)
    quality: int = Field(default=15, ge=0, le=100)


class EvidenceItem(BaseModel):
    """Evidence pointing back to the exact transcript turn."""
    turn_ts: float
    text: str
    translation: Optional[str] = None
    lang: str = "en"
    audio_url: Optional[str] = None


class RecommendedShop(BaseModel):
    call_id: str
    shop_name: str
    reason: str


class ReportRow(BaseModel):
    call_id: str
    shop_name: str
    rank: int
    score: float
    first_price: Optional[int] = None
    final_price: Optional[int] = None
    saving: Optional[int] = None
    warranty_months: Optional[int] = None
    eta_days: Optional[int] = None
    part_type: Optional[str] = None  # OEM | Aftermarket | Unknown
    conditions: Optional[str] = None
    evidence: Dict[str, EvidenceItem] = Field(default_factory=dict)


class OtherShop(BaseModel):
    call_id: str
    why_not: str


class TimelineEvent(BaseModel):
    call_id: Optional[str] = None
    text: str
    ts: float


# ---------------------------------------------------------------------------
# HTTP Request & Response Models
# ---------------------------------------------------------------------------

class JobCreateRequest(BaseModel):
    need: str
    weights: Optional[Weights] = Field(default_factory=Weights)


class CallSummary(BaseModel):
    call_id: str
    shop_id: str
    shop_name: str
    lang: str = "en"


class JobCreateResponse(BaseModel):
    job_id: str
    calls: List[CallSummary]


class OkResponse(BaseModel):
    ok: bool = True


class CheckItem(BaseModel):
    name: str
    ok: bool
    latency_ms: int
    detail: str


class CheckResponse(BaseModel):
    checks: List[CheckItem]


class DemoFailRequest(BaseModel):
    kind: Literal["hangup", "price_change", "kill_provider", "unclear_audio"]
    call_id: Optional[str] = None


class Report(BaseModel):
    job_id: str
    recommended: Optional[RecommendedShop] = None
    weights: Weights
    rows: List[ReportRow] = Field(default_factory=list)
    others: List[OtherShop] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Storage Models
# ---------------------------------------------------------------------------

class Job(BaseModel):
    job_id: str
    need: str
    weights: Weights
    created_at: float


class Call(BaseModel):
    call_id: str
    job_id: str
    shop_id: str
    shop_name: str
    lang: str = "en"
    status: Literal["idle", "ringing", "talking", "done", "failed", "retrying"] = "idle"
    error: Optional[str] = None


class Turn(BaseModel):
    call_id: str
    speaker: Literal["agent", "shop"]
    text: str
    translation: Optional[str] = None
    lang: Literal["en", "hi", "kn"] = "en"
    ts: float
    confidence: Optional[float] = 1.0


class Offer(BaseModel):
    call_id: str
    price: Optional[int] = None
    first_price: Optional[int] = None
    warranty_months: Optional[int] = None
    eta_days: Optional[int] = None
    part_type: Optional[str] = "Unknown"  # OEM | Aftermarket | Unknown
    conditions: Optional[str] = ""
    confidence: Optional[float] = 1.0
    evidence: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# WebSocket Shop Messages (Contract compliant)
# ---------------------------------------------------------------------------

class RingMessage(BaseModel):
    type: Literal["ring"] = "ring"
    call_id: str
    caller: str = "AI assistant calling for a customer"


class AgentTextMessage(BaseModel):
    type: Literal["agent_text"] = "agent_text"
    call_id: str
    text: str
    lang: str = "en"


class AgentAudioMessage(BaseModel):
    type: Literal["agent_audio"] = "agent_audio"
    call_id: str
    mime: str = "audio/mpeg"
    data: str  # base64 encoded


class EndMessage(BaseModel):
    type: Literal["end"] = "end"
    call_id: str


# ---------------------------------------------------------------------------
# WebSocket Dashboard Events (Contract compliant)
# ---------------------------------------------------------------------------

class CallStatusEvent(BaseModel):
    type: Literal["call_status"] = "call_status"
    call_id: str
    status: Literal["idle", "ringing", "talking", "done", "failed", "retrying"]
    error: Optional[str] = None


class TurnEvent(BaseModel):
    type: Literal["turn"] = "turn"
    call_id: str
    speaker: Literal["agent", "shop"]
    text: str
    translation: Optional[str] = None
    lang: Literal["en", "hi", "kn"] = "en"
    ts: float
    confidence: Optional[float] = 1.0


class OfferEvent(BaseModel):
    type: Literal["offer"] = "offer"
    call_id: str
    price: Optional[int] = None
    first_price: Optional[int] = None
    warranty_months: Optional[int] = None
    eta_days: Optional[int] = None
    part_type: Optional[str] = "Unknown"
    conditions: Optional[str] = ""
    confidence: Optional[float] = 1.0
    evidence: Dict[str, Any] = Field(default_factory=dict)


class ConflictEvent(BaseModel):
    type: Literal["conflict"] = "conflict"
    call_id: str
    field: str
    old_value: str
    new_value: str
    old_ts: float
    new_ts: float


class HealthEvent(BaseModel):
    type: Literal["health"] = "health"
    provider: str
    ok: bool
    active: bool


class ReportReadyEvent(BaseModel):
    type: Literal["report_ready"] = "report_ready"
    job_id: str
