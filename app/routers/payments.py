import hmac
import hashlib
import json
import logging
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import WEBHOOK_SECRET
from ..database import get_db
from ..deps import get_current_user
from ..models import Booking, BookingStatus, PaymentStatus, User, WebhookEvent
from ..schemas import PaymentIn, PaymentOut, WebhookIn
from ..services import record_payment
from .bookings import own_booking_or_404

log = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentOut, status_code=201)
def make_payment(
    body: PaymentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mock payment. Succeeds ~80% of the time unless simulate_status is given."""
    booking = own_booking_or_404(db, body.booking_id, user, lock=True)
    if booking.status != BookingStatus.PENDING.value:
        raise HTTPException(
            status_code=409, detail=f"Booking is {booking.status}, only PENDING can be paid"
        )

    outcome = body.simulate_status or (
        PaymentStatus.SUCCESS.value if random.random() < 0.8 else PaymentStatus.FAILED.value
    )
    payment = record_payment(db, booking, outcome, "API", f"mock_{uuid.uuid4().hex}")
    db.commit()
    db.refresh(payment)
    log.info("payment id=%s booking=%s status=%s", payment.id, booking.id, outcome)
    return PaymentOut(
        id=payment.id,
        booking_id=booking.id,
        amount=payment.amount,
        status=payment.status,
        booking_status=booking.status,
    )


async def verified_body(request: Request) -> bytes:
    """Reads the raw body and checks the HMAC signature from the provider."""
    raw = await request.body()
    signature = request.headers.get("X-Signature", "")
    expected = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return raw


@router.post("/webhook/")
def payment_webhook(raw: bytes = Depends(verified_body), db: Session = Depends(get_db)):
    try:
        event = WebhookIn.model_validate_json(raw)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=json.loads(e.json()))

    # lock the booking first so two copies of the same event can't run together
    booking = (
        db.query(Booking).filter(Booking.id == event.booking_id).with_for_update().first()
    )
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    # event_id is unique, so a repeated event fails here and changes nothing
    record = WebhookEvent(
        event_id=event.event_id, booking_id=booking.id, status=event.status
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        log.info("duplicate webhook event_id=%s ignored", event.event_id)
        return {"result": "duplicate"}

    if booking.status == BookingStatus.PENDING.value:
        record_payment(db, booking, event.status, "WEBHOOK", event.event_id)
        record.outcome = "APPLIED"
    else:
        # e.g. a late FAILED for a booking that is already CONFIRMED / CANCELLED
        record.outcome = "IGNORED"
        log.warning(
            "webhook event_id=%s ignored, booking %s is %s",
            event.event_id, booking.id, booking.status,
        )
    db.commit()
    return {"result": record.outcome.lower(), "booking_status": booking.status}
