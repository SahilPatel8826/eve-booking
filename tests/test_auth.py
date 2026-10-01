def test_signup_and_login(client):
    res = client.post("/auth/signup", json={"email": "a@b.com", "password": "password123"})
    assert res.status_code == 201
    assert "password" not in res.text

    res = client.post("/auth/login", json={"email": "a@b.com", "password": "password123"})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_duplicate_signup(client):
    body = {"email": "a@b.com", "password": "password123"}
    client.post("/auth/signup", json=body)
    assert client.post("/auth/signup", json=body).status_code == 409


def test_signup_validation(client):
    assert client.post("/auth/signup", json={"email": "nope", "password": "password123"}).status_code == 422
    assert client.post("/auth/signup", json={"email": "a@b.com", "password": "short"}).status_code == 422


def test_wrong_password(client):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "password123"})
    res = client.post("/auth/login", json={"email": "a@b.com", "password": "wrongpass1"})
    assert res.status_code == 401


def test_protected_routes_need_token(client):
    assert client.get("/bookings").status_code == 401
    assert client.get("/bookings", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_only_admin_can_create_centres(client, user):
    res = client.post("/centres", json={"name": "X", "location": "Y"}, headers=user)
    assert res.status_code == 403
