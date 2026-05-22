"""Balance computation accuracy."""
from tests.conftest import make_event


def test_balance_empty_account_is_zero(client):
    bal = client.get("/accounts/unknown/balance").json()
    assert bal["balance"] == 0.0
    assert bal["eventCount"] == 0


def test_balance_credits_minus_debits(client):
    client.post("/events", json=make_event(eventId="c1", type="CREDIT", amount=500.0))
    client.post("/events", json=make_event(eventId="c2", type="CREDIT", amount=250.0))
    client.post("/events", json=make_event(eventId="d1", type="DEBIT", amount=125.50))

    bal = client.get("/accounts/acct-123/balance").json()
    assert bal["balance"] == 624.50  # 750 - 125.50


def test_balance_can_go_negative(client):
    client.post("/events", json=make_event(eventId="c1", type="CREDIT", amount=10.0))
    client.post("/events", json=make_event(eventId="d1", type="DEBIT", amount=40.0))

    bal = client.get("/accounts/acct-123/balance").json()
    assert bal["balance"] == -30.0


def test_balance_is_per_account(client):
    client.post("/events", json=make_event(eventId="a1", accountId="A", amount=100.0))
    client.post("/events", json=make_event(eventId="b1", accountId="B", amount=70.0))

    assert client.get("/accounts/A/balance").json()["balance"] == 100.0
    assert client.get("/accounts/B/balance").json()["balance"] == 70.0


def test_balance_rounds_to_two_decimals(client):
    client.post("/events", json=make_event(eventId="c1", type="CREDIT", amount=0.1))
    client.post("/events", json=make_event(eventId="c2", type="CREDIT", amount=0.2))

    bal = client.get("/accounts/acct-123/balance").json()
    assert bal["balance"] == 0.30  # not 0.30000000000000004
