from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import CATALOG_BY_TICKER
from ..config import get_settings
from ..db import get_db
from ..deps import to_inputs, user_transactions
from ..models import Dividend, User
from ..security import current_user
from ..services.fmt import br
from ..services.portfolio import build_ledger
from ..services.tax import monthly_tax

router = APIRouter(prefix="/api/tax", tags=["tax"])

TYPE_DESCRIPTION = {"FII": "cotas do fundo imobiliário", "ETF": "cotas do fundo de índice (ETF)", "ETF_RF": "cotas do ETF de renda fixa"}


@router.get("/monthly")
def monthly(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ledger = build_ledger(to_inputs(user_transactions(db, user)))
    return monthly_tax(ledger.sales, get_settings())


@router.get("/annual")
def annual(
    year: int = Query(default_factory=lambda: date.today().year - 1, ge=2000, le=2100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Dados de apoio à declaração anual (IRPF): bens e direitos, proventos e vendas do ano."""
    txs = to_inputs(user_transactions(db, user))
    end_prev = build_ledger(txs, until=date(year - 1, 12, 31))
    end_year = build_ledger(txs, until=date(year, 12, 31))

    assets = []
    for ticker in sorted(set(end_prev.positions) | set(end_year.positions)):
        prev = end_prev.positions.get(ticker)
        cur = end_year.positions.get(ticker)
        prev_cost = prev.total_cost if prev else 0.0
        cur_cost = cur.total_cost if cur else 0.0
        if prev_cost == 0 and cur_cost == 0:
            continue
        meta = CATALOG_BY_TICKER.get(ticker)
        asset_type = (cur or prev).asset_type  # type: ignore[union-attr]
        qty = cur.quantity if cur else 0
        assets.append(
            {
                "ticker": ticker,
                "asset_type": asset_type,
                "quantity": qty,
                "avg_price": round(cur.avg_price, 4) if cur else 0,
                "value_previous_year": round(prev_cost, 2),
                "value_current_year": round(cur_cost, 2),
                "description": (
                    f"{br(qty, 0) if float(qty).is_integer() else br(qty, 4)} {TYPE_DESCRIPTION.get(asset_type, 'cotas')} {ticker}"
                    f"{' (' + meta.name + ')' if meta else ''}, preço médio R$ {br(cur.avg_price if cur else 0)}. "
                    "Custodiadas na B3."
                ),
            }
        )

    divs = db.scalars(select(Dividend).where(Dividend.user_id == user.id))
    income: dict[tuple[str, str], float] = defaultdict(float)
    for d in divs:
        if d.payment_date.year == year:
            income[(d.ticker, d.kind)] += d.amount

    sales_year = [s for s in end_year.sales if s.date.year == year]
    return {
        "year": year,
        "assets": assets,
        "income": [
            {"ticker": t, "kind": k, "amount": round(v, 2)} for (t, k), v in sorted(income.items())
        ],
        "sales": {
            "count": len(sales_year),
            "gross": round(sum(s.gross_value for s in sales_year), 2),
            "result": round(sum(s.gain for s in sales_year), 2),
        },
    }
