from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import to_inputs, user_transactions
from ..models import TargetAllocation, User
from ..schemas import RebalanceIn, TargetIn
from ..security import current_user
from ..services.market import MarketService, get_market
from ..services.portfolio import build_ledger
from ..services.rebalance import Holding, rebalance

router = APIRouter(prefix="/api/rebalance", tags=["rebalance"])


def _targets(db: Session, user: User) -> list[TargetAllocation]:
    stmt = select(TargetAllocation).where(TargetAllocation.user_id == user.id).order_by(TargetAllocation.ticker)
    return list(db.scalars(stmt))


@router.get("/targets")
def get_targets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"ticker": t.ticker, "target_pct": t.target_pct} for t in _targets(db, user)]


@router.put("/targets")
def set_targets(body: list[TargetIn], user: User = Depends(current_user), db: Session = Depends(get_db)):
    tickers = [t.ticker for t in body]
    if len(set(tickers)) != len(tickers):
        raise HTTPException(400, "Ticker repetido na alocação-alvo")
    total = sum(t.target_pct for t in body)
    if body and abs(total - 100) > 0.01:
        raise HTTPException(400, f"A soma dos percentuais deve ser 100% (atual: {total:.2f}%)")
    db.execute(delete(TargetAllocation).where(TargetAllocation.user_id == user.id))
    db.add_all(TargetAllocation(user_id=user.id, ticker=t.ticker, target_pct=t.target_pct) for t in body)
    db.commit()
    return get_targets(user, db)


@router.post("")
async def run_rebalance(
    body: RebalanceIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    market: MarketService = Depends(get_market),
):
    targets = {t.ticker: t.target_pct for t in _targets(db, user)}
    if not targets:
        raise HTTPException(400, "Defina a alocação-alvo antes de calcular o rebalanceamento")
    positions = {p.ticker: p for p in build_ledger(to_inputs(user_transactions(db, user))).open_positions()}
    data, errors = await market.get_many(list(set(targets) | set(positions)))

    holdings: dict[str, Holding] = {}
    for ticker in set(targets) | set(positions):
        pos = positions.get(ticker)
        price = data[ticker].price if ticker in data else (pos.avg_price if pos else None)
        if not price:
            raise HTTPException(502, f"Sem cotação para {ticker}: {errors.get(ticker, 'indisponível')}")
        holdings[ticker] = Holding(ticker, pos.quantity if pos else 0.0, price)

    result = rebalance(holdings, targets, body.contribution, body.mode)
    result["market_errors"] = errors
    return result
