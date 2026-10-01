from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import ADMIN_EMAILS
from ..database import get_db
from ..models import User
from ..schemas import LoginIn, SignupIn, TokenOut, UserOut
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        is_admin=email in ADMIN_EMAILS,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two signups racing with the same email
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    # same message for both cases so we don't reveal which emails exist
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(access_token=create_token(user.id))
