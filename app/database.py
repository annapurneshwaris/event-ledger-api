"""Database layer: engine, session factory, and ORM models.

Design notes
------------
* ``Event.event_id`` is the PRIMARY KEY. This pushes idempotency down to the
  storage engine: a duplicate insert raises an IntegrityError that we catch,
  rather than relying on a check-then-insert that would race under concurrency.
* Events are treated as IMMUTABLE. We never UPDATE an event row. Balance and
  ordering are derived at read time, which makes out-of-order arrival a
  non-issue by construction.
* ``AuditLog`` is append-only and records every state-changing attempt
  (created / duplicate / rejected) so the ledger has a tamper-evident trail.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

# check_same_thread=False is required for SQLite under a threaded server.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    # Natural primary key -> storage-enforced idempotency.
    event_id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False)
    type = Column(String, nullable=False)  # CREDIT | DEBIT
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    event_metadata = Column(Text, nullable=True)  # JSON-encoded blob
    received_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        # Listing events for an account ordered by event time is the hot path.
        Index("ix_events_account_ts", "account_id", "event_timestamp"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    action = Column(String, nullable=False)  # EVENT_CREATED | DUPLICATE_IGNORED | EVENT_REJECTED
    detail = Column(Text, nullable=True)
    request_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
