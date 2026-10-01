from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    is_admin: bool

    model_config = {"from_attributes": True}


class CentreIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=255)


class CentreOut(CentreIn):
    id: int

    model_config = {"from_attributes": True}


class TestIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TestOut(TestIn):
    id: int

    model_config = {"from_attributes": True}


class OfferingIn(BaseModel):
    test_id: int
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class OfferingOut(BaseModel):
    test_id: int
    test_name: str
    price: Decimal

    model_config = {"from_attributes": True}


class BookingIn(BaseModel):
    centre_id: int
    test_id: int
    appointment_at: datetime


class BookingOut(BaseModel):
    id: int
    centre_id: int
    test_id: int
    appointment_at: datetime
    amount: Decimal
    status: str

    model_config = {"from_attributes": True}


class PaymentIn(BaseModel):
    booking_id: int
    # only meant for demos/tests, leave it out to get a random result
    simulate_status: Optional[Literal["SUCCESS", "FAILED"]] = None


class PaymentOut(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    status: str
    booking_status: str


class WebhookIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    booking_id: int
    status: Literal["SUCCESS", "FAILED"]
