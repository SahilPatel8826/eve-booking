from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import Centre, CentreTest, DiagnosticTest
from ..schemas import CentreIn, CentreOut, OfferingIn, OfferingOut, TestIn, TestOut

router = APIRouter(tags=["centres & tests"])


def get_centre_or_404(db: Session, centre_id: int) -> Centre:
    centre = db.get(Centre, centre_id)
    if centre is None:
        raise HTTPException(status_code=404, detail="Centre not found")
    return centre


# ---- centres ----

@router.post(
    "/centres",
    response_model=CentreOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_centre(body: CentreIn, db: Session = Depends(get_db)):
    centre = Centre(name=body.name.strip(), location=body.location.strip())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get("/centres", response_model=list[CentreOut])
def list_centres(
    location: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Centre)
    if location:
        query = query.filter(Centre.location.ilike(f"%{location}%"))
    return query.order_by(Centre.id).limit(limit).offset(offset).all()


@router.get("/centres/{centre_id}", response_model=CentreOut)
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    return get_centre_or_404(db, centre_id)


# ---- tests (the catalogue of test types) ----

@router.post(
    "/tests",
    response_model=TestOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_test(body: TestIn, db: Session = Depends(get_db)):
    name = body.name.strip()
    if db.query(DiagnosticTest).filter(DiagnosticTest.name == name).first():
        raise HTTPException(status_code=409, detail="Test already exists")
    test = DiagnosticTest(name=name)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.get("/tests", response_model=list[TestOut])
def list_tests(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return db.query(DiagnosticTest).order_by(DiagnosticTest.id).limit(limit).offset(offset).all()


# ---- which tests a centre offers, and at what price ----

@router.post(
    "/centres/{centre_id}/tests",
    response_model=OfferingOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def add_test_to_centre(centre_id: int, body: OfferingIn, db: Session = Depends(get_db)):
    get_centre_or_404(db, centre_id)
    if db.get(DiagnosticTest, body.test_id) is None:
        raise HTTPException(status_code=404, detail="Test not found")
    exists = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == body.test_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Centre already offers this test")

    offering = CentreTest(centre_id=centre_id, test_id=body.test_id, price=body.price)
    db.add(offering)
    db.commit()
    db.refresh(offering)
    return offering


@router.get("/centres/{centre_id}/tests", response_model=list[OfferingOut])
def list_centre_tests(
    centre_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    get_centre_or_404(db, centre_id)
    return (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id)
        .order_by(CentreTest.id)
        .limit(limit)
        .offset(offset)
        .all()
    )
