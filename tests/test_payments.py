from app.models import Booking, Payment, WebhookEvent

from .conftest import login, send_webhook


def pay(client, user, booking_id, status="SUCCESS"):
    return client.post(
        "/payments/", json={"booking_id": booking_id, "simulate_status": status}, headers=user
    )


def test_successful_payment_confirms_booking(client, user, booking):
    res = pay(client, user, booking["id"])
    assert res.status_code == 201
    assert res.json()["booking_status"] == "CONFIRMED"


def test_failed_payment_fails_booking(client, user, booking):
    assert pay(client, user, booking["id"], "FAILED").json()["booking_status"] == "FAILED"


def test_cannot_pay_twice(client, user, booking):
    pay(client, user, booking["id"])
    assert pay(client, user, booking["id"]).status_code == 409


def test_cannot_pay_for_other_users_booking(client, booking):
    other = login(client, "other@example.com")
    assert pay(client, other, booking["id"]).status_code == 404


def test_payment_needs_auth_and_valid_body(client, user, booking):
    assert client.post("/payments/", json={"booking_id": booking["id"]}).status_code == 401
    assert client.post("/payments/", json={}, headers=user).status_code == 422
    assert pay(client, user, booking["id"], "MAYBE").status_code == 422
    assert pay(client, user, 12345).status_code == 404


# ---- webhook ----

def test_webhook_confirms_booking(client, user, booking):
    res = send_webhook(client, {"event_id": "evt_1", "booking_id": booking["id"], "status": "SUCCESS"})
    assert res.status_code == 200
    assert res.json()["result"] == "applied"
    assert client.get(f"/bookings/{booking['id']}", headers=user).json()["status"] == "CONFIRMED"


def test_webhook_is_idempotent(client, user, booking, session_factory):
    payload = {"event_id": "evt_1", "booking_id": booking["id"], "status": "SUCCESS"}
    results = [send_webhook(client, payload) for _ in range(3)]

    assert all(r.status_code == 200 for r in results)
    assert [r.json()["result"] for r in results] == ["applied", "duplicate", "duplicate"]

    db = session_factory()
    assert db.query(Payment).count() == 1
    assert db.query(WebhookEvent).count() == 1
    assert db.query(Booking).count() == 1
    assert db.query(Booking).first().status == "CONFIRMED"


def test_late_failed_event_does_not_undo_confirmed(client, user, booking, session_factory):
    send_webhook(client, {"event_id": "evt_1", "booking_id": booking["id"], "status": "SUCCESS"})
    res = send_webhook(client, {"event_id": "evt_2", "booking_id": booking["id"], "status": "FAILED"})

    assert res.json()["result"] == "ignored"
    assert client.get(f"/bookings/{booking['id']}", headers=user).json()["status"] == "CONFIRMED"
    assert session_factory().query(Payment).count() == 1


def test_webhook_after_api_payment_is_ignored(client, user, booking, session_factory):
    pay(client, user, booking["id"])
    res = send_webhook(client, {"event_id": "evt_9", "booking_id": booking["id"], "status": "SUCCESS"})
    assert res.json()["result"] == "ignored"
    assert session_factory().query(Payment).count() == 1


def test_webhook_cannot_revive_cancelled_booking(client, user, booking):
    client.post(f"/bookings/{booking['id']}/cancel", headers=user)
    send_webhook(client, {"event_id": "evt_1", "booking_id": booking["id"], "status": "SUCCESS"})
    assert client.get(f"/bookings/{booking['id']}", headers=user).json()["status"] == "CANCELLED"


def test_webhook_bad_signature(client, booking):
    res = send_webhook(
        client,
        {"event_id": "evt_1", "booking_id": booking["id"], "status": "SUCCESS"},
        secret="wrong-secret",
    )
    assert res.status_code == 401


def test_webhook_bad_payload_and_unknown_booking(client, booking):
    assert send_webhook(client, {"event_id": "e", "booking_id": booking["id"], "status": "NOPE"}).status_code == 422
    assert send_webhook(client, {"booking_id": booking["id"], "status": "SUCCESS"}).status_code == 422
    assert send_webhook(client, {"event_id": "e", "booking_id": 9999, "status": "SUCCESS"}).status_code == 404
