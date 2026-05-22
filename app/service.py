"""Business logic for the event ledger.

Kept separate from the HTTP layer so it can be unit-tested directly and so the
transactional + idempotency logic lives in one place.
"""
import json
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import AuditLog, Event
from app.logging_config import get_logger, request_id_ctx
from app.schemas import EventIn

logger = get_logger("ledger.service")


@dataclass
class IngestResult:
    event: Event
    created: bool  # True -> newly stored (201); False -> duplicate (200)


def _audit(db: Session, action: str, *, event_id=None, account_id=None, detail=None) -> None:
    db.add(
        AuditLog(
            event_id=event_id,
            account_id=account_id,
            action=action,
            detail=detail,
            request_id=request_id_ctx.get(),
        )
    )


def get_event(db: Session, event_id: str) -> Optional[Event]:
    return db.get(Event, event_id)


def ingest_event(db: Session, payload: EventIn) -> IngestResult:
    """Store an event idempotently.

    Strategy: optimistic insert. We attempt the INSERT and let the primary-key
    constraint reject duplicates. This is race-free under concurrent POSTs for
    the same eventId because the database, not the application, arbitrates the
    winner. The loser catches IntegrityError and returns the stored row.
    """
    existing = db.get(Event, payload.event_id)
    if existing is not None:
        _audit(
            db,
            "DUPLICATE_IGNORED",
            event_id=payload.event_id,
            account_id=payload.account_id,
            detail="eventId already present; returning original",
        )
        db.commit()
        logger.info(
            "duplicate event ignored",
            extra={"context": {"event_id": payload.event_id, "outcome": "duplicate"}},
        )
        return IngestResult(event=existing, created=False)

    event = Event(
        event_id=payload.event_id,
        account_id=payload.account_id,
        type=payload.type.value,
        amount=payload.amount,
        currency=payload.currency,
        event_timestamp=payload.event_timestamp,
        event_metadata=json.dumps(payload.metadata) if payload.metadata else None,
    )
    db.add(event)
    _audit(
        db,
        "EVENT_CREATED",
        event_id=payload.event_id,
        account_id=payload.account_id,
        detail=f"{payload.type.value} {payload.amount} {payload.currency}",
    )

    try:
        db.commit()
    except IntegrityError:
        # Lost a concurrent race: another request inserted the same id first.
        db.rollback()
        stored = db.get(Event, payload.event_id)
        logger.info(
            "concurrent duplicate resolved",
            extra={"context": {"event_id": payload.event_id, "outcome": "duplicate_race"}},
        )
        return IngestResult(event=stored, created=False)

    db.refresh(event)
    logger.info(
        "event created",
        extra={
            "context": {
                "event_id": event.event_id,
                "account_id": event.account_id,
                "type": event.type,
                "amount": event.amount,
                "outcome": "created",
            }
        },
    )
    return IngestResult(event=event, created=True)


def list_events_for_account(
    db: Session, account_id: str, page: int, page_size: int
) -> tuple[list[Event], int]:
    """Return events for an account ordered chronologically by event_timestamp.

    Ordering is applied at query time, so the order events were *received* in
    has no effect on the output.
    """
    total = db.scalar(
        select(func.count()).select_from(Event).where(Event.account_id == account_id)
    )
    stmt = (
        select(Event)
        .where(Event.account_id == account_id)
        .order_by(Event.event_timestamp.asc(), Event.event_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    events = list(db.scalars(stmt).all())
    return events, int(total or 0)


def compute_balance(db: Session, account_id: str) -> tuple[float, int, Optional[str]]:
    """Compute net balance = sum(CREDIT) - sum(DEBIT).

    Derived from the immutable event set, so it is correct regardless of the
    order events arrived in. Returns (balance, event_count, currency).
    """
    credit = db.scalar(
        select(func.coalesce(func.sum(Event.amount), 0.0)).where(
            Event.account_id == account_id, Event.type == "CREDIT"
        )
    )
    debit = db.scalar(
        select(func.coalesce(func.sum(Event.amount), 0.0)).where(
            Event.account_id == account_id, Event.type == "DEBIT"
        )
    )
    count = db.scalar(
        select(func.count()).select_from(Event).where(Event.account_id == account_id)
    )
    currency = db.scalar(
        select(Event.currency).where(Event.account_id == account_id).limit(1)
    )
    balance = round(float(credit or 0.0) - float(debit or 0.0), 2)
    return balance, int(count or 0), currency


def event_to_dict(event: Event) -> dict:
    """Map an ORM Event to the API representation (deserializing metadata)."""
    return {
        "event_id": event.event_id,
        "account_id": event.account_id,
        "type": event.type,
        "amount": event.amount,
        "currency": event.currency,
        "event_timestamp": event.event_timestamp,
        "metadata": json.loads(event.event_metadata) if event.event_metadata else None,
        "received_at": event.received_at,
    }
