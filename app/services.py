from sqlalchemy.orm import Session

from .models import Booking, BookingStatus, Payment, PaymentStatus

# which statuses a booking is allowed to move to from each state
ALLOWED_TRANSITIONS = {
    BookingStatus.PENDING: {
        BookingStatus.CONFIRMED,
        BookingStatus.FAILED,
        BookingStatus.CANCELLED,
    },
    BookingStatus.CONFIRMED: {BookingStatus.CANCELLED},
    BookingStatus.FAILED: set(),
    BookingStatus.CANCELLED: set(),
}


def can_move(current: str, new: BookingStatus) -> bool:
    return new in ALLOWED_TRANSITIONS[BookingStatus(current)]


def record_payment(
    db: Session, booking: Booking, status: str, source: str, provider_ref: str
) -> Payment:
    """Save a payment and move the booking to CONFIRMED / FAILED.
    Caller must have checked the booking is PENDING."""
    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status=status,
        source=source,
        provider_ref=provider_ref,
    )
    booking.status = (
        BookingStatus.CONFIRMED.value
        if status == PaymentStatus.SUCCESS.value
        else BookingStatus.FAILED.value
    )
    db.add(payment)
    return payment
