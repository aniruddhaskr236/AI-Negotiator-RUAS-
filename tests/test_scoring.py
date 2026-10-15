import pytest
from backend.models import (
    Call,
    ConflictEvent,
    Job,
    Offer,
    TimelineEvent,
    Weights,
)
from backend import scoring


def test_scoring_min_max_and_ranking():
    """Verify weighted min-max scoring and ranking calculation."""
    job = Job(
        job_id="j_score_test",
        need="iPhone 13 screen fix",
        weights=Weights(price=40, warranty=25, speed=20, quality=15),
        created_at=100.0,
    )

    calls = [
        Call(call_id="c1", job_id="j_score_test", shop_id="1", shop_name="Sri Ganesh Mobiles", status="done"),
        Call(call_id="c2", job_id="j_score_test", shop_id="2", shop_name="Mobile Hub", status="done"),
        Call(call_id="c3", job_id="j_score_test", shop_id="3", shop_name="City Fix", status="failed", error="Shop hung up"),
    ]

    offers = {
        "c1": Offer(
            call_id="c1",
            price=3800,
            first_price=4500,
            warranty_months=6,
            eta_days=1,
            part_type="OEM",
            conditions="GST extra",
            evidence={
                "price": {"turn_ts": 12.0, "text": "3800", "lang": "en"},
                "warranty": {"turn_ts": 10.0, "text": "6 months", "lang": "en"},
            },
        ),
        "c2": Offer(
            call_id="c2",
            price=4200,
            first_price=3900,
            warranty_months=3,
            eta_days=2,
            part_type="Aftermarket",
            conditions="today only",
            evidence={"price": {"turn_ts": 14.0, "text": "4200", "lang": "en"}},
        ),
    }

    conflicts = [
        ConflictEvent(call_id="c2", field="price", old_value="3900", new_value="4200", old_ts=5.0, new_ts=14.0)
    ]
    timeline = [
        TimelineEvent(call_id="c1", text="Price dropped to 3800", ts=12.0)
    ]

    report = scoring.build_report(job, calls, offers, conflicts, timeline)

    assert report.job_id == "j_score_test"
    assert report.recommended is not None
    assert report.recommended.call_id == "c1"
    assert report.recommended.shop_name == "Sri Ganesh Mobiles"

    assert len(report.rows) == 2
    top_row = report.rows[0]
    assert top_row.rank == 1
    assert top_row.call_id == "c1"
    assert top_row.final_price == 3800
    assert top_row.saving == 700
    assert top_row.warranty_months == 6
    assert top_row.part_type == "OEM"
    assert "price" in top_row.evidence
    assert top_row.evidence["price"].turn_ts == 12.0

    # Verify caveats capture failed call and conflict
    assert any("City Fix" in c for c in report.caveats)
    assert any("Discrepancy detected for price" in c for c in report.caveats)

    # Verify others trade-off
    assert len(report.others) == 1
    assert report.others[0].call_id == "c2"


def test_scoring_custom_weights_reranking():
    """Verify that tweaking weights changes the score dynamically."""
    job = Job(
        job_id="j_weights_test",
        need="iPhone screen",
        weights=Weights(price=40, warranty=25, speed=20, quality=15),
        created_at=100.0,
    )

    calls = [
        Call(call_id="c1", job_id="j_weights_test", shop_id="1", shop_name="Cheap Aftermarket", status="done"),
        Call(call_id="c2", job_id="j_weights_test", shop_id="2", shop_name="Expensive OEM", status="done"),
    ]

    offers = {
        "c1": Offer(call_id="c1", price=2500, first_price=2500, warranty_months=1, eta_days=1, part_type="Aftermarket"),
        "c2": Offer(call_id="c2", price=5000, first_price=5000, warranty_months=12, eta_days=1, part_type="OEM"),
    }

    # 1. Price-heavy weights (90% price)
    price_heavy = Weights(price=90, warranty=5, speed=0, quality=5)
    rep_price = scoring.build_report(job, calls, offers, [], [], custom_weights=price_heavy)
    assert rep_price.recommended.call_id == "c1"

    # 2. Quality & warranty-heavy weights (80% warranty + quality, 5% price)
    qual_heavy = Weights(price=5, warranty=45, speed=10, quality=40)
    rep_qual = scoring.build_report(job, calls, offers, [], [], custom_weights=qual_heavy)
    assert rep_qual.recommended.call_id == "c2"
