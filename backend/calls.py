"""
Call manager handling parallel shop calls, timeouts, retries, and the complete dialogue loop.

Design decision: Parallel independent call loops with isolated state machines ensure that
one shop hanging up or stalling never affects other concurrent negotiations.
Evidence is updated turn-by-turn and shared across calls for verified countering.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket

from backend.agent import generate_agent_utterance
from backend.bus import publish_event
from backend.config import logger, settings
from backend.extract import detect_conflicts, extract_offer
from backend.models import (
    AgentAudioMessage,
    AgentTextMessage,
    Call,
    CallStatusEvent,
    EndMessage,
    Job,
    OfferEvent,
    ReportReadyEvent,
    RingMessage,
    TimelineEvent,
    Turn,
    TurnEvent,
    Weights,
)
from backend.speech import synthesize
from backend.negotiation import (
    NegotiationAction,
    NegotiationState,
    next_negotiation_step,
)
from backend.personas import DEFAULT_SHOPS
from backend.shop_sim import ShopSimulator
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
    async def send_agent_utterance(self, shop_id: str, call_id: str, text: str, lang: str) -> None:
        """
        Sends agent utterance. Audio order requirement:
        send agent_audio FIRST only if TTS finishes within 1.2 s, then agent_text;
        otherwise agent_text only. Never audio after its text.
        """
        audio_msg = None
        try:
            synth = await asyncio.wait_for(synthesize(text, lang=lang), timeout=1.2)
            if synth:
                mime, data = synth
                audio_msg = AgentAudioMessage(call_id=call_id, mime=mime, data=data).model_dump()
        except Exception as exc:
            logger.debug("TTS synthesis skipped or exceeded 1.2s budget: %s", exc)
            audio_msg = None

        if audio_msg:
            # 1. Send audio FIRST
            await self.send_to_shop(shop_id, audio_msg)
            # 2. Then send text
            await self.send_to_shop(
                shop_id,
                AgentTextMessage(call_id=call_id, text=text, lang=lang).model_dump(),
            )
        else:
            # Otherwise agent_text only
            await self.send_to_shop(
                shop_id,
                AgentTextMessage(call_id=call_id, text=text, lang=lang).model_dump(),
            )

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
        Creates a new Job with 3 parallel calls corresponding to default shop personas.
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
        """Resets a failed or finished call to 'retrying' and spawns a new call task."""
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

    def _check_and_notify_report_ready(self, job_id: str) -> None:
        """Checks if all calls for this job have finished; if so, emits report_ready."""
        calls = store.get_calls_for_job(job_id)
        if calls and all(c.status in ("done", "failed") for c in calls):
            publish_event(job_id, ReportReadyEvent(job_id=job_id))
            logger.info("All calls finished for job %s. Emitted report_ready.", job_id)

    async def run_call_loop(self, job_id: str, call_id: str) -> None:
        """
        Complete per-call live negotiation loop:
        1. Ringing & answer handling
        2. GREET turn with mandatory AI disclosure
        3. Turn-by-turn dialogue, real-time offer extraction & conflict detection
        4. State machine negotiation using verified quotes from concurrent calls
        5. Polite CLOSE and report_ready notification
        """
        call = store.get_call(call_id)
        job = store.get_job(job_id)
        if not call or not job:
            return

        simulator = ShopSimulator(call.shop_id) if settings.scripted_shops else None

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
                await asyncio.sleep(0.1)
                self.handle_shop_answer(call_id)

            # 2. Wait up to configured seconds for answer
            answer_event = self.answer_events.get(call_id)
            answered = False
            if answer_event:
                try:
                    await asyncio.wait_for(
                        answer_event.wait(), timeout=settings.call_answer_timeout
                    )
                    answered = True
                except asyncio.TimeoutError:
                    answered = False

            if not answered:
                call.status = "failed"
                call.error = f"No answer after {int(settings.call_answer_timeout)} seconds"
                store.save_call(call)
                publish_event(
                    job_id,
                    CallStatusEvent(call_id=call_id, status="failed", error=call.error),
                )
                self._check_and_notify_report_ready(job_id)
                return

            # 3. Talking state
            call.status = "talking"
            store.save_call(call)
            publish_event(job_id, CallStatusEvent(call_id=call_id, status="talking"))

            state = NegotiationState.GREET
            refusal_count = 0
            agent_utterance = ""
            active_conflict = None

            # 4. Turn 0: Agent Opening Utterance (GREET) with mandatory AI disclosure
            greet_action = next_negotiation_step(
                current_state=NegotiationState.GREET,
                current_offer=None,
                other_offers={},
                user_weights=job.weights,
                turn_count=0,
                job_id=job_id,
                call_id=call_id,
                ts=time.time(),
            )
            agent_text, agent_trans = await generate_agent_utterance(
                need=job.need,
                action=greet_action,
                dialogue_history=[],
                target_lang=call.lang,
            )
            agent_utterance = agent_text

            agent_turn = Turn(
                call_id=call_id,
                speaker="agent",
                text=agent_text,
                translation=agent_trans,
                lang=call.lang,  # type: ignore
                ts=time.time(),
                confidence=1.0,
            )
            store.add_turn(agent_turn)
            publish_event(
                job_id,
                TurnEvent(
                    call_id=call_id,
                    speaker="agent",
                    text=agent_text,
                    translation=agent_trans,
                    lang=call.lang,  # type: ignore
                    ts=agent_turn.ts,
                ),
            )
            await self.send_agent_utterance(
                call.shop_id, call_id, agent_text, call.lang
            )
            state = greet_action.next_state

            # 5. Conversation turns loop (up to 14 agent turns)
            for turn_idx in range(1, 14):
                # Retrieve other offers for cross-shop intelligence
                other_offers = store.get_offers_for_job(job_id)
                competing_quote = None
                current_offer = store.get_offer(call_id)
                if current_offer and current_offer.price is not None:
                    comp_offer = next(
                        (o for cid, o in other_offers.items() if cid != call_id and o.price and o.price < current_offer.price),
                        None,
                    )
                    if comp_offer:
                        competing_quote = comp_offer.price

                # A. Receive shop reply
                shop_text = ""
                shop_lang = call.lang
                shop_hangup = False
                turn_ts = time.time()
                turn_confidence = 1.0

                if settings.scripted_shops and simulator:
                    await asyncio.sleep(0.05)
                    shop_text, shop_lang, shop_hangup = simulator.respond(
                        agent_utterance=agent_utterance,
                        competing_quote=competing_quote,
                    )
                else:
                    # Live WebSocket / human shop
                    q = self.shop_queues.get(call_id)
                    if not q:
                        break
                    try:
                        # 20s silence detection: ask once if quiet
                        msg = await asyncio.wait_for(q.get(), timeout=20.0)
                    except asyncio.TimeoutError:
                        logger.info("Silence detected on call %s. Prompting shop once.", call_id)
                        prompt_text = "Are you still there? Could you please confirm if you can hear me?"
                        await self.send_to_shop(
                            call.shop_id,
                            AgentTextMessage(call_id=call_id, text=prompt_text, lang=call.lang).model_dump(),
                        )
                        try:
                            msg = await asyncio.wait_for(q.get(), timeout=10.0)
                        except asyncio.TimeoutError:
                            call.status = "failed"
                            call.error = "Silence timeout: shop did not respond"
                            store.save_call(call)
                            publish_event(
                                job_id,
                                CallStatusEvent(call_id=call_id, status="failed", error=call.error),
                            )
                            break

                    mtype = msg.get("type")
                    if msg.get("ts"):
                        turn_ts = float(msg["ts"])
                    if mtype == "hangup":
                        shop_hangup = True
                    elif mtype == "text":
                        shop_text = msg.get("text", "")
                        turn_confidence = msg.get("confidence", 1.0)
                    elif mtype == "audio":
                        if msg.get("needs_repeat"):
                            repeat_prompt = (
                                "Sorry, I could not hear that clearly. Could you please repeat or type your answer?"
                                if call.lang == "en"
                                else "माफ़ कीजिए, मुझे ठीक से सुनाई नहीं दिया। क्या आप दोबारा बता सकते हैं?"
                            )
                            await self.send_agent_utterance(
                                call.shop_id, call_id, repeat_prompt, call.lang
                            )
                            publish_event(
                                job_id,
                                TimelineEvent(
                                    call_id=call_id,
                                    text="Audio from shop was unclear; agent requested repetition.",
                                    ts=time.time(),
                                ),
                            )
                            continue

                        shop_text = msg.get("text", "")
                        turn_confidence = msg.get("confidence", 0.9)

                if shop_hangup:
                    call.status = "failed"
                    call.error = "Shop hung up"
                    store.save_call(call)
                    publish_event(
                        job_id,
                        CallStatusEvent(call_id=call_id, status="failed", error=call.error),
                    )
                    break

                # B. Store & publish shop turn
                shop_turn = Turn(
                    call_id=call_id,
                    speaker="shop",
                    text=shop_text,
                    lang=shop_lang,  # type: ignore
                    ts=turn_ts,
                    confidence=turn_confidence,
                )
                store.add_turn(shop_turn)
                publish_event(
                    job_id,
                    TurnEvent(
                        call_id=call_id,
                        speaker="shop",
                        text=shop_text,
                        lang=shop_lang,  # type: ignore
                        ts=turn_ts,
                        confidence=turn_confidence,
                    ),
                )

                # Check refusal keywords
                lower_s = shop_text.lower()
                if any(w in lower_s for w in ["fixed", "final", "last price", "nahi hoga", "kam nahi"]):
                    refusal_count += 1

                # C. Extract offer details & detect conflicts
                all_turns = store.get_turns_for_call(call_id)
                old_offer = store.get_offer(call_id)
                new_offer = extract_offer(all_turns, call_id=call_id)

                conflicts = detect_conflicts(old_offer, new_offer, current_turn_ts=turn_ts)
                for conf in conflicts:
                    store.add_conflict(conf)
                    publish_event(job_id, conf)
                    active_conflict = conf.model_dump()

                store.upsert_offer(new_offer)
                publish_event(
                    job_id,
                    OfferEvent(
                        call_id=call_id,
                        price=new_offer.price,
                        first_price=new_offer.first_price,
                        warranty_months=new_offer.warranty_months,
                        eta_days=new_offer.eta_days,
                        part_type=new_offer.part_type,
                        conditions=new_offer.conditions,
                        confidence=new_offer.confidence,
                        evidence=new_offer.evidence,
                    ),
                )

                # D. Compute next negotiation action
                other_offers = store.get_offers_for_job(job_id)
                action = next_negotiation_step(
                    current_state=state,
                    current_offer=new_offer,
                    other_offers=other_offers,
                    user_weights=job.weights,
                    turn_count=turn_idx,
                    refusal_count=refusal_count,
                    active_conflict=active_conflict,
                    job_id=job_id,
                    call_id=call_id,
                    ts=turn_ts,
                )
                state = action.next_state
                active_conflict = None  # Reset active conflict after handling

                # E. Generate agent reply
                agent_text, agent_trans = await generate_agent_utterance(
                    need=job.need,
                    action=action,
                    dialogue_history=all_turns,
                    target_lang=call.lang,
                    current_shop_price=new_offer.price,
                )
                agent_utterance = agent_text

                agent_turn = Turn(
                    call_id=call_id,
                    speaker="agent",
                    text=agent_text,
                    translation=agent_trans,
                    lang=call.lang,  # type: ignore
                    ts=time.time(),
                    confidence=1.0,
                )
                store.add_turn(agent_turn)
                publish_event(
                    job_id,
                    TurnEvent(
                        call_id=call_id,
                        speaker="agent",
                        text=agent_text,
                        translation=agent_trans,
                        lang=call.lang,  # type: ignore
                        ts=agent_turn.ts,
                    ),
                )
                await self.send_agent_utterance(
                    call.shop_id, call_id, agent_text, call.lang
                )

                # F. If negotiation reached DECIDE or CLOSE, conclude cleanly
                if action.next_state in (NegotiationState.DECIDE, NegotiationState.CLOSE):
                    await self.send_to_shop(call.shop_id, EndMessage(call_id=call_id).model_dump())
                    call.status = "done"
                    store.save_call(call)
                    publish_event(job_id, CallStatusEvent(call_id=call_id, status="done"))
                    break

            # If call finishes loop still talking, close cleanly as done
            if call.status == "talking":
                await self.send_to_shop(call.shop_id, EndMessage(call_id=call_id).model_dump())
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
        finally:
            self._check_and_notify_report_ready(job_id)


# Singleton call manager
call_manager = CallManager()
