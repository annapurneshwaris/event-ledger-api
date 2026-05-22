"""Out-of-order tolerance: listing must be chronological and balance correct
regardless of arrival order."""
from tests.conftest import make_event


def test_listing_is_chronological_regardless_of_arrival_order(client):
    # Submit deliberately out of timestamp order.
    client.post("/events", json=make_event(
        eventId="evt-c", eventTimestamp="2026-05-15T16:00:00Z"))
    client.post("/events", json=make_event(
        eventId="evt-a", eventTimestamp="2026-05-15T08:00:00Z"))
    client.post("/events", json=make_event(
        eventId="evt-b", eventTimestamp="2026-05-15T12:00:00Z"))

    items = client.get("/events", params={"account": "acct-123"}).json()["items"]
    ids = [e["eventId"] for e in items]
    assert ids == ["evt-a", "evt-b", "evt-c"]


def test_late_arriving_earlier_event_sorts_first(client):
    client.post("/events", json=make_event(
        eventId="evt-late", eventTimestamp="2026-05-10T00:00:00Z"))
    client.post("/events", json=make_event(
        eventId="evt-first-seen", eventTimestamp="2026-05-20T00:00:00Z"))

    items = client.get("/events", params={"account": "acct-123"}).json()["items"]
    assert items[0]["eventId"] == "evt-late"


def test_balance_correct_regardless_of_order(client):
    # Arrive: CREDIT 200 (late ts), DEBIT 50 (early ts), CREDIT 30 (mid ts)
    client.post("/events", json=make_event(
        eventId="e1", type="CREDIT", amount=200, eventTimestamp="2026-05-15T18:00:00Z"))
    client.post("/events", json=make_event(
        eventId="e2", type="DEBIT", amount=50, eventTimestamp="2026-05-15T06:00:00Z"))
    client.post("/events", json=make_event(
        eventId="e3", type="CREDIT", amount=30, eventTimestamp="2026-05-15T12:00:00Z"))

    bal = client.get("/accounts/acct-123/balance").json()
    assert bal["balance"] == 180.0  # 200 + 30 - 50
    assert bal["eventCount"] == 3
