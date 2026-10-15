"""
SQLite3 storage engine with dual in-memory write buffer for failure tolerance.

Design decision: Live calls cannot afford disk locks or filesystem crashes.
Every write updates an in-memory replica first, and catches any SQLite error
so calls proceed unhindered even if the database is locked or corrupted.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional

from backend.config import settings, logger
from backend.models import (
    Call,
    ConflictEvent,
    Job,
    Offer,
    TimelineEvent,
    Turn,
    Weights,
)

# In-memory resilient cache
_mem_jobs: Dict[str, Job] = {}
_mem_calls: Dict[str, Call] = {}
_mem_turns: List[Turn] = []
_mem_offers: Dict[str, Offer] = {}
_mem_conflicts: List[ConflictEvent] = []
_mem_timeline: List[TimelineEvent] = []


def _get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a connection with autocommit / isolation level None and 5s timeout."""
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes tables in SQLite database if they don't already exist."""
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    need TEXT,
                    weights_json TEXT,
                    created_at REAL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS calls (
                    call_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    shop_id TEXT,
                    shop_name TEXT,
                    lang TEXT,
                    status TEXT,
                    error TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT,
                    speaker TEXT,
                    text TEXT,
                    translation TEXT,
                    lang TEXT,
                    ts REAL,
                    confidence REAL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS offers (
                    call_id TEXT PRIMARY KEY,
                    price INTEGER,
                    first_price INTEGER,
                    warranty_months INTEGER,
                    eta_days INTEGER,
                    part_type TEXT,
                    conditions TEXT,
                    confidence REAL,
                    evidence_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT,
                    field TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    old_ts REAL,
                    new_ts REAL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS timeline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT,
                    text TEXT,
                    ts REAL
                )
                """
            )
            conn.commit()
    except Exception as exc:
        logger.error("Failed to initialize SQLite database (%s): %s", type(exc).__name__, exc)


def save_job(job: Job, db_path: Optional[str] = None) -> None:
    """Saves a Job record to in-memory store and SQLite."""
    _mem_jobs[job.job_id] = job
    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (job_id, need, weights_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (job.job_id, job.need, job.weights.model_dump_json(), job.created_at),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("SQLite write failed for save_job, kept in-memory (%s): %s", type(exc).__name__, exc)


def get_job(job_id: str, db_path: Optional[str] = None) -> Optional[Job]:
    """Retrieves a Job by job_id, falling back to memory if DB fails."""
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT job_id, need, weights_json, created_at FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                weights = Weights.model_validate_json(row["weights_json"])
                return Job(
                    job_id=row["job_id"],
                    need=row["need"],
                    weights=weights,
                    created_at=row["created_at"],
                )
    except Exception as exc:
        logger.warning("SQLite read failed for get_job: %s", exc)

    return _mem_jobs.get(job_id)


def save_call(call: Call, db_path: Optional[str] = None) -> None:
    """Saves or updates a Call status and metadata."""
    _mem_calls[call.call_id] = call
    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO calls (call_id, job_id, shop_id, shop_name, lang, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (call.call_id, call.job_id, call.shop_id, call.shop_name, call.lang, call.status, call.error),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("SQLite write failed for save_call: %s", exc)


def get_call(call_id: str, db_path: Optional[str] = None) -> Optional[Call]:
    """Retrieves a Call by call_id."""
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT call_id, job_id, shop_id, shop_name, lang, status, error FROM calls WHERE call_id = ?", (call_id,))
            row = cur.fetchone()
            if row:
                return Call(
                    call_id=row["call_id"],
                    job_id=row["job_id"],
                    shop_id=row["shop_id"],
                    shop_name=row["shop_name"],
                    lang=row["lang"],
                    status=row["status"],
                    error=row["error"],
                )
    except Exception as exc:
        logger.warning("SQLite read failed for get_call: %s", exc)

    return _mem_calls.get(call_id)


def get_calls_for_job(job_id: str, db_path: Optional[str] = None) -> List[Call]:
    """Retrieves all calls associated with a job."""
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT call_id, job_id, shop_id, shop_name, lang, status, error FROM calls WHERE job_id = ?", (job_id,))
            rows = cur.fetchall()
            if rows:
                return [
                    Call(
                        call_id=r["call_id"],
                        job_id=r["job_id"],
                        shop_id=r["shop_id"],
                        shop_name=r["shop_name"],
                        lang=r["lang"],
                        status=r["status"],
                        error=r["error"],
                    )
                    for r in rows
                ]
    except Exception as exc:
        logger.warning("SQLite read failed for get_calls_for_job: %s", exc)

    return [c for c in _mem_calls.values() if c.job_id == job_id]


def add_turn(turn: Turn, db_path: Optional[str] = None) -> None:
    """Records a spoken or typed dialogue turn."""
    _mem_turns.append(turn)
    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO turns (call_id, speaker, text, translation, lang, ts, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (turn.call_id, turn.speaker, turn.text, turn.translation, turn.lang, turn.ts, turn.confidence),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("SQLite write failed for add_turn: %s", exc)


def get_turns_for_call(call_id: str, db_path: Optional[str] = None) -> List[Turn]:
    """Retrieves all dialogue turns for a call ordered by timestamp."""
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT call_id, speaker, text, translation, lang, ts, confidence
                FROM turns WHERE call_id = ? ORDER BY ts ASC
                """,
                (call_id,),
            )
            rows = cur.fetchall()
            if rows:
                return [
                    Turn(
                        call_id=r["call_id"],
                        speaker=r["speaker"],
                        text=r["text"],
                        translation=r["translation"],
                        lang=r["lang"],
                        ts=r["ts"],
                        confidence=r["confidence"],
                    )
                    for r in rows
                ]
    except Exception as exc:
        logger.warning("SQLite read failed for get_turns_for_call: %s", exc)

    return [t for t in _mem_turns if t.call_id == call_id]


