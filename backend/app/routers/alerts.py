from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert, User
from ..schemas import AlertIn, AlertOut
from ..security import current_user
from ..services.market import MarketService, get_market
from ..services.fmt import br
from ..services.metrics import asset_metrics

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


def evaluate(kind: str, threshold: float | None, m: dict) -> tuple[bool, float | None, str]:
    price, rsi, dy, rec = m["price"], m["rsi14"], m["dy_12m"], m["recommendation"]
    t = m["ticker"]
    if kind == "PRICE_ABOVE":
        return price >= threshold, price, f"{t} a R$ {br(price)} (alvo ≥ R$ {br(threshold)})"
    if kind == "PRICE_BELOW":
        return price <= threshold, price, f"{t} a R$ {br(price)} (alvo ≤ R$ {br(threshold)})"
    if kind == "RSI_ABOVE":
        return rsi is not None and rsi >= threshold, rsi, f"RSI de {t} em {br(rsi or 0, 0)} (alvo ≥ {br(threshold, 0)})"
    if kind == "RSI_BELOW":
        return rsi is not None and rsi <= threshold, rsi, f"RSI de {t} em {br(rsi or 0, 0)} (alvo ≤ {br(threshold, 0)})"
    if kind == "DY_ABOVE":
        return dy is not None and dy >= threshold, dy, f"DY 12m de {t} em {br(dy or 0)}% (alvo ≥ {br(threshold)}%)"
    if kind == "SIGNAL_BUY":
        return rec.startswith("COMPRA"), m["signal_score"], f"Sinal técnico de {t}: {rec}"
    if kind == "SIGNAL_SELL":
        return rec.startswith("VENDA"), m["signal_score"], f"Sinal técnico de {t}: {rec}"
    return False, None, ""


@router.post("/check")
async def check_alerts(
    user: User = Depends(current_user), db: Session = Depends(get_db), market: MarketService = Depends(get_market)
):
    alerts = list(db.scalars(select(Alert).where(Alert.user_id == user.id, Alert.active.is_(True))))
    data, errors = await market.get_many([a.ticker for a in alerts])
    now = datetime.now(timezone.utc)
    results = []
    for a in alerts:
        if a.ticker not in data:
            continue
        triggered, value, message = evaluate(a.kind, a.threshold, asset_metrics(data[a.ticker]))
        if triggered:
            a.last_triggered_at = now
        results.append({"alert_id": a.id, "ticker": a.ticker, "kind": a.kind, "triggered": triggered, "value": value, "message": message})
    db.commit()
    return {"results": results, "errors": errors}
