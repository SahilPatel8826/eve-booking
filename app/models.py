import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Centre(Base):
    __tablename__ = "centres"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    location = Column(String(255), nullable=False, index=True)


class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)


class CentreTest(Base):
    """A test offered by a centre, with that centre's price."""

    __tablename__ = "centre_tests"
    __table_args__ = (UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),)

    id = Column(Integer, primary_key=True)
    centre_id = Column(Integer, ForeignKey("centres.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("diagnostic_tests.id"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    test = relationship("DiagnosticTest")

    @property
    def test_name(self):
        return self.test.name


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("diagnostic_tests.id"), nullable=False)
    appointment_at = Column(DateTime(timezone=True), nullable=False)
    # copied from centre_tests.price at booking time so later price changes
    # don't rewrite old bookings
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default=BookingStatus.PENDING.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False)
    source = Column(String(20), nullable=False)  # "API" or "WEBHOOK"
    provider_ref = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WebhookEvent(Base):
    """Every webhook event_id we have seen. The unique key is what makes
    the webhook idempotent."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True)
    event_id = Column(String(100), unique=True, nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    status = Column(String(20), nullable=False)
    outcome = Column(String(20), nullable=True)  # APPLIED or IGNORED
    received_at = Column(DateTime(timezone=True), server_default=func.now())
