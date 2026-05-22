"""Idempotency: duplicate submissions must not create duplicates or alter balance."""
from tests.conftest import make_event


def test_first_submission_returns_201(client):
    resp = client.post("/events", json=make_event())
    assert resp.status_code == 201
    assert resp.json()["eventId"] == "evt-001"


def test_duplicate_submission_returns_200_and_original(client):
    payload = make_event()
    first = client.post("/events", json=payload)
    assert first.status_code == 201

    # Re-submit the SAME eventId, even with different field values.
    dupe = client.post("/events", json=make_event(amount=999.99, type="DEBIT"))
    assert dupe.status_code == 200
    # The original event is returned unchanged, not the new values.
    assert dupe.json()["amount"] == 150.00
    assert dupe.json()["type"] == "CREDIT"


def test_duplicate_does_not_create_second_row(client):
    client.post("/events", json=make_event())
    client.post("/events", json=make_event())
    client.post("/events", json=make_event())

    listing = client.get("/events", params={"account": "acct-123"})
    assert listing.json()["pagination"]["total"] == 1


def test_duplicate_does_not_alter_balance(client):
    client.post("/events", json=make_event(amount=100.0))
    # Same id submitted twice more -> balance must stay at 100, not 300.
    client.post("/events", json=make_event(amount=100.0))
    client.post("/events", json=make_event(amount=100.0))

    bal = client.get("/accounts/acct-123/balance").json()
    assert bal["balance"] == 100.0
    assert bal["eventCount"] == 1
