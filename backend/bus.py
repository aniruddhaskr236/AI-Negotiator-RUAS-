"""
In-memory async pub/sub event bus with 200-event replay buffer per job.

Design decision: The dashboard WebSocket may connect after negotiation events
have already fired. Retaining a circular replay buffer of the last 200 events
ensures late-joining or reconnecting dashboards render complete call timelines.
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List
from pydantic import BaseModel

from backend.config import logger


class JobEventBus:
    """Event bus for a single job with replay buffer and active subscriber queues."""

    def __init__(self, job_id: str, max_buffer: int = 200):
        self.job_id = job_id
        self.max_buffer = max_buffer
        self.replay_buffer: List[dict] = []
        self.subscribers: set[asyncio.Queue] = set()

    def publish(self, event: Any) -> None:
        """Appends event to replay buffer and pushes to all active subscriber queues."""
        if isinstance(event, BaseModel):
            event_dict = event.model_dump()
        elif isinstance(event, dict):
            event_dict = event
        else:
            event_dict = {"type": "unknown", "data": str(event)}

        # Maintain replay buffer limit
        self.replay_buffer.append(event_dict)
        if len(self.replay_buffer) > self.max_buffer:
            self.replay_buffer.pop(0)

        # Broadcast to active queues
        dead_subscribers = []
        for q in self.subscribers:
            try:
                q.put_nowait(event_dict)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full for job %s, dropping event", self.job_id)
            except Exception:
                dead_subscribers.append(q)

        for dead in dead_subscribers:
            self.subscribers.discard(dead)

    def subscribe(self) -> asyncio.Queue:
        """Returns a new queue subscribed to future events."""
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Removes a subscriber queue."""
        self.subscribers.discard(q)


# Registry of buses per job
_job_buses: Dict[str, JobEventBus] = {}
_lock = asyncio.Lock()


def get_or_create_bus(job_id: str) -> JobEventBus:
    """Returns or instantiates the event bus for a given job."""
    if job_id not in _job_buses:
        _job_buses[job_id] = JobEventBus(job_id)
    return _job_buses[job_id]


def publish_event(job_id: str, event: Any) -> None:
    """Convenience helper to publish an event to a job's bus."""
    bus = get_or_create_bus(job_id)
    bus.publish(event)


def broadcast_all_jobs(event: Any) -> None:
    """Broadcast an event to all active job buses (e.g., global provider health)."""
    for bus in _job_buses.values():
        bus.publish(event)
