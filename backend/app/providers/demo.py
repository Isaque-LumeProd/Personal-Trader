"""Provedor de demonstração: séries determinísticas e realistas, sem rede.

Útil para desenvolvimento, testes e para experimentar o app sem token da brapi.
"""

import math
import random
import zlib
from datetime import date, datetime, timedelta, timezone

from ..catalog import CATALOG_BY_TICKER, CatalogAsset
from .base import AssetData, Bar, CashDividend

HISTORY_DAYS = 420


def _business_days(end: date, count: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def _last_business_day(year: int, month: int) -> date:
    d = (date(year + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


class DemoProvider:
    name = "demo"

    def __init__(self, today: date | None = None):
        self.today = today

    async def fetch(self, ticker: str) -> AssetData:
        return self.generate(ticker)

    def generate(self, ticker: str) -> AssetData:
        today = self.today or date.today()
        meta = CATALOG_BY_TICKER.get(ticker) or CatalogAsset(
            ticker, ticker, "FII", "Outros", 50.0 + zlib.crc32(ticker.encode()) % 100, 0.008, 0.95
        )
        rng = random.Random(zlib.crc32(ticker.encode()))
        days = _business_days(today, HISTORY_DAYS)

        dt = 1 / 252
        mu, sigma = meta.demo_drift, meta.demo_vol
        cycle_len = rng.randint(60, 140)
        phase = rng.random() * 2 * math.pi
        # Caminho de log-preço; depois é escalado para terminar perto do preço de referência.
        log_p, path = 0.0, []
        for i in range(len(days)):
            cycle = 0.0006 * math.sin(2 * math.pi * i / cycle_len + phase)
            log_p += (mu - 0.5 * sigma**2) * dt + cycle + sigma * math.sqrt(dt) * rng.gauss(0, 1)
            path.append(log_p)
        offset = math.log(meta.demo_price) - path[-1]
        closes = [math.exp(p + offset) for p in path]

        history = []
        base_volume = 2_000_000 / max(meta.demo_price, 1)
        for i, (d, close) in enumerate(zip(days, closes)):
            prev = closes[i - 1] if i else close
            spread = abs(rng.gauss(0, sigma * math.sqrt(dt))) * close
            history.append(
                Bar(
                    date=d,
                    open=round(prev, 2),
                    high=round(max(prev, close) + spread, 2),
                    low=round(min(prev, close) - spread, 2),
                    close=round(close, 2),
                    volume=round(base_volume * rng.uniform(0.5, 1.8)),
                )
            )

        dividends: list[CashDividend] = []
        if meta.demo_monthly_yield > 0 and meta.demo_dividend_every > 0:
            close_by_date = {b.date: b.close for b in history}
            y, m = days[0].year, days[0].month
            while (y, m) <= (today.year, today.month):
                if m % meta.demo_dividend_every == 0:
                    ex = _last_business_day(y, m)
                    if ex >= days[0]:
                        ref_price = close_by_date.get(ex) or history[-1].close
                        rate = ref_price * meta.demo_monthly_yield * meta.demo_dividend_every
                        rate *= rng.uniform(0.92, 1.08)
                        pay = ex + timedelta(days=14)
                        label = "RENDIMENTO" if meta.asset_type == "FII" else "DIVIDENDO"
                        dividends.append(CashDividend(ex, pay, round(rate, 4), label))
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)

        last, prev = history[-1], history[-2]
        pvp = meta.demo_pvp
        if pvp is not None:
            # P/VP acompanha o preço em relação à média do último ano
            avg = sum(b.close for b in history[-252:]) / min(252, len(history))
            pvp = round(pvp * last.close / avg, 2)
        return AssetData(
            ticker=ticker,
            name=meta.name,
            price=last.close,
            change_pct=round((last.close / prev.close - 1) * 100, 2),
            previous_close=prev.close,
            volume=last.volume,
            updated_at=datetime.combine(last.date, datetime.min.time(), tzinfo=timezone.utc),
            price_to_book=pvp,
            history=history,
            dividends=dividends,
        )
