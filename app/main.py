"""HTTP layer: FastAPI app, middleware, routes, and error handling."""
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import service
from app.config import get_settings
from app.database import get_db, init_db
from app.logging_config import configure_logging, get_logger, request_id_ctx
from app.schemas import (
    BalanceOut,
    EventIn,
    EventListOut,
    EventOut,
    PageMeta,
)

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("ledger.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("application started", extra={"context": {"db": settings.database_url}})
    yield


app = FastAPI(
    title="Event Ledger API",
    description=(
        "Receives financial transaction events from multiple upstream systems. "
        "Handles out-of-order delivery and at-least-once (duplicate) delivery."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Attach a request id to every request for log correlation."""
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_ctx.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return clear, structured validation errors with a 422."""
    logger.info(
        "validation failed",
        extra={"context": {"path": str(request.url.path), "errors": exc.errors().__len__()}},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": "validation_error",
            "message": "Request payload failed validation.",
            "details": [
                {"field": ".".join(str(p) for p in e["loc"][1:]), "issue": e["msg"]}
                for e in exc.errors()
            ],
        },
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/events",
    response_model=EventOut,
    tags=["events"],
    responses={
        201: {"description": "Event created"},
        200: {"description": "Duplicate eventId; original event returned"},
    },
)
def post_event(payload: EventIn, response: Response, db: Session = Depends(get_db)):
    """Submit a transaction event.

    Idempotent: re-submitting the same ``eventId`` returns the original event
    with status 200 instead of creating a duplicate.
    """
    result = service.ingest_event(db, payload)
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return EventOut(**service.event_to_dict(result.event))


@app.get("/events/{event_id}", response_model=EventOut, tags=["events"])
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = service.get_event(db, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{event_id}' not found",
        )
    return EventOut(**service.event_to_dict(event))


@app.get("/events", response_model=EventListOut, tags=["events"])
def list_events(
    account: str = Query(..., description="Account id to list events for"),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """List events for an account, ordered chronologically by eventTimestamp."""
    size = min(page_size or settings.default_page_size, settings.max_page_size)
    events, total = service.list_events_for_account(db, account, page, size)
    total_pages = (total + size - 1) // size if total else 0
    return EventListOut(
        items=[EventOut(**service.event_to_dict(e)) for e in events],
        pagination=PageMeta(
            page=page, page_size=size, total=total, total_pages=total_pages
        ),
    )


@app.get(
    "/accounts/{account_id}/balance",
    response_model=BalanceOut,
    tags=["accounts"],
)
def get_balance(account_id: str, db: Session = Depends(get_db)):
    """Return the net balance: sum(CREDIT) - sum(DEBIT)."""
    balance, count, currency = service.compute_balance(db, account_id)
    return BalanceOut(
        account_id=account_id, balance=balance, currency=currency, event_count=count
    )
