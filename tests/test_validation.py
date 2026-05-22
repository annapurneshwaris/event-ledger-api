"""Input validation and error handling."""
import pytest

from tests.conftest import make_event


def test_missing_required_field_rejected(client):
    payload = make_event()
    del payload["accountId"]
    resp = client.post("/events", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


@pytest.mark.parametrize("bad_amount", [0, -1, -150.5])
def test_non_positive_amount_rejected(client, bad_amount):
    resp = client.post("/events", json=make_event(amount=bad_amount))
    assert resp.status_code == 422


def test_unknown_event_type_rejected(client):
    resp = client.post("/events", json=make_event(type="TRANSFER"))
    assert resp.status_code == 422


def test_blank_account_id_rejected(client):
    resp = client.post("/events", json=make_event(accountId="   "))
    assert resp.status_code == 422


def test_unknown_extra_field_rejected(client):
    payload = make_event()
    payload["unexpected"] = "nope"
    resp = client.post("/events", json=payload)
    assert resp.status_code == 422


def test_invalid_timestamp_rejected(client):
    resp = client.post("/events", json=make_event(eventTimestamp="not-a-date"))
    assert resp.status_code == 422


def test_get_unknown_event_returns_404(client):
    resp = client.get("/events/does-not-exist")
    assert resp.status_code == 404


def test_validation_error_lists_offending_field(client):
    payload = make_event()
    del payload["currency"]
    details = client.post("/events", json=payload).json()["details"]
    assert any(d["field"] == "currency" for d in details)
