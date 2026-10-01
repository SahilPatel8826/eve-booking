# Diagnostic Test Booking API

Backend for booking diagnostic tests at centres, with a simulated payment
flow and an idempotent payment webhook. Built with FastAPI, SQLAlchemy and PostgreSQL.

## Running it

**Docker (easiest)**

```bash
docker compose up --build
```

API on http://localhost:8000, Swagger docs on http://localhost:8000/docs.
Anyone who signs up with `admin@example.com` becomes an admin (set via `ADMIN_EMAILS`).

**Without Docker**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then export the vars, or set them in your shell
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/eve
export ADMIN_EMAILS=admin@example.com
uvicorn app.main:app --reload
```

You need a Postgres database called `eve`. Tables are created on startup.

**Tests** (use in-memory SQLite, no Postgres needed)

```bash
pytest
```

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/signup` | – | email + password (min 8 chars) |
| POST | `/auth/login` | – | returns a JWT |
| POST | `/centres` | admin | create centre |
| GET | `/centres` | – | `?location=`, `?limit=`, `?offset=` |
| GET | `/centres/{id}` | – | |
| POST | `/tests` | admin | add a test type |
| GET | `/tests` | – | |
| POST | `/centres/{id}/tests` | admin | centre offers a test at a price |
| GET | `/centres/{id}/tests` | – | tests + prices for a centre |
| POST | `/bookings` | user | create booking (status PENDING) |
| GET | `/bookings` | user | your bookings only |
| GET | `/bookings/{id}` | user | |
| POST | `/bookings/{id}/cancel` | user | PENDING or CONFIRMED only |
| POST | `/payments/` | user | mock payment |
| POST | `/payments/webhook/` | HMAC signature | provider callback |

### Example requests

```bash
# sign up + log in
curl -X POST localhost:8000/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"password123"}'
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"password123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# set up a centre with a test (admin)
curl -X POST localhost:8000/centres -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"City Labs","location":"Delhi"}'
curl -X POST localhost:8000/tests -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"CBC"}'
curl -X POST localhost:8000/centres/1/tests -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"test_id":1,"price":"500.00"}'

# book and pay
curl -X POST localhost:8000/bookings -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"centre_id":1,"test_id":1,"appointment_at":"2030-01-15T10:00:00Z"}'
curl -X POST localhost:8000/payments/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"booking_id":1}'
```

`simulate_status` (`"SUCCESS"` or `"FAILED"`) can be added to the payment body to force an outcome.

### Calling the webhook

The provider signs the raw request body with HMAC-SHA256 using `WEBHOOK_SECRET`
and sends the hex digest in `X-Signature`.

```bash
BODY='{"event_id":"evt_123","booking_id":1,"status":"SUCCESS"}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "dev-webhook-secret" | awk '{print $NF}')
curl -X POST localhost:8000/payments/webhook/ -H "X-Signature: $SIG" \
  -H 'Content-Type: application/json' -d "$BODY"
```

Send it twice: the second response is `{"result":"duplicate"}` and nothing changes.

## Database design

- **users**: email (unique), password_hash, is_admin
- **centres**: name, location
- **diagnostic_tests**: name (unique). The catalogue of test types.
- **centre_tests**: centre_id, test_id, price. Unique on (centre_id, test_id). Price lives here because each centre prices differently.
- **bookings**: user_id, centre_id, test_id, appointment_at, amount, status. `amount` is copied from the price when booking, so later price changes don't touch old bookings.
- **payments**: booking_id, amount, status, source (API/WEBHOOK), provider_ref (unique)
- **webhook_events**: event_id (unique), booking_id, status, outcome (APPLIED/IGNORED)

### Booking states

```
PENDING   -> CONFIRMED | FAILED | CANCELLED
CONFIRMED -> CANCELLED
FAILED, CANCELLED are final
```

The allowed moves are in `app/services.py`.

### How the webhook stays idempotent

1. The booking row is locked (`SELECT ... FOR UPDATE`).
2. The `event_id` is inserted into `webhook_events`, which has a unique constraint.
3. If that insert fails, the event was already handled: roll back, return 200 `duplicate`. No payment is created and the booking is untouched.
4. If it succeeds and the booking is still PENDING, a payment is recorded and the booking moves to CONFIRMED/FAILED. If the booking is already in another state, the event is stored as IGNORED and the booking is left alone (so a late FAILED can't undo a CONFIRMED).

The unique constraint is the real guarantee, so this also holds with several workers.

## Assumptions

- Only admins create centres/tests/prices; there are no roles beyond that.
- A FAILED payment is final for that booking, the user books again. Retrying payment on the same booking would be easy to add but I kept the state machine small.
- Cancelling doesn't trigger a refund, since there's no real payment gateway.
- Another user's booking returns 404 instead of 403 so booking ids can't be guessed.
- Appointment times without a timezone are treated as UTC.
- No slot/capacity limits per centre. Double booking the same slot is allowed.
- The webhook is authenticated with a shared-secret HMAC signature.

## With more time

- Alembic migrations instead of `create_all` on startup
- Appointment slots and capacity per centre
- Retry payment on a failed booking, and expire PENDING bookings that never get paid
- Refresh tokens and rate limiting on login
- Redis caching for the centre listing
- Webhook timestamp in the signature to stop replays with old signed bodies
- Concurrency test against real Postgres (the tests use SQLite, which ignores row locks)
