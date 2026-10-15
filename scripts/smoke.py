"""
Smoke test script for Bhaav:
1. Submits POST /api/jobs
2. Streams real-time events over /ws/dashboard/{job_id}
3. Fetches and displays final evidence-backed report
"""

import asyncio
import json
import os
import sys
import httpx
import websockets

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
WS_BASE_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")


async def run_smoke():
    print(f"Connecting to Bhaav backend at {BASE_URL}...")

    # 1. Create a job
    job_payload = {
        "need": "iPhone 13 screen replacement, original display preferred",
        "weights": {"price": 40, "warranty": 25, "speed": 20, "quality": 15},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{BASE_URL}/api/jobs", json=job_payload)
            resp.raise_for_status()
            job_data = resp.json()
        except Exception as e:
            print(f"Error creating job: {e}")
            sys.exit(1)

    job_id = job_data["job_id"]
    calls = job_data["calls"]
    print(f"\n[+] Job Created: {job_id}")
    for c in calls:
        print(f"    - Call {c['call_id']}: {c['shop_name']} (Shop {c['shop_id']}, Lang: {c['lang']})")

    # 2. Connect to dashboard WebSocket
    ws_url = f"{WS_BASE_URL}/ws/dashboard/{job_id}"
    print(f"\n[+] Listening to dashboard stream: {ws_url}\n")

    report_ready = False
    done_calls = set()
    total_calls = len(calls)

    try:
        async with websockets.connect(ws_url) as ws:
            # Send initial ping
            await ws.send(json.dumps({"type": "ping"}))

            while not report_ready:
                try:
                    msg_text = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    event = json.loads(msg_text)
                    ev_type = event.get("type")

                    if ev_type == "call_status":
                        cid = event.get("call_id")
                        status = event.get("status")
                        err = event.get("error")
                        err_str = f" ({err})" if err else ""
                        print(f"  [STATUS] Call {cid} -> {status.upper()}{err_str}")
                        if status in ("done", "failed"):
                            done_calls.add(cid)
                            if len(done_calls) >= total_calls:
                                report_ready = True

                    elif ev_type == "turn":
                        cid = event.get("call_id")
                        speaker = event.get("speaker")
                        text = event.get("text")
                        lang = event.get("lang")
                        trans = event.get("translation")
                        trans_str = f" [EN: {trans}]" if trans else ""
                        print(f"  [TURN] [{speaker.upper()}] ({lang}): {text}{trans_str}")

                    elif ev_type == "offer":
                        cid = event.get("call_id")
                        price = event.get("price")
                        w = event.get("warranty_months")
                        part = event.get("part_type")
                        print(f"  [OFFER] Call {cid} Quote: Rs {price} | Warranty: {w}m | Part: {part}")

                    elif ev_type == "conflict":
                        field = event.get("field")
                        old_v = event.get("old_value")
                        new_v = event.get("new_value")
                        print(f"  [CONFLICT] Discrepancy on {field}: {old_v} -> {new_v}")

                    elif ev_type == "timeline":
                        text = event.get("text")
                        print(f"  [TIMELINE] {text}")

                    elif ev_type == "report_ready":
                        print("  [REPORT READY] Notification received")
                        report_ready = True

                except asyncio.TimeoutError:
                    print("  [TIMEOUT] No more events received within 15s")
                    break

    except Exception as exc:
        print(f"WebSocket error: {exc}")

    # 3. Retrieve final report
    print("\n" + "=" * 65)
    print(" FETCHING FINAL EVIDENCE-BACKED REPORT")
    print("=" * 65)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            report_resp = await client.get(f"{BASE_URL}/api/jobs/{job_id}/report")
            report_data = report_resp.json()
            rec = report_data.get("recommended")
            if rec:
                print(f"RECOMMENDED SHOP: {rec['shop_name']}")
                print(f"REASON          : {rec['reason']}\n")

            print(f"{'Rank':<5} | {'Shop Name':<25} | {'Final Price':<12} | {'Saving':<8} | {'Warranty':<10} | {'Score'}")
            print("-" * 65)
            for row in report_data.get("rows", []):
                p_str = f"Rs {row['final_price']}" if row['final_price'] else "N/A"
                s_str = f"Rs {row['saving']}" if row['saving'] else "0"
                w_str = f"{row['warranty_months']} mos" if row['warranty_months'] else "N/A"
                print(f"{row['rank']:<5} | {row['shop_name']:<25} | {p_str:<12} | {s_str:<8} | {w_str:<10} | {row['score']}")

            if report_data.get("caveats"):
                print("\nCAVEATS:")
                for c in report_data["caveats"]:
                    print(f"  * {c}")

        except Exception as e:
            print(f"Error fetching report: {e}")

    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_smoke())
