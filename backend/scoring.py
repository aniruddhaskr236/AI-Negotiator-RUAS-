"""
Weighted min-max scoring engine and evidence-backed report generator.

Design decision: Multi-criteria decision analysis (MCDA) with min-max normalization
allows objective ranking across conflicting dimensions (price vs warranty vs quality vs speed)
weighted by customer preference, linking every conclusion directly to dialogue evidence.
"""

from typing import Dict, List, Optional

from backend.models import (
    Call,
    ConflictEvent,
    EvidenceItem,
    Job,
    Offer,
    OtherShop,
    RecommendedShop,
    Report,
    ReportRow,
    TimelineEvent,
    Weights,
)

# Part quality numerical weights
_PART_QUALITY_SCORES = {
    "OEM": 1.0,
    "Aftermarket": 0.6,
    "Unknown": 0.2,
}


def _min_max_norm(val: float, min_val: float, max_val: float, higher_is_better: bool = True) -> float:
    """Normalize value between 0.0 and 1.0."""
    if max_val == min_val:
        return 1.0
    if higher_is_better:
        return (val - min_val) / (max_val - min_val)
    else:
        return (max_val - val) / (max_val - min_val)


def build_report(
    job: Job,
    calls: List[Call],
    offers: Dict[str, Offer],
    conflicts: List[ConflictEvent],
    timeline: List[TimelineEvent],
    custom_weights: Optional[Weights] = None,
) -> Report:
    """
    Computes weighted min-max scores and builds the complete evidence-backed Report object.
    """
    weights = custom_weights or job.weights
    total_weight = weights.price + weights.warranty + weights.speed + weights.quality
    if total_weight == 0:
        total_weight = 100

    # Separate successful offers from failed/incomplete calls
    valid_candidates = []
    caveats = []

    for c in calls:
        if c.status == "failed":
            caveats.append(f"{c.shop_name} did not complete: {c.error or 'no response'}")
            continue

        off = offers.get(c.call_id)
        if not off or off.price is None:
            caveats.append(f"{c.shop_name} did not provide a firm price quote")
            continue

        valid_candidates.append((c, off))

    # Add conflict caveats
    for conf in conflicts:
        caveats.append(
            f"Discrepancy detected for {conf.field}: changed from {conf.old_value} to {conf.new_value}"
        )

    if not valid_candidates:
        return Report(
            job_id=job.job_id,
            recommended=None,
            weights=weights,
            rows=[],
            others=[],
            caveats=caveats,
            timeline=timeline,
        )

    # Determine min/max values across valid candidates
    prices = [off.price for _, off in valid_candidates if off.price is not None]
    warranties = [off.warranty_months or 0 for _, off in valid_candidates]
    etas = [off.eta_days if off.eta_days is not None else 3 for _, off in valid_candidates]

    min_p, max_p = min(prices), max(prices)
    min_w, max_w = min(warranties), max(warranties)
    min_e, max_e = min(etas), max(etas)

    scored_rows = []
    for call, off in valid_candidates:
        p_val = off.price or max_p
        w_val = off.warranty_months or 0
        e_val = off.eta_days if off.eta_days is not None else 3
        q_val = _PART_QUALITY_SCORES.get(off.part_type or "Unknown", 0.2)

        s_price = _min_max_norm(p_val, min_p, max_p, higher_is_better=False)
        s_warranty = _min_max_norm(w_val, min_w, max_w, higher_is_better=True)
        s_speed = _min_max_norm(e_val, min_e, max_e, higher_is_better=False)
        s_quality = q_val

        score = (
            (weights.price * s_price)
            + (weights.warranty * s_warranty)
            + (weights.speed * s_speed)
            + (weights.quality * s_quality)
        ) / total_weight

        # Build evidence map
        evidence_map: Dict[str, EvidenceItem] = {}
        for k, v in off.evidence.items():
            if isinstance(v, dict) and "turn_ts" in v:
                evidence_map[k] = EvidenceItem(
                    turn_ts=v.get("turn_ts", 0.0),
                    text=v.get("text", ""),
                    translation=v.get("translation"),
                    lang=v.get("lang", "en"),
                    audio_url=v.get("audio_url"),
                )

        first_p = off.first_price or p_val
        saving = max(0, first_p - p_val)

        scored_rows.append(
            {
                "call_id": call.call_id,
                "shop_name": call.shop_name,
                "score": round(score, 2),
                "first_price": first_p,
                "final_price": p_val,
                "saving": saving,
                "warranty_months": off.warranty_months,
                "eta_days": off.eta_days,
                "part_type": off.part_type or "Unknown",
                "conditions": off.conditions or "",
                "evidence": evidence_map,
            }
        )

    # Sort rows by score descending
    scored_rows.sort(key=lambda r: r["score"], reverse=True)

    rows: List[ReportRow] = []
    for idx, r in enumerate(scored_rows, start=1):
        rows.append(
            ReportRow(
                call_id=r["call_id"],
                shop_name=r["shop_name"],
                rank=idx,
                score=r["score"],
                first_price=r["first_price"],
                final_price=r["final_price"],
                saving=r["saving"],
                warranty_months=r["warranty_months"],
                eta_days=r["eta_days"],
                part_type=r["part_type"],
                conditions=r["conditions"],
                evidence=r["evidence"],
            )
        )

    # Plain language recommendation comparison
    best = rows[0]
    reason = (
        f"{best.shop_name} ranked #1 with an overall score of {best.score}. "
        f"They offered a final price of Rs {best.final_price}"
        + (f" (saved Rs {best.saving} through negotiation)" if best.saving > 0 else "")
        + f" with {best.warranty_months or 0} months warranty on an {best.part_type} part."
    )

    if len(rows) > 1:
        runner_up = rows[1]
        reason += (
            f" In comparison, {runner_up.shop_name} quoted Rs {runner_up.final_price} "
            f"with {runner_up.warranty_months or 0} months warranty on an {runner_up.part_type} screen."
        )

    recommended = RecommendedShop(
        call_id=best.call_id,
        shop_name=best.shop_name,
        reason=reason,
    )

    # Other shops rationale
    others = []
    for r in rows[1:]:
        reasons = []
        if r.final_price and best.final_price and r.final_price > best.final_price:
            reasons.append(f"Rs {r.final_price - best.final_price} higher price")
        if (r.warranty_months or 0) < (best.warranty_months or 0):
            reasons.append(f"shorter warranty ({(best.warranty_months or 0) - (r.warranty_months or 0)} fewer months)")
        if r.part_type != "OEM" and best.part_type == "OEM":
            reasons.append(f"aftermarket quality vs OEM")

        why_text = f"Lower overall score due to {', '.join(reasons)}." if reasons else "Lower relative score across weighted criteria."
        others.append(OtherShop(call_id=r.call_id, why_not=why_text))

    return Report(
        job_id=job.job_id,
        recommended=recommended,
        weights=weights,
        rows=rows,
        others=others,
        caveats=caveats,
        timeline=timeline,
    )