def upsert_offer(offer: Offer, db_path: Optional[str] = None) -> None:
    """Updates the extracted offer figures for a call."""
    _mem_offers[offer.call_id] = offer
    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO offers
                (call_id, price, first_price, warranty_months, eta_days, part_type, conditions, confidence, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    offer.call_id,
                    offer.price,
                    offer.first_price,
                    offer.warranty_months,
                    offer.eta_days,
                    offer.part_type,
                    offer.conditions,
                    offer.confidence,
                    json.dumps(offer.evidence),
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("SQLite write failed for upsert_offer: %s", exc)


def get_offer(call_id: str, db_path: Optional[str] = None) -> Optional[Offer]:
    """Retrieves latest offer extracted for a call."""
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT call_id, price, first_price, warranty_months, eta_days, part_type, conditions, confidence, evidence_json
                FROM offers WHERE call_id = ?
                """,
                (call_id,),
            )
            r = cur.fetchone()
            if r:
                return Offer(
                    call_id=r["call_id"],
                    price=r["price"],
                    first_price=r["first_price"],
                    warranty_months=r["warranty_months"],
                    eta_days=r["eta_days"],
                    part_type=r["part_type"],
                    conditions=r["conditions"],
                    confidence=r["confidence"],
                    evidence=json.loads(r["evidence_json"] or "{}"),
                )
    except Exception as exc:
        logger.warning("SQLite read failed for get_offer: %s", exc)

    return _mem_offers.get(call_id)


def get_offers_for_job(job_id: str, db_path: Optional[str] = None) -> Dict[str, Offer]:
    """Returns a mapping of call_id -> Offer for all calls belonging to a job."""
    calls = get_calls_for_job(job_id, db_path=db_path)
    result: Dict[str, Offer] = {}
    for c in calls:
        offer = get_offer(c.call_id, db_path=db_path)
        if offer:
            result[c.call_id] = offer
    return result


def add_conflict(conflict: ConflictEvent, db_path: Optional[str] = None) -> None:
    """Stores a detected offer discrepancy."""
    _mem_conflicts.append(conflict)
    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO conflicts (call_id, field, old_value, new_value, old_ts, new_ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conflict.call_id, conflict.field, conflict.old_value, conflict.new_value, conflict.old_ts, conflict.new_ts),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("SQLite write failed for add_conflict: %s", exc)


def get_conflicts_for_job(job_id: str, db_path: Optional[str] = None) -> List[ConflictEvent]:
    """Retrieves all conflict events across all calls of a job."""
    calls = get_calls_for_job(job_id, db_path=db_path)
    call_ids = {c.call_id for c in calls}
    conflicts: List[ConflictEvent] = []
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT call_id, field, old_value, new_value, old_ts, new_ts FROM conflicts")
            for r in cur.fetchall():
                if r["call_id"] in call_ids:
                    conflicts.append(
                        ConflictEvent(
                            call_id=r["call_id"],
                            field=r["field"],
                            old_value=r["old_value"],
                            new_value=r["new_value"],
                            old_ts=r["old_ts"],
                            new_ts=r["new_ts"],
                        )
                    )
            return conflicts
    except Exception as exc:
        logger.warning("SQLite read failed for get_conflicts_for_job: %s", exc)

    return [c for c in _mem_conflicts if c.call_id in call_ids]


def add_timeline_event(event: TimelineEvent, db_path: Optional[str] = None) -> None:
    """Records an event on the job timeline."""
    _mem_timeline.append(event)
    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO timeline (call_id, text, ts)
                VALUES (?, ?, ?)
                """,
                (event.call_id, event.text, event.ts),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("SQLite write failed for add_timeline_event: %s", exc)


def get_timeline_for_job(job_id: str, db_path: Optional[str] = None) -> List[TimelineEvent]:
    """Returns chronological timeline events associated with this job's calls."""
    calls = get_calls_for_job(job_id, db_path=db_path)
    call_ids = {c.call_id for c in calls}
    events: List[TimelineEvent] = []
    try:
        with _get_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT call_id, text, ts FROM timeline ORDER BY ts ASC")
            for r in cur.fetchall():
                if r["call_id"] is None or r["call_id"] in call_ids:
                    events.append(
                        TimelineEvent(
                            call_id=r["call_id"],
                            text=r["text"],
                            ts=r["ts"],
                        )
                    )
            return events
    except Exception as exc:
        logger.warning("SQLite read failed for get_timeline_for_job: %s", exc)

    return [e for e in _mem_timeline if e.call_id is None or e.call_id in call_ids]
