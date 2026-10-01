import hashlib
import hmac
import json
import os

# env must be set before the app is imported
os.environ["ADMIN_EMAILS"] = "admin@example.com"
os.environ["WEBHOOK_SECRET"] = "test-secret"

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, email, password="password123"):
    client.post("/auth/signup", json={"email": email, "password": password})
    res = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "admin@example.com")


@pytest.fixture()
def user(client):
    return login(client, "user@example.com")


@pytest.fixture()
def catalogue(client, admin):
    """One centre offering one test at 500."""
    centre = client.post(
        "/centres", json={"name": "City Labs", "location": "Delhi"}, headers=admin
    ).json()
    test = client.post("/tests", json={"name": "CBC"}, headers=admin).json()
    client.post(
        f"/centres/{centre['id']}/tests",
        json={"test_id": test["id"], "price": "500.00"},
        headers=admin,
    )
    return {"centre_id": centre["id"], "test_id": test["id"]}


def future_time(days=2):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture()
def booking(client, user, catalogue):
    res = client.post(
        "/bookings",
        json={**catalogue, "appointment_at": future_time()},
        headers=user,
    )
    assert res.status_code == 201
    return res.json()


def send_webhook(client, payload, secret="test-secret"):
    body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/payments/webhook/",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"},
    )
