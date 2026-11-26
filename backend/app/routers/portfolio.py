from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import CATALOG_BY_TICKER
from ..db import get_db
from ..deps import to_inputs, user_events, user_ledger, user_transactions
from ..models import Dividend, User
from ..security import current_user
from ..services.market import MarketService, get_market
from ..services.portfolio import build_ledger

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

TYPE_LABELS = {"FII": "FIIs", "ETF": "ETFs", "ETF_RF": "ETFs de Renda Fixa"}


def _month_keys(today: date, count: int = 12) -> list[str]:
    keys, y, m = [], today.year, today.month
    for _ in range(count):
        keys.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return list(reversed(keys))


@router.get("/summary")
async def summary(
    user: User = Depends(current_user), db: Session = Depends(get_db), market: MarketService = Depends(get_market)
):
    today = date.today()
    ledger = user_ledger(db, user)
    positions = ledger.open_positions()
    data, errors = await market.get_many([p.ticker for p in positions])
    dividends = list(db.scalars(select(Dividend).where(Dividend.user_id == user.id)))

    # amortizações devolvem capital (reduzem o custo) e não entram como renda
    income = [d for d in dividends if d.kind != "AMORTIZACAO"]
    received = [d for d in income if d.payment_date <= today]
    upcoming = sorted((d for d in income if d.payment_date > today), key=lambda d: d.payment_date)
    year_ago = today - timedelta(days=365)
    div_total: dict[str, float] = defaultdict(float)
    div_12m: dict[str, float] = defaultdict(float)
    for d in received:
        div_total[d.ticker] += d.amount
        if d.payment_date > year_ago:
            div_12m[d.ticker] += d.amount

    rows = []
    for p in positions:
        asset = data.get(p.ticker)
        price = asset.price if asset else p.avg_price
        value = p.quantity * price
        meta = CATALOG_BY_TICKER.get(p.ticker)
        rows.append(
            {
                "ticker": p.ticker,
                "name": asset.name if asset else (meta.name if meta else p.ticker),
                "asset_type": p.asset_type,
                "segment": meta.segment if meta else "Outros",
                "quantity": p.quantity,
                "avg_price": round(p.avg_price, 4),
                "price": round(price, 2),
                "price_available": asset is not None,
                "change_pct": round(asset.change_pct, 2) if asset else None,
                "cost": round(p.total_cost, 2),
                "market_value": round(value, 2),
                "unrealized": round(value - p.total_cost, 2),
                "unrealized_pct": round(100 * (value / p.total_cost - 1), 2) if p.total_cost else 0.0,
                "realized": round(p.realized, 2),
                "dividends_total": round(div_total[p.ticker], 2),
                "dividends_12m": round(div_12m[p.ticker], 2),
                "yield_on_cost_12m": round(100 * div_12m[p.ticker] / p.total_cost, 2) if p.total_cost else 0.0,
            }
        )

    market_value = sum(r["market_value"] for r in rows)
    for r in rows:
        r["weight"] = round(100 * r["market_value"] / market_value, 2) if market_value else 0.0
    rows.sort(key=lambda r: -r["market_value"])

    def allocation(key: str, label=lambda k: k):
        agg: dict[str, float] = defaultdict(float)
        for r in rows:
            agg[r[key]] += r["market_value"]
        return [
            {"label": label(k), "value": round(v, 2), "pct": round(100 * v / market_value, 2) if market_value else 0}
            for k, v in sorted(agg.items(), key=lambda kv: -kv[1])
        ]

    monthly: dict[str, float] = {k: 0.0 for k in _month_keys(today)}
    for d in received:
        key = d.payment_date.strftime("%Y-%m")
        if key in monthly:
            monthly[key] += d.amount

    cost = sum(r["cost"] for r in rows)
    realized_total = sum(p.realized for p in ledger.positions.values())
    dividends_all = sum(d.amount for d in received)
    return {
        "provider": market.provider_name,
        "market_errors": errors,
        "totals": {
            "market_value": round(market_value, 2),
            "cost": round(cost, 2),
            "unrealized": round(market_value - cost, 2),
            "unrealized_pct": round(100 * (market_value / cost - 1), 2) if cost else 0.0,
            "realized": round(realized_total, 2),
            "dividends_total": round(dividends_all, 2),
            "dividends_12m": round(sum(div_12m.values()), 2),
            "yield_on_cost_12m": round(100 * sum(div_12m.values()) / cost, 2) if cost else 0.0,
            "total_return": round(market_value - cost + realized_total + dividends_all, 2),
            "day_change": round(
                sum(r["market_value"] * (r["change_pct"] or 0) / (100 + (r["change_pct"] or 0)) for r in rows), 2
            ),
        },
        "positions": rows,
        "allocation_by_type": allocation("asset_type", lambda k: TYPE_LABELS.get(k, k)),
        "allocation_by_segment": allocation("segment"),
        "dividends_monthly": [{"month": k, "amount": round(v, 2)} for k, v in monthly.items()],
        "upcoming_dividends": [
            {"ticker": d.ticker, "payment_date": d.payment_date.isoformat(), "amount": d.amount} for d in upcoming
        ],
    }


@router.get("/evolution")
async def evolution(
    days: int = Query(180, ge=30, le=1825),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    market: MarketService = Depends(get_market),
):
    """Patrimônio a mercado x capital investido ao longo do tempo."""
    txs = to_inputs(user_transactions(db, user))
    events = user_events(db, user)
    if not txs:
        return {"points": []}
    data, _ = await market.get_many(list({t.ticker for t in txs}))
    start = max(date.today() - timedelta(days=days), min(t.date for t in txs))
    closes: dict[str, dict[date, float]] = {t: {b.date: b.close for b in a.history} for t, a in data.items()}
    all_dates = sorted({d for series in closes.values() for d in series if d >= start})

    points = []
    last_close: dict[str, float] = {}
    # pré-carrega o último fechamento antes do início
    for ticker, series in closes.items():
        before = [d for d in series if d < start]
        if before:
            last_close[ticker] = series[max(before)]
    for d in all_dates:
        for ticker, series in closes.items():
            if d in series:
                last_close[ticker] = series[d]
        ledger = build_ledger(txs, events, until=d)
        value = invested = 0.0
        for p in ledger.open_positions():
            invested += p.total_cost
            value += p.quantity * last_close.get(p.ticker, p.avg_price)
        points.append({"date": d.isoformat(), "market_value": round(value, 2), "invested": round(invested, 2)})
    return {"points": points}
