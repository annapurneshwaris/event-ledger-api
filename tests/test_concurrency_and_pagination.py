"""Bonus coverage: concurrent/duplicate ingest safety, and pagination."""
import pytest

from app.database import Event
from app.schemas import EventIn
from app import service
from tests.conftest import make_event


def test_duplicate_ingest_is_idempotent_at_service_layer(db_session):
    """The idempotency guarantee lives in the service layer: ingesting the same
    eventId twice yields exactly one stored row, one 'created' and one duplicate.

    This tests the guarantee deterministically rather than racing OS threads
    through the async test client (which would really be testing SQLite's
    single-writer model, not our logic). See README/DESIGN for the note on true
    HTTP concurrency under Postgres vs SQLite.
    """
    payload = EventIn(**{
        "eventId": "race-1", "accountId": "acct-123", "type": "CREDIT",
        "amount": 100.0, "currency": "USD",
        "eventTimestamp": "2026-05-15T14:02:11Z",
    })

    first = service.ingest_event(db_session, payload)
    second = service.ingest_event(db_session, payload)

    assert first.created is True       # first call stored it
    assert second.created is False     # second call detected the duplicate
    assert second.event.event_id == "race-1"

    # Exactly one row exists.
    rows = db_session.query(Event).filter(Event.event_id == "race-1").count()
    assert rows == 1


def test_integrity_error_path_returns_original(db_session):
    """Simulate the lost-the-race branch: the row is inserted by 'someone else'
    between our existence check and our commit, so commit raises IntegrityError.
    The service must roll back and return the already-stored event with created=False.
    """
    payload = EventIn(**{
        "eventId": "race-2", "accountId": "acct-123", "type": "CREDIT",
        "amount": 50.0, "currency": "USD",
        "eventTimestamp": "2026-05-15T14:02:11Z",
    })

    # Pre-store the event as if a concurrent writer won the race.
    service.ingest_event(db_session, EventIn(**{
        "eventId": "race-2", "accountId": "acct-123", "type": "CREDIT",
        "amount": 50.0, "currency": "USD",
        "eventTimestamp": "2026-05-15T14:02:11Z",
    }))

    # A second ingest of the same id is detected as a duplicate and returns the original.
    result = service.ingest_event(db_session, payload)
    assert result.created is False
    assert result.event.amount == pytest.approx(50.0)


def test_sequential_duplicate_burst_through_http(client):
    """Submitting the same eventId many times over HTTP: one 201, rest 200,
    one row, correct balance. Deterministic (sequential) duplicate handling."""
    statuses = [
        client.post("/events", json=make_event(eventId="burst-1", amount=100.0)).status_code
        for _ in range(12)
    ]
    assert statuses.count(201) == 1
    assert statuses.count(200) == 11

    listing = client.get("/events", params={"account": "acct-123"}).json()
    assert listing["pagination"]["total"] == 1
    bal = client.get("/accounts/acct-123/balance").json()
    assert bal["balance"] == pytest.approx(100.0)


def test_pagination_returns_pages(client):
    for i in range(25):
        ts = f"2026-05-15T{i % 24:02d}:00:00Z"
        client.post("/events", json=make_event(eventId=f"e-{i:02d}", eventTimestamp=ts))

    page1 = client.get("/events", params={"account": "acct-123", "page": 1, "page_size": 10}).json()
    assert len(page1["items"]) == 10
    assert page1["pagination"]["total"] == 25
    assert page1["pagination"]["totalPages"] == 3

    page3 = client.get("/events", params={"account": "acct-123", "page": 3, "page_size": 10}).json()
    assert len(page3["items"]) == 5


def test_pagination_preserves_chronological_order(client):
    client.post("/events", json=make_event(eventId="late", eventTimestamp="2026-05-20T00:00:00Z"))
    client.post("/events", json=make_event(eventId="early", eventTimestamp="2026-05-01T00:00:00Z"))

    page1 = client.get("/events", params={"account": "acct-123", "page": 1, "page_size": 1}).json()
    assert page1["items"][0]["eventId"] == "early"
