"""Request/response schemas with validation rules.

Validation requirements from the spec are enforced here so bad input is
rejected at the edge with a 422 and a clear message, before touching the DB.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class EventIn(BaseModel):
    """Incoming event payload (POST /events)."""

    event_id: str = Field(..., alias="eventId", min_length=1)
    account_id: str = Field(..., alias="accountId", min_length=1)
    type: EventType
    amount: float = Field(..., gt=0, description="Must be greater than 0")
    currency: str = Field(..., min_length=1)
    event_timestamp: datetime = Field(..., alias="eventTimestamp")
    metadata: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("event_id", "account_id", "currency")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v


class EventOut(BaseModel):
    """Event representation returned to clients."""

    event_id: str = Field(..., serialization_alias="eventId")
    account_id: str = Field(..., serialization_alias="accountId")
    type: EventType
    amount: float
    currency: str
    event_timestamp: datetime = Field(..., serialization_alias="eventTimestamp")
    metadata: Optional[dict] = None
    received_at: datetime = Field(..., serialization_alias="receivedAt")

    model_config = ConfigDict(populate_by_name=True)


class BalanceOut(BaseModel):
    account_id: str = Field(..., serialization_alias="accountId")
    balance: float
    currency: Optional[str] = None
    event_count: int = Field(..., serialization_alias="eventCount")

    model_config = ConfigDict(populate_by_name=True)


class PageMeta(BaseModel):
    page: int
    page_size: int = Field(..., serialization_alias="pageSize")
    total: int
    total_pages: int = Field(..., serialization_alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)


class EventListOut(BaseModel):
    items: list[EventOut]
    pagination: PageMeta
