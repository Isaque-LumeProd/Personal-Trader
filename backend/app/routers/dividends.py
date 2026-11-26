from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import to_inputs, user_transactions
from ..models import Dividend, User
from ..schemas import DividendIn, DividendOut
from ..security import current_user
from ..services.market import MarketService, get_market
from ..services.portfolio import quantity_held

router = APIRouter(prefix="/api/dividends", tags=["dividends"])


def normalize_kind(label: str) -> str:
    label = label.upper()
    if "JCP" in label or "JUROS" in label:
        return "JCP"
    if "AMORT" in label:
        return "AMORTIZACAO"
    if "DIVID" in label:
        return "DIVIDENDO"
    return "RENDIMENTO"


@router.get("", response_model=list[DividendOut])
def list_dividends(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Dividend).where(Dividend.user_id == user.id).order_by(Dividend.payment_date.desc(), Dividend.id.desc())
    return list(db.scalars(stmt))


@router.post("", response_model=DividendOut, status_code=201)
def create_dividend(body: DividendIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    div = Dividend(user_id=user.id, amount=round(body.quantity * body.per_share, 2), source="manual", **body.model_dump())
    db.add(div)
    db.commit()
    return div


@router.delete("/{div_id}", status_code=204)
def delete_dividend(div_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    div = db.get(Dividend, div_id)
    if not div or div.user_id != user.id:
        raise HTTPException(404, "Provento não encontrado")
    db.delete(div)
    db.commit()


@router.post("/sync")
async def sync_dividends(
    user: User = Depends(current_user), db: Session = Depends(get_db), market: MarketService = Depends(get_market)
):
    """Importa proventos do provedor com base na posição em cada data com."""
    txs = to_inputs(user_transactions(db, user))
    first_trade: dict[str, date] = {}
    for tx in txs:
        first_trade.setdefault(tx.ticker, tx.date)
    data, errors = await market.get_many(list(first_trade))

    existing = {
        (d.ticker, d.ex_date, d.kind, round(d.per_share, 6))
        for d in db.scalars(select(Dividend).where(Dividend.user_id == user.id))
    }
    created = 0
    for ticker, asset in data.items():
        for c in asset.dividends:
            if c.ex_date < first_trade[ticker]:
                continue
            qty = quantity_held(txs, ticker, c.ex_date)
            if qty <= 0:
                continue
            kind = normalize_kind(c.label)
            key = (ticker, c.ex_date, kind, round(c.rate, 6))
            if key in existing:
                continue
            existing.add(key)
            db.add(
                Dividend(
                    user_id=user.id,
                    ticker=ticker,
                    kind=kind,
                    ex_date=c.ex_date,
                    payment_date=c.payment_date or c.ex_date,
                    quantity=qty,
                    per_share=c.rate,
                    amount=round(qty * c.rate, 2),
                    source="auto",
                )
            )
            created += 1
    db.commit()
    return {"created": created, "errors": errors}
