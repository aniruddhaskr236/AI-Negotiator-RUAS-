"""
WebSocket endpoints for shop phone pages and agent dashboard.

Design decision: Separate WebSocket routes decouple the low-latency shop phone
audio/dialogue channel from the multi-call broadcast dashboard channel.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.bus import get_or_create_bus
from backend.calls import call_manager
from backend.config import logger

router = APIRouter()


@router.websocket("/ws/shop/{shop_id}")
async def shop_websocket(websocket: WebSocket, shop_id: str):
    """
    Shop phone WebSocket connection.
    Transports ring, agent_text, agent_audio, answer, audio, typed text, and hangup.
    """
    await websocket.accept()
    call_manager.register_shop_socket(shop_id, websocket)

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "ping":
                # Keep-alive
                await websocket.send_json({"type": "pong"})
            elif msg_type == "answer":
                call_id = msg.get("call_id")
                if call_id:
                    call_manager.handle_shop_answer(call_id)
            elif msg_type in ("text", "audio", "hangup"):
                call_id = msg.get("call_id")
                if call_id:
                    call_manager.handle_shop_message(call_id, msg)
            else:
                logger.debug("Received unknown message from shop %s: %s", shop_id, msg)

    except WebSocketDisconnect:
        logger.info("Shop WebSocket disconnected: shop_id=%s", shop_id)
    except Exception as exc:
        logger.warning("Error in shop WebSocket (%s): %s", shop_id, exc)
    finally:
        call_manager.unregister_shop_socket(shop_id)


@router.websocket("/ws/dashboard/{job_id}")
async def dashboard_websocket(websocket: WebSocket, job_id: str):
    """
    Dashboard WebSocket connection.
    Plays back the circular replay buffer (up to 200 events) upon connection,
    then streams live turn, offer, conflict, status, timeline, and health events.
    """
    await websocket.accept()
    bus = get_or_create_bus(job_id)

    # 1. Replay past events in chronological order
    for past_event in bus.replay_buffer:
        try:
            await websocket.send_json(past_event)
        except Exception:
            return

    # 2. Subscribe to new real-time events
    event_queue = bus.subscribe()

    async def _send_loop():
        try:
            while True:
                event = await event_queue.get()
                await websocket.send_json(event)
        except Exception:
            pass

    async def _receive_loop():
        try:
            while True:
                msg = await websocket.receive_json()
                # Dashboard ping handling
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except Exception:
            pass

    send_task = asyncio.create_task(_send_loop())
    recv_task = asyncio.create_task(_receive_loop())

    try:
        # Wait until either task finishes (e.g. client disconnects)
        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        bus.unsubscribe(event_queue)
        logger.info("Dashboard WebSocket disconnected for job_id=%s", job_id)
