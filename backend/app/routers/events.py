from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import user_ledger
from ..models import CorporateEvent, User
from ..schemas import TICKER_PATTERN
from ..security import current_user
from ..services.portfolio import PortfolioError

router = APIRouter(prefix="/api/events", tags=["events"])


class EventIn(BaseModel):
    ticker: str = Field(pattern=TICKER_PATTERN)
    kind: Literal["SPLIT", "REVERSE_SPLIT"]
    date: date
    factor: float = Field(gt=1, le=1000, description="Proporção: 10 = desdobramento 1:10 ou grupamento 10:1")
    notes: str | None = Field(default=None, max_length=255)

    @field_validator("ticker", mode="before")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    kind: str
    date: date
    factor: float
    notes: str | None


def _validate(db: Session, user: User) -> None:
    db.flush()
    try:
        user_ledger(db, user)
    except PortfolioError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    db.commit()


@router.get("", response_model=list[EventOut])
def list_events(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(CorporateEvent).where(CorporateEvent.user_id == user.id).order_by(CorporateEvent.date.desc())
    return list(db.scalars(stmt))


@router.post("", response_model=EventOut, status_code=201)
def create_event(body: EventIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ev = CorporateEvent(user_id=user.id, **body.model_dump())
    db.add(ev)
    _validate(db, user)
    return ev


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ev = db.get(CorporateEvent, event_id)
    if not ev or ev.user_id != user.id:
        raise HTTPException(404, "Evento não encontrado")
    db.delete(ev)
    _validate(db, user)
