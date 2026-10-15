import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.bus import get_or_create_bus, publish_event
from backend.models import TurnEvent


def test_create_job_and_retrieve_calls():
    """Verify POST /api/jobs creates a job with 3 default calls."""
    client = TestClient(app)
    payload = {
        "need": "iPhone 13 screen replacement, original preferred",
        "weights": {"price": 40, "warranty": 25, "speed": 20, "quality": 15},
    }
    resp = client.post("/api/jobs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert len(data["calls"]) == 3
    names = {c["shop_name"] for c in data["calls"]}
    assert "Sri Ganesh Mobiles" in names
    assert "Mobile Hub Indiranagar" in names
    assert "City Fix Corner" in names


def test_retry_call_endpoint():
    """Verify retry endpoint resets call state and returns ok: true."""
    client = TestClient(app)
    # First create a job
    resp = client.post("/api/jobs", json={"need": "Battery replacement"})
    job_id = resp.json()["job_id"]
    call_id = resp.json()["calls"][0]["call_id"]

    # Retry call
    retry_resp = client.post(f"/api/jobs/{job_id}/calls/{call_id}/retry")
    assert retry_resp.status_code == 200
    assert retry_resp.json() == {"ok": True}


def test_report_endpoint():
    """Verify GET /api/jobs/{job_id}/report returns valid Report structure."""
    client = TestClient(app)
    resp = client.post("/api/jobs", json={"need": "Screen fix"})
    job_id = resp.json()["job_id"]

    report_resp = client.get(f"/api/jobs/{job_id}/report?weights=50,20,15,15")
    assert report_resp.status_code == 200
    rep = report_resp.json()
    assert rep["job_id"] == job_id
    assert rep["weights"]["price"] == 50
    assert "rows" in rep
    assert "caveats" in rep


def test_check_system_endpoint():
    """Verify GET /api/check returns diagnostic items."""
    client = TestClient(app)
    resp = client.get("/api/check")
    assert resp.status_code == 200
    data = resp.json()
    assert "checks" in data
    names = [c["name"] for c in data["checks"]]
    assert "Server Health" in names


def test_demo_fail_endpoint():
    """Verify POST /api/demo/fail handles failure kinds."""
    client = TestClient(app)
    resp = client.post("/api/demo/fail", json={"kind": "kill_provider"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_event_bus_replay_buffer():
    """Verify event bus limits replay buffer to 200 and preserves order."""
    bus = get_or_create_bus("test_bus_job")
    for i in range(250):
        bus.publish({"type": "turn", "index": i})

    assert len(bus.replay_buffer) == 200
    assert bus.replay_buffer[0]["index"] == 50
    assert bus.replay_buffer[-1]["index"] == 249


def test_shop_websocket_flow():
    """Verify shop phone websocket answers call and responds to ping."""
    client = TestClient(app)
    with client.websocket_connect("/ws/shop/1") as ws:
        # Send ping
        ws.send_json({"type": "ping"})
        msg = ws.receive_json()
        assert msg == {"type": "pong"}

        # Send answer
        ws.send_json({"type": "answer", "call_id": "c_mock_1"})


def test_dashboard_websocket_replays_events():
    """Verify dashboard websocket replays existing events and receives live events."""
    client = TestClient(app)
    job_id = "j_dash_test"
    publish_event(
        job_id,
        TurnEvent(
            call_id="c_1",
            speaker="agent",
            text="Hello shop",
            lang="en",
            ts=10.0,
        ),
    )

    with client.websocket_connect(f"/ws/dashboard/{job_id}") as ws:
        # First message should be the replayed event
        replayed = ws.receive_json()
        assert replayed["type"] == "turn"
        assert replayed["text"] == "Hello shop"

        # Send ping
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong == {"type": "pong"}
