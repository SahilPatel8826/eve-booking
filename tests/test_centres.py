def test_list_centres_and_tests(client, catalogue):
    centres = client.get("/centres").json()
    assert len(centres) == 1

    tests = client.get(f"/centres/{catalogue['centre_id']}/tests").json()
    assert tests[0]["test_name"] == "CBC"
    assert float(tests[0]["price"]) == 500.0


def test_location_filter_and_pagination(client, admin):
    for i in range(3):
        client.post("/centres", json={"name": f"C{i}", "location": "Pune"}, headers=admin)
    client.post("/centres", json={"name": "Other", "location": "Delhi"}, headers=admin)

    assert len(client.get("/centres?location=pune").json()) == 3
    assert len(client.get("/centres?limit=2").json()) == 2
    assert client.get("/centres?limit=0").status_code == 422


def test_unknown_centre(client):
    assert client.get("/centres/999").status_code == 404
    assert client.get("/centres/999/tests").status_code == 404


def test_duplicate_offering(client, admin, catalogue):
    res = client.post(
        f"/centres/{catalogue['centre_id']}/tests",
        json={"test_id": catalogue["test_id"], "price": "100"},
        headers=admin,
    )
    assert res.status_code == 409


def test_negative_price_rejected(client, admin, catalogue):
    t = client.post("/tests", json={"name": "LFT"}, headers=admin).json()
    res = client.post(
        f"/centres/{catalogue['centre_id']}/tests",
        json={"test_id": t["id"], "price": "-5"},
        headers=admin,
    )
    assert res.status_code == 422
