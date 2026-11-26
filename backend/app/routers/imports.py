from collections import Counter
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import user_ledger, user_transactions
from ..models import Dividend, Transaction, User
from ..schemas import AssetType, TICKER_PATTERN
from ..security import current_user
from ..services.importer import ImportError_, parse_file
from ..services.portfolio import PortfolioError

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _trade_key(ticker: str, side: str, d: date, qty: float, price: float) -> tuple:
    return (ticker, side, d, round(qty, 6), round(price, 2))


def _div_key(ticker: str, d: date, kind: str, amount: float) -> tuple:
    return (ticker, d, kind, round(amount, 2))


@router.post("/preview")
async def preview(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Arquivo maior que 5 MB")
    try:
        fmt, rows = parse_file(file.filename or "", content)
    except ImportError_ as exc:
        raise HTTPException(400, str(exc)) from exc

    # Duplicatas contra o que já existe (contagem, pois a B3 pode repetir linhas idênticas legítimas)
    existing_trades = Counter(
        _trade_key(t.ticker, t.side, t.date, t.quantity, t.price) for t in user_transactions(db, user)
    )
    existing_divs = Counter(
        _div_key(d.ticker, d.payment_date, d.kind, d.amount)
        for d in db.scalars(select(Dividend).where(Dividend.user_id == user.id))
    )
    for row in rows:
        if row.status != "ok":
            continue
        if row.kind == "trade":
            key = _trade_key(row.ticker, row.side or "", row.date, row.quantity, row.price)  # type: ignore[arg-type]
            pool = existing_trades
        else:
            key = _div_key(row.ticker, row.date, row.dividend_kind or "", row.amount)  # type: ignore[arg-type]
            pool = existing_divs
        if pool[key] > 0:
            pool[key] -= 1
            row.status, row.reason = "duplicate", "já cadastrado"

    counts = Counter(r.status for r in rows)
    return {"format": fmt, "rows": [r.to_dict() for r in rows], "summary": dict(counts)}


class TradeIn(BaseModel):
    ticker: str = Field(pattern=TICKER_PATTERN)
    asset_type: AssetType
    side: Literal["BUY", "SELL"]
    date: date
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(default=0, ge=0)


class DividendRowIn(BaseModel):
    ticker: str = Field(pattern=TICKER_PATTERN)
    dividend_kind: Literal["RENDIMENTO", "DIVIDENDO", "JCP", "AMORTIZACAO"]
    date: date
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    amount: float = Field(gt=0)


class CommitIn(BaseModel):
    trades: list[TradeIn] = Field(default_factory=list, max_length=5000)
    dividends: list[DividendRowIn] = Field(default_factory=list, max_length=5000)


@router.post("/commit")
def commit(body: CommitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for t in body.trades:
        db.add(Transaction(user_id=user.id, notes="Importado", **t.model_dump()))
    for d in body.dividends:
        db.add(
            Dividend(
                user_id=user.id,
                ticker=d.ticker,
                kind=d.dividend_kind,
                ex_date=None,
                payment_date=d.date,
                quantity=d.quantity,
                per_share=d.price or d.amount / d.quantity,
                amount=round(d.amount, 2),
                source="import",
            )
        )
    db.flush()
    try:
        user_ledger(db, user)
    except PortfolioError as exc:
        db.rollback()
        raise HTTPException(
            400, f"{exc} Importe também o histórico anterior ou cadastre a posição inicial antes."
        ) from exc
    db.commit()
    return {"trades": len(body.trades), "dividends": len(body.dividends)}
