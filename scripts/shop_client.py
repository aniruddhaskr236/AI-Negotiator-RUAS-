"""
Terminal-based interactive shop client for human testing or manual simulation.

Usage:
    python scripts/shop_client.py [shop_id]
"""

import asyncio
import json
import os
import sys
import websockets

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
WS_BASE_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")


async def run_shop_client(shop_id: str):
    ws_url = f"{WS_BASE_URL}/ws/shop/{shop_id}"
    print(f"Connecting to shop line: {ws_url}")

    async with websockets.connect(ws_url) as ws:
        print(f"\n[Shop {shop_id}] Online and waiting for incoming calls...\n")
        current_call_id = None

        async def _ping_loop():
            while True:
                await asyncio.sleep(20)
                await ws.send(json.dumps({"type": "ping"}))

        ping_task = asyncio.create_task(_ping_loop())

        try:
            while True:
                msg_raw = await ws.recv()
                msg = json.loads(msg_raw)
                mtype = msg.get("type")

                if mtype == "ring":
                    current_call_id = msg.get("call_id")
                    caller = msg.get("caller")
                    print(f"\n>>> INCOMING CALL from: {caller} (Call ID: {current_call_id})")
                    print(">>> Auto-answering call...")
                    await ws.send(json.dumps({"type": "answer", "call_id": current_call_id}))

                elif mtype == "agent_text":
                    text = msg.get("text")
                    lang = msg.get("lang")
                    print(f"\n[Agent] ({lang}): {text}")

                    # Read reply from console (in thread to avoid blocking loop)
                    reply = await asyncio.to_thread(input, f"[Shop {shop_id} Reply] > ")
                    if reply.strip().lower() == "hangup":
                        await ws.send(json.dumps({"type": "hangup", "call_id": current_call_id}))
                        print(">>> Hung up.")
                    else:
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "text",
                                    "call_id": current_call_id,
                                    "text": reply,
                                }
                            )
                        )

                elif mtype == "end":
                    print("\n>>> Call ended by agent.")
                    current_call_id = None

        except (websockets.ConnectionClosed, KeyboardInterrupt):
            print("\nShop line closed.")
        finally:
            ping_task.cancel()


if __name__ == "__main__":
    shop_id_arg = sys.argv[1] if len(sys.argv) > 1 else "1"
    try:
        asyncio.run(run_shop_client(shop_id_arg))
    except KeyboardInterrupt:
        pass
