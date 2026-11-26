from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..catalog import CATALOG, CATALOG_BY_TICKER
from ..db import get_db
from ..deps import user_ledger
from ..models import User
from ..providers.base import MarketDataError
from ..security import current_user
from ..services import technical as ta
from ..services.fmt import br
from ..services.market import MarketService, get_market
from ..services.metrics import asset_metrics, score_universe

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market/status")
def status(market: MarketService = Depends(get_market)):
    return {"provider": market.provider_name, "catalog_size": len(CATALOG)}


@router.get("/market/assets")
def assets():
    return [
        {"ticker": a.ticker, "name": a.name, "asset_type": a.asset_type, "segment": a.segment} for a in CATALOG
    ]


async def _fetch(market: MarketService, ticker: str):
    try:
        return await market.get(ticker.upper())
    except MarketDataError as exc:
        raise HTTPException(404 if "não encontrado" in exc.message else 502, exc.message) from exc


def _r(v, n=4):
    return round(v, n) if v is not None else None


@router.get("/market/analysis/{ticker}")
async def analysis(
    ticker: str,
    days: int = Query(180, ge=30, le=1000),
    _: User = Depends(current_user),
    market: MarketService = Depends(get_market),
):
    data = await _fetch(market, ticker)
    closes = [b.close for b in data.history]
    s20, s50, s200 = ta.sma(closes, 20), ta.sma(closes, 50), ta.sma(closes, 200)
    _, bb_up, bb_low = ta.bollinger(closes)
    rsi = ta.rsi(closes)
    macd_line, macd_sig, macd_hist = ta.macd(closes)

    start = max(0, len(closes) - days)
    series = [
        {
            "date": b.date.isoformat(),
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "sma20": _r(s20[i]),
            "sma50": _r(s50[i]),
            "sma200": _r(s200[i]),
            "bb_upper": _r(bb_up[i]),
            "bb_lower": _r(bb_low[i]),
            "rsi": _r(rsi[i], 2),
            "macd": _r(macd_line[i]),
            "macd_signal": _r(macd_sig[i]),
            "macd_hist": _r(macd_hist[i]),
        }
        for i, b in enumerate(data.history)
        if i >= start
    ]

    metrics = asset_metrics(data)
    technical = ta.generate_signals(closes)
    fundamentals = []
    meta = CATALOG_BY_TICKER.get(data.ticker)
    if (meta is None or meta.asset_type == "FII") and metrics["dy_12m"]:
        dy = metrics["dy_12m"]
        if dy >= 10:
            fundamentals.append({"name": "Dividend Yield", "direction": "BUY", "description": f"DY de 12 meses de {br(dy)}% (acima de 10%)."})
        elif dy < 7:
            fundamentals.append({"name": "Dividend Yield", "direction": "SELL", "description": f"DY de 12 meses de {br(dy)}% (abaixo de 7%)."})
        else:
            fundamentals.append({"name": "Dividend Yield", "direction": "NEUTRAL", "description": f"DY de 12 meses de {br(dy)}%."})
    if metrics["pvp"]:
        pvp = metrics["pvp"]
        if pvp < 0.9:
            fundamentals.append({"name": "P/VP", "direction": "BUY", "description": f"P/VP de {br(pvp)}: negociado com desconto sobre o patrimônio."})
        elif pvp > 1.1:
            fundamentals.append({"name": "P/VP", "direction": "SELL", "description": f"P/VP de {br(pvp)}: negociado com ágio sobre o patrimônio."})
        else:
            fundamentals.append({"name": "P/VP", "direction": "NEUTRAL", "description": f"P/VP de {br(pvp)}: próximo do valor patrimonial."})

    return {
        "provider": market.provider_name,
        "metrics": metrics,
        "technical": technical,
        "fundamentals": fundamentals,
        "series": series,
        "dividends": [
            {
                "ex_date": d.ex_date.isoformat(),
                "payment_date": d.payment_date.isoformat() if d.payment_date else None,
                "rate": d.rate,
                "label": d.label,
            }
            for d in reversed(data.dividends[-12:])
        ],
    }


@router.get("/screener")
async def screener(
    asset_type: str | None = Query(None, pattern="^(FII|ETF|ETF_RF)$"),
    segment: str | None = None,
    min_dy: float | None = None,
    max_pvp: float | None = None,
    min_liquidity: float | None = None,
    recommendation: str | None = None,
    sort: str = "score",
    order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    market: MarketService = Depends(get_market),
):
    held = {p.ticker for p in user_ledger(db, user).open_positions()}
    data, errors = await market.get_many([a.ticker for a in CATALOG] + list(held))
    rows = [asset_metrics(a) for a in data.values()]
    for r in rows:
        r["in_portfolio"] = r["ticker"] in held
        r["asset_type"] = r["asset_type"] or "FII"
        r["segment"] = r["segment"] or "Outros"
    score_universe(rows)

    def keep(r: dict) -> bool:
        if asset_type and r["asset_type"] != asset_type:
            return False
        if segment and r["segment"] != segment:
            return False
        if min_dy is not None and (r["dy_12m"] or 0) < min_dy:
            return False
        if max_pvp is not None and (r["pvp"] is None or r["pvp"] > max_pvp):
            return False
        if min_liquidity is not None and (r["avg_daily_liquidity"] or 0) < min_liquidity:
            return False
        if recommendation and not r["recommendation"].startswith(recommendation.upper()):
            return False
        return True

    result = [r for r in rows if keep(r)]
    reverse = order == "desc"
    present = [r for r in result if r.get(sort) is not None]
    missing = [r for r in result if r.get(sort) is None]
    present.sort(key=lambda r: r[sort], reverse=reverse)
    return {
        "provider": market.provider_name,
        "errors": errors,
        "segments": sorted({r["segment"] for r in rows}),
        "results": present + missing,
    }
