"""
Call manager handling parallel shop calls, timeouts, retries, and shop WebSocket sockets.

Design decision: Calls run as independent, isolated asyncio tasks.
A network failure, hangup or timeout in Call 1 never blocks or terminates Call 2 or 3.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket

from backend.bus import publish_event
from backend.config import logger, settings
from backend.models import (
    Call,
    CallStatusEvent,
    Job,
    RingMessage,
    Weights,
)
from backend.personas import DEFAULT_SHOPS
from backend import store


class CallManager:
    """Manages active calls, shop sockets, and call lifecycle states."""

    def __init__(self):
        # shop_id -> WebSocket
        self.shop_sockets: Dict[str, WebSocket] = {}
        # call_id -> asyncio.Event signaled when shop sends "answer"
        self.answer_events: Dict[str, asyncio.Event] = {}
        # call_id -> asyncio.Task running the call loop
        self.call_tasks: Dict[str, asyncio.Task] = {}
        # call_id -> message queue for incoming shop messages (text, audio, hangup)
        self.shop_queues: Dict[str, asyncio.Queue] = {}

    def register_shop_socket(self, shop_id: str, websocket: WebSocket) -> None:
        """Register an active WebSocket connection from a shop."""
        self.shop_sockets[shop_id] = websocket
        logger.info("Shop socket connected for shop_id: %s", shop_id)

    def unregister_shop_socket(self, shop_id: str) -> None:
        """Unregister a disconnected shop socket."""
        if shop_id in self.shop_sockets:
            del self.shop_sockets[shop_id]
            logger.info("Shop socket disconnected for shop_id: %s", shop_id)

    def is_shop_connected(self, shop_id: str) -> bool:
        """Check if shop currently has an open WebSocket connection."""
        return shop_id in self.shop_sockets

    async def send_to_shop(self, shop_id: str, message: dict) -> bool:
        """Send a JSON payload to a registered shop socket safely."""
        ws = self.shop_sockets.get(shop_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as exc:
            logger.warning("Failed to send message to shop %s: %s", shop_id, exc)
            self.unregister_shop_socket(shop_id)
            return False

    def handle_shop_answer(self, call_id: str) -> None:
        """Signals that the shop clicked Answer."""
        if call_id in self.answer_events:
            self.answer_events[call_id].set()

    def handle_shop_message(self, call_id: str, msg: dict) -> None:
        """Queues an incoming message from the shop (text, audio, hangup)."""
        q = self.shop_queues.get(call_id)
        if q:
            try:
                q.put_nowait(msg)
            except Exception as e:
                logger.warning("Could not queue message for call %s: %s", call_id, e)

    def create_job(self, need: str, weights: Weights) -> Job:
        """
        Creates a new Job with 3 initial calls corresponding to default shop personas.
        Saves entities and initiates parallel call tasks.
        """
        job_id = f"j_{uuid.uuid4().hex[:8]}"
        job = Job(
            job_id=job_id,
            need=need,
            weights=weights,
            created_at=time.time(),
        )
        store.save_job(job)

        for s in DEFAULT_SHOPS:
            call_id = f"c_{uuid.uuid4().hex[:8]}"
            call = Call(
                call_id=call_id,
                job_id=job_id,
                shop_id=s["shop_id"],
                shop_name=s["shop_name"],
                lang=s["lang"],
                status="idle",
            )
            store.save_call(call)
            self.answer_events[call_id] = asyncio.Event()
            self.shop_queues[call_id] = asyncio.Queue()

            # Start call task in background
            task = asyncio.create_task(self.run_call_loop(job_id, call_id))
            self.call_tasks[call_id] = task

        return job

    async def retry_call(self, job_id: str, call_id: str) -> bool:
        """Resets a failed or done call to 'retrying' and spawns a new call task."""
        call = store.get_call(call_id)
        if not call:
            return False

        call.status = "retrying"
        call.error = None
        store.save_call(call)
        publish_event(job_id, CallStatusEvent(call_id=call_id, status="retrying"))

        self.answer_events[call_id] = asyncio.Event()
        self.shop_queues[call_id] = asyncio.Queue()

        task = asyncio.create_task(self.run_call_loop(job_id, call_id))
        self.call_tasks[call_id] = task
        return True

    async def run_call_loop(self, job_id: str, call_id: str) -> None:
        """
        Core call loop:
        1. Rings shop socket (or auto-answers if SCRIPTED_SHOPS=1)
        2. Waits up to 30s for 'answer'
        3. Updates status to talking, processes conversation turns
        4. Updates status to done / failed
        """
        call = store.get_call(call_id)
        if not call:
            return

        try:
            # 1. Ringing state
            call.status = "ringing"
            store.save_call(call)
            publish_event(job_id, CallStatusEvent(call_id=call_id, status="ringing"))

            # Send ring message to shop socket
            ring_msg = RingMessage(call_id=call_id).model_dump()
            await self.send_to_shop(call.shop_id, ring_msg)

            # In scripted mode, auto-answer after short simulated delay
            if settings.scripted_shops:
                await asyncio.sleep(0.5)
                self.handle_shop_answer(call_id)

            # 2. Wait up to 30 seconds for answer
            answer_event = self.answer_events.get(call_id)
            answered = False
            if answer_event:
                try:
                    await asyncio.wait_for(answer_event.wait(), timeout=30.0)
                    answered = True
                except asyncio.TimeoutError:
                    answered = False

            if not answered:
                call.status = "failed"
                call.error = "No answer after 30 seconds"
                store.save_call(call)
                publish_event(
                    job_id,
                    CallStatusEvent(call_id=call_id, status="failed", error=call.error),
                )
                return

            # 3. Talking state
            call.status = "talking"
            store.save_call(call)
            publish_event(job_id, CallStatusEvent(call_id=call_id, status="talking"))

            # Note: The detailed conversation dialogue loop with negotiation state machine
            # and speech STT/TTS will be expanded in Phases 6-9.
            # In Phase 4 skeleton, we ensure the state transitions succeed gracefully.
            if settings.scripted_shops:
                # Simulated brief duration for Phase 4 skeleton tests
                await asyncio.sleep(0.2)
                call.status = "done"
                store.save_call(call)
                publish_event(job_id, CallStatusEvent(call_id=call_id, status="done"))

        except Exception as exc:
            logger.error("Error in run_call_loop for call %s: %s", call_id, exc)
            call.status = "failed"
            call.error = str(exc)
            store.save_call(call)
            publish_event(
                job_id,
                CallStatusEvent(call_id=call_id, status="failed", error=call.error),
            )


# Singleton call manager
call_manager = CallManager()
