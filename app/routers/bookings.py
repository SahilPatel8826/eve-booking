import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Booking, BookingStatus, CentreTest, User
from ..schemas import BookingIn, BookingOut
from ..services import can_move

log = logging.getLogger(__name__)
router = APIRouter(prefix="/bookings", tags=["bookings"])


def own_booking_or_404(db: Session, booking_id: int, user: User, lock: bool = False) -> Booking:
    # Someone else's booking gives the same 404 as a missing one,
    # so ids can't be probed.
    query = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id)
    if lock:
        query = query.with_for_update()
    booking = query.first()
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("", response_model=BookingOut, status_code=201)
def create_booking(
    body: BookingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    when = body.appointment_at
    if when.tzinfo is None:  # treat naive datetimes as UTC
        when = when.replace(tzinfo=timezone.utc)
    if when <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Appointment must be in the future")

    offering = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == body.centre_id, CentreTest.test_id == body.test_id)
        .first()
    )
    if offering is None:
        raise HTTPException(status_code=404, detail="This centre does not offer that test")

    booking = Booking(
        user_id=user.id,
        centre_id=body.centre_id,
        test_id=body.test_id,
        appointment_at=when,
        amount=offering.price,
        status=BookingStatus.PENDING.value,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    log.info("booking created id=%s user=%s amount=%s", booking.id, user.id, booking.amount)
    return booking


@router.get("", response_model=list[BookingOut])
def list_my_bookings(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Booking)
        .filter(Booking.user_id == user.id)
        .order_by(Booking.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return own_booking_or_404(db, booking_id, user)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = own_booking_or_404(db, booking_id, user, lock=True)
    if not can_move(booking.status, BookingStatus.CANCELLED):
        raise HTTPException(
            status_code=409, detail=f"Cannot cancel a {booking.status} booking"
        )
    booking.status = BookingStatus.CANCELLED.value
    db.commit()
    db.refresh(booking)
    log.info("booking cancelled id=%s user=%s", booking.id, user.id)
    return booking
