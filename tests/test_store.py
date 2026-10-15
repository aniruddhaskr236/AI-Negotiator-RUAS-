import os
import pytest
from backend import store
from backend.models import (
    Call,
    ConflictEvent,
    Job,
    Offer,
    TimelineEvent,
    Turn,
    Weights,
)

TEST_DB = "./test_bhaav.db"


@pytest.fixture(autouse=True)
def cleanup_test_db():
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass
    store.init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass


def test_job_save_and_retrieve():
    """Verify job creation and retrieval."""
    job = Job(
        job_id="j_test_1",
        need="iPhone 13 screen replacement",
        weights=Weights(price=50, warranty=20, speed=15, quality=15),
        created_at=100.0,
    )
    store.save_job(job, db_path=TEST_DB)
    loaded = store.get_job("j_test_1", db_path=TEST_DB)
    assert loaded is not None
    assert loaded.job_id == "j_test_1"
    assert loaded.need == "iPhone 13 screen replacement"
    assert loaded.weights.price == 50


def test_call_and_turns():
    """Verify call status updates and turn dialogues."""
    call = Call(
        call_id="c_1",
        job_id="j_test_1",
        shop_id="1",
        shop_name="Sri Ganesh Mobiles",
        lang="en",
        status="ringing",
    )
    store.save_call(call, db_path=TEST_DB)

    turn1 = Turn(
        call_id="c_1",
        speaker="agent",
        text="Hello, I am an AI assistant.",
        lang="en",
        ts=10.5,
    )
    turn2 = Turn(
        call_id="c_1",
        speaker="shop",
        text="Yes, we can do it for 4500.",
        lang="en",
        ts=12.0,
    )
    store.add_turn(turn1, db_path=TEST_DB)
    store.add_turn(turn2, db_path=TEST_DB)

    turns = store.get_turns_for_call("c_1", db_path=TEST_DB)
    assert len(turns) == 2
    assert turns[0].speaker == "agent"
    assert turns[1].speaker == "shop"
    assert turns[1].text == "Yes, we can do it for 4500."


def test_offer_upsert():
    """Verify offer upsert and retrieval."""
    offer = Offer(
        call_id="c_1",
        price=4500,
        first_price=4500,
        warranty_months=6,
        eta_days=1,
        part_type="OEM",
        conditions="GST extra",
        confidence=0.9,
        evidence={"price": {"turn_ts": 12.0}},
    )
    store.upsert_offer(offer, db_path=TEST_DB)

    loaded = store.get_offer("c_1", db_path=TEST_DB)
    assert loaded is not None
    assert loaded.price == 4500
    assert loaded.warranty_months == 6
    assert loaded.part_type == "OEM"
    assert loaded.evidence.get("price") == {"turn_ts": 12.0}


def test_conflicts_and_timeline():
    """Verify conflict recording and chronological timeline."""
    conflict = ConflictEvent(
        call_id="c_1",
        field="price",
        old_value="4500",
        new_value="4200",
        old_ts=12.0,
        new_ts=25.0,
    )
    store.add_conflict(conflict, db_path=TEST_DB)

    evt = TimelineEvent(call_id="c_1", text="Price dropped from 4500 to 4200", ts=25.0)
    store.add_timeline_event(evt, db_path=TEST_DB)

    conflicts = store.get_conflicts_for_job("j_test_1", db_path=TEST_DB)
    assert len(conflicts) == 1
    assert conflicts[0].new_value == "4200"

    timeline = store.get_timeline_for_job("j_test_1", db_path=TEST_DB)
    assert len(timeline) >= 1
    assert any("Price dropped" in e.text for e in timeline)


def test_storage_failure_tolerance():
    """Verify that an invalid db_path does not crash writes/reads."""
    invalid_path = "/nonexistent_folder/subfolder/cannot_write.db"
    job = Job(
        job_id="j_fail_safe",
        need="Screen fix",
        weights=Weights(),
        created_at=200.0,
    )
    # Should not raise exception
    store.save_job(job, db_path=invalid_path)
    loaded = store.get_job("j_fail_safe", db_path=invalid_path)
    assert loaded is not None
    assert loaded.job_id == "j_fail_safe"
