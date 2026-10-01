import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models  # noqa: F401  (needed so the tables get registered)
from .database import Base, engine
from .routers import auth, bookings, centres, payments

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="EVE Diagnostics Booking API", version="1.0.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
