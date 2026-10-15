"""
Offer extraction from dialogue turns and conflict detection between turns.

Design decision: Regex-first rule extraction operates with 0ms LLM latency and
stores precise turn timestamps as evidence. Discrepancies between turns trigger
ConflictEvents so contradictions are flagged and confirmed with the shop.
"""

from typing import List, Optional

from backend.models import ConflictEvent, Offer, Turn
from backend.normalize import (
    parse_conditions,
    parse_days,
    parse_months,
    parse_part_type,
    parse_price,
)


def extract_offer(turns: List[Turn], call_id: Optional[str] = None) -> Offer:
    """
    Extracts structured offer details from dialogue turns with supporting evidence.
    Tracks first_price vs final agreed price and records timestamp evidence for each figure.
    """
    if not turns:
        cid = call_id or "unknown"
        return Offer(call_id=cid)

    cid = call_id or turns[0].call_id

    first_price: Optional[int] = None
    latest_price: Optional[int] = None
    warranty_months: Optional[int] = None
    eta_days: Optional[int] = None
    part_type: str = "Unknown"
    conditions_list: List[str] = []
    evidence: dict = {}
    confidences: List[float] = []

    for turn in turns:
        # Shop statements provide the authoritative quotes
        if turn.speaker == "shop":
            # 1. Price
            p, conf_p = parse_price(turn.text)
            if p is not None:
                if first_price is None:
                    first_price = p
                latest_price = p
                confidences.append(conf_p)
                evidence["price"] = {
                    "turn_ts": turn.ts,
                    "text": turn.text,
                    "translation": turn.translation,
                    "lang": turn.lang,
                    "audio_url": None,
                }

            # 2. Warranty
            w, conf_w = parse_months(turn.text)
            if w is not None:
                warranty_months = w
                confidences.append(conf_w)
                evidence["warranty"] = {
                    "turn_ts": turn.ts,
                    "text": turn.text,
                    "translation": turn.translation,
                    "lang": turn.lang,
                    "audio_url": None,
                }

            # 3. ETA / Days
            d, conf_d = parse_days(turn.text)
            if d is not None:
                eta_days = d
                confidences.append(conf_d)
                evidence["eta"] = {
                    "turn_ts": turn.ts,
                    "text": turn.text,
                    "translation": turn.translation,
                    "lang": turn.lang,
                    "audio_url": None,
                }

            # 4. Part Type
            pt, conf_pt = parse_part_type(turn.text)
            if pt != "Unknown":
                part_type = pt
                confidences.append(conf_pt)
                evidence["part_type"] = {
                    "turn_ts": turn.ts,
                    "text": turn.text,
                    "translation": turn.translation,
                    "lang": turn.lang,
                    "audio_url": None,
                }

            # 5. Conditions
            cond = parse_conditions(turn.text)
            if cond and cond not in conditions_list:
                conditions_list.append(cond)

    overall_confidence = (
        round(sum(confidences) / len(confidences), 2) if confidences else 1.0
    )

    return Offer(
        call_id=cid,
        price=latest_price,
        first_price=first_price,
        warranty_months=warranty_months,
        eta_days=eta_days,
        part_type=part_type,
        conditions=", ".join(conditions_list) if conditions_list else "",
        confidence=overall_confidence,
        evidence=evidence,
    )


def detect_conflicts(
    old_offer: Optional[Offer], new_offer: Offer, current_turn_ts: float
) -> List[ConflictEvent]:
    """
    Detects contradictions between established quotes and new quotes.
    E.g., if price changes mid-call or warranty is reduced.
    """
    conflicts: List[ConflictEvent] = []
    if not old_offer:
        return conflicts

    # 1. Price conflict
    if (
        old_offer.price is not None
        and new_offer.price is not None
        and old_offer.price != new_offer.price
    ):
        old_ts = (
            old_offer.evidence.get("price", {}).get("turn_ts", current_turn_ts)
            if old_offer.evidence
            else current_turn_ts
        )
        conflicts.append(
            ConflictEvent(
                call_id=new_offer.call_id,
                field="price",
                old_value=str(old_offer.price),
                new_value=str(new_offer.price),
                old_ts=old_ts,
                new_ts=current_turn_ts,
            )
        )

    # 2. Warranty conflict
    if (
        old_offer.warranty_months is not None
        and new_offer.warranty_months is not None
        and old_offer.warranty_months != new_offer.warranty_months
    ):
        old_ts = (
            old_offer.evidence.get("warranty", {}).get("turn_ts", current_turn_ts)
            if old_offer.evidence
            else current_turn_ts
        )
        conflicts.append(
            ConflictEvent(
                call_id=new_offer.call_id,
                field="warranty_months",
                old_value=f"{old_offer.warranty_months} months",
                new_value=f"{new_offer.warranty_months} months",
                old_ts=old_ts,
                new_ts=current_turn_ts,
            )
        )

    return conflicts
