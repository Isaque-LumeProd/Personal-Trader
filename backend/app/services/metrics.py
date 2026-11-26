"""Métricas fundamentais e de mercado calculadas a partir dos dados do provedor."""

from datetime import date, timedelta

from ..catalog import CATALOG_BY_TICKER
from ..providers.base import AssetData
from .technical import annualized_volatility, generate_signals


def _return(closes: list[float], days: int) -> float | None:
    if len(closes) <= days:
        return None
    base = closes[-days - 1]
    return (closes[-1] / base - 1) * 100 if base else None


def dividends_12m(data: AssetData, today: date | None = None) -> float:
    today = today or date.today()
    start = today - timedelta(days=365)
    return sum(d.rate for d in data.dividends if start < d.ex_date <= today)


def asset_metrics(data: AssetData, today: date | None = None) -> dict:
    today = today or date.today()
    closes = [b.close for b in data.history]
    meta = CATALOG_BY_TICKER.get(data.ticker)
    div12 = dividends_12m(data, today)
    past_divs = [d for d in data.dividends if d.ex_date <= today]
    last_div = past_divs[-1] if past_divs else None
    recent = data.history[-21:]
    liquidity = sum(b.close * b.volume for b in recent) / len(recent) if recent else None
    signals = generate_signals(closes)
    return {
        "ticker": data.ticker,
        "name": data.name,
        "asset_type": meta.asset_type if meta else None,
        "segment": meta.segment if meta else None,
        "price": round(data.price, 2),
        "change_pct": round(data.change_pct, 2),
        "dividends_12m": round(div12, 4),
        "dy_12m": round(100 * div12 / data.price, 2) if data.price else None,
        "last_dividend": round(last_div.rate, 4) if last_div else None,
        "last_dividend_yield": round(100 * last_div.rate / data.price, 2) if last_div and data.price else None,
        "pvp": round(data.price_to_book, 2) if data.price_to_book else None,
        "avg_daily_liquidity": round(liquidity, 0) if liquidity else None,
        "return_1m": _round(_return(closes, 21)),
        "return_3m": _round(_return(closes, 63)),
        "return_12m": _round(_return(closes, 252)),
        "volatility": _round(100 * v if (v := annualized_volatility(closes)) is not None else None),
        "rsi14": _round(signals["indicators"].get("rsi14")),
        "signal_score": signals["score"],
        "recommendation": signals["recommendation"],
    }


def _round(v: float | None, n: int = 2) -> float | None:
    return round(v, n) if v is not None else None


def percentile_ranks(values: list[float | None]) -> list[float | None]:
    present = sorted(v for v in values if v is not None)
    if not present:
        return [None] * len(values)
    if len(present) == 1:
        return [0.5 if v is not None else None for v in values]
    out = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        below = sum(1 for p in present if p < v)
        equal = sum(1 for p in present if p == v)
        out.append((below + (equal - 1) / 2) / (len(present) - 1))
    return out


def score_universe(rows: list[dict]) -> None:
    """Adiciona `score` (0-100) comparando cada ativo com os pares do mesmo tipo."""
    weights = {
        "FII": [("dy_12m", 0.4, False), ("pvp", 0.3, True), ("avg_daily_liquidity", 0.15, False), ("volatility", 0.15, True)],
        "ETF": [("return_12m", 0.4, False), ("volatility", 0.3, True), ("avg_daily_liquidity", 0.3, False)],
        "ETF_RF": [("return_12m", 0.5, False), ("volatility", 0.3, True), ("avg_daily_liquidity", 0.2, False)],
    }
    for asset_type, criteria in weights.items():
        group = [r for r in rows if (r.get("asset_type") or "FII") == asset_type]
        if not group:
            continue
        ranks = {}
        for field, _, invert in criteria:
            pr = percentile_ranks([r.get(field) for r in group])
            ranks[field] = [(1 - p) if (p is not None and invert) else p for p in pr]
        for i, row in enumerate(group):
            num = den = 0.0
            for field, weight, _ in criteria:
                p = ranks[field][i]
                if p is not None:
                    num += weight * p
                    den += weight
            row["score"] = round(100 * num / den) if den else None
