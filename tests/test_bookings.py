from .conftest import login, future_time


def test_create_booking_copies_price(client, booking):
    assert booking["status"] == "PENDING"
    assert float(booking["amount"]) == 500.0


def test_booking_in_the_past(client, user, catalogue):
    res = client.post(
        "/bookings",
        json={**catalogue, "appointment_at": "2020-01-01T10:00:00Z"},
        headers=user,
    )
    assert res.status_code == 400


def test_centre_does_not_offer_test(client, user, admin, catalogue):
    other = client.post("/tests", json={"name": "Lipid"}, headers=admin).json()
    res = client.post(
        "/bookings",
        json={"centre_id": catalogue["centre_id"], "test_id": other["id"],
              "appointment_at": future_time()},
        headers=user,
    )
    assert res.status_code == 404


def test_bad_booking_id(client, user):
    assert client.get("/bookings/9999", headers=user).status_code == 404
    assert client.get("/bookings/abc", headers=user).status_code == 422


def test_cannot_see_or_cancel_someone_elses_booking(client, booking):
    other = login(client, "other@example.com")
    assert client.get(f"/bookings/{booking['id']}", headers=other).status_code == 404
    assert client.post(f"/bookings/{booking['id']}/cancel", headers=other).status_code == 404
    assert client.get("/bookings", headers=other).json() == []


def test_cancel(client, user, booking):
    res = client.post(f"/bookings/{booking['id']}/cancel", headers=user)
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"
    # cancelling twice is not allowed
    assert client.post(f"/bookings/{booking['id']}/cancel", headers=user).status_code == 409
