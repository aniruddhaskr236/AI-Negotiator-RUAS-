import asyncio
import httpx
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend import store


@pytest.mark.asyncio
async def test_e2e_three_scripted_shops():
    """
    End-to-end test simulating three parallel scripted shops with a stubbed LLM:
    - Sri Ganesh Mobiles: Honest, opens 4500, lowers to 4200 then 3800.
    - Mobile Hub Indiranagar: Pushy, changes price mid-call (conflicts flagged).
    - City Fix Corner: Evasive, hangs up after 3 turns.
    Verifies that City Fix Corner hanging up does not affect the others,
    and report_ready is generated with full evidence.
    """
    # Enable scripted shops mode
    with patch.object(settings, "scripted_shops", True), \
         patch.object(settings, "call_answer_timeout", 0.5), \
         patch("backend.agent.call_llm", new_callable=AsyncMock) as mock_llm:

        # Mock LLM to return safe polite response
        mock_llm.return_value = "Understood, could you tell me more details?"

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create a job
            payload = {
                "need": "iPhone 13 screen replacement, original display preferred",
                "weights": {"price": 40, "warranty": 25, "speed": 20, "quality": 15},
            }
            create_resp = await client.post("/api/jobs", json=payload)
            assert create_resp.status_code == 200
            job_data = create_resp.json()
            job_id = job_data["job_id"]
            calls = job_data["calls"]
            assert len(calls) == 3

            # 2. Poll until all calls finish (max 8 seconds)
            for _ in range(80):
                await asyncio.sleep(0.1)
                db_calls = store.get_calls_for_job(job_id)
                if db_calls and all(c.status in ("done", "failed") for c in db_calls):
                    break

            final_calls = store.get_calls_for_job(job_id)
            assert all(c.status in ("done", "failed") for c in final_calls), f"Not all calls finished: {[(c.shop_name, c.status, c.error) for c in final_calls]}"

            # Check statuses
            shop1_call = next(c for c in final_calls if c.shop_name == "Sri Ganesh Mobiles")
            shop2_call = next(c for c in final_calls if c.shop_name == "Mobile Hub Indiranagar")
            shop3_call = next(c for c in final_calls if c.shop_name == "City Fix Corner")

            assert shop1_call.status == "done"
            assert shop2_call.status == "done"
            assert shop3_call.status == "failed"  # Hung up after 3 turns

            # 3. Verify conflicts were detected for Shop 2
            conflicts = store.get_conflicts_for_job(job_id)
            assert any(c.call_id == shop2_call.call_id and c.field == "price" for c in conflicts)

            # 4. Verify Final Report
            report_resp = await client.get(f"/api/jobs/{job_id}/report")
            assert report_resp.status_code == 200
            report = report_resp.json()

        assert report["job_id"] == job_id
        assert len(report["rows"]) >= 2
        # Sri Ganesh Mobiles should have a lower final price than first price
        sg_row = next(r for r in report["rows"] if r["call_id"] == shop1_call.call_id)
        assert sg_row["first_price"] == 4500
        assert sg_row["final_price"] in (3800, 4200)
        assert sg_row["saving"] > 0
        assert sg_row["warranty_months"] == 6
        assert sg_row["part_type"] == "OEM"

        # Caveat about City Fix Corner failing
        assert any("City Fix Corner" in cav for cav in report["caveats"])
