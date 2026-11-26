from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert, User
from ..schemas import AlertIn, AlertOut
from ..security import current_user
from ..services.market import MarketService, get_market
from ..services.alerts_engine import check_alerts

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

NEEDS_THRESHOLD = {"PRICE_ABOVE", "PRICE_BELOW", "RSI_ABOVE", "RSI_BELOW", "DY_ABOVE"}


def _owned(db: Session, user: User, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id)
    if not alert or alert.user_id != user.id:
        raise HTTPException(404, "Alerta não encontrado")
    return alert


def _validate(body: AlertIn) -> None:
    if body.kind in NEEDS_THRESHOLD and body.threshold is None:
        raise HTTPException(400, "Este tipo de alerta exige um valor de referência")


@router.get("", response_model=list[AlertOut])
def list_alerts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Alert).where(Alert.user_id == user.id).order_by(Alert.id.desc())))


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(body: AlertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _validate(body)
    alert = Alert(user_id=user.id, **body.model_dump())
    db.add(alert)
    db.commit()
    return alert


@router.put("/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: int, body: AlertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _validate(body)
    alert = _owned(db, user, alert_id)
    for k, v in body.model_dump().items():
        setattr(alert, k, v)
    db.commit()
    return alert


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, user, alert_id))
    db.commit()


@router.post("/check")
async def check(
    user: User = Depends(current_user), db: Session = Depends(get_db), market: MarketService = Depends(get_market)
):
    results, errors = await check_alerts(db, market, user_id=user.id)
    for r in results:
        r.pop("user_id", None)
    return {"results": results, "errors": errors}
