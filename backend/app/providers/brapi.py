from datetime import date, datetime, timezone

import httpx

from .base import AssetData, Bar, CashDividend, MarketDataError


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


class BrapiProvider:
    """Cliente da API brapi.dev (cotações B3, histórico e proventos)."""

    name = "brapi"

    def __init__(self, token: str | None, base_url: str, history_range: str = "1y", timeout: float = 15.0):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.history_range = history_range
        self.timeout = timeout

    async def _request(self, client: httpx.AsyncClient, ticker: str, history_range: str) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        params = {"range": history_range, "interval": "1d", "dividends": "true"}
        return await client.get(f"{self.base_url}/quote/{ticker}", params=params, headers=headers)

    async def fetch(self, ticker: str) -> AssetData:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await self._request(client, ticker, self.history_range)
                # Planos mais simples limitam o período de histórico: tenta um período menor.
                if resp.status_code in (400, 402, 403) and self.history_range != "3mo":
                    resp = await self._request(client, ticker, "3mo")
            except httpx.HTTPError as exc:
                raise MarketDataError(ticker, f"falha de rede: {exc}") from exc

        if resp.status_code == 404:
            raise MarketDataError(ticker, "ativo não encontrado")
        if resp.status_code == 401:
            raise MarketDataError(ticker, "token da brapi ausente ou inválido (BRAPI_TOKEN)")
        if resp.status_code >= 400:
            raise MarketDataError(ticker, f"erro da brapi ({resp.status_code}): {resp.text[:200]}")

        results = resp.json().get("results") or []
        if not results:
            raise MarketDataError(ticker, "sem dados")
        return self.parse(results[0])

    @staticmethod
    def parse(d: dict) -> AssetData:
        history = [
            Bar(
                date=datetime.fromtimestamp(b["date"], tz=timezone.utc).date(),
                open=float(b.get("open") or b["close"]),
                high=float(b.get("high") or b["close"]),
                low=float(b.get("low") or b["close"]),
                close=float(b["close"]),
                volume=float(b.get("volume") or 0),
            )
            for b in d.get("historicalDataPrice") or []
            if b.get("close") is not None
        ]
        history.sort(key=lambda b: b.date)

        dividends = []
        for c in (d.get("dividendsData") or {}).get("cashDividends") or []:
            ex = _parse_date(c.get("lastDatePrior"))
            if ex is None or not c.get("rate"):
                continue
            dividends.append(
                CashDividend(
                    ex_date=ex,
                    payment_date=_parse_date(c.get("paymentDate")),
                    rate=float(c["rate"]),
                    label=(c.get("label") or "RENDIMENTO").upper(),
                )
            )
        dividends.sort(key=lambda c: c.ex_date)

        updated = d.get("regularMarketTime")
        return AssetData(
            ticker=d["symbol"],
            name=d.get("longName") or d.get("shortName") or d["symbol"],
            price=float(d.get("regularMarketPrice") or (history[-1].close if history else 0)),
            change_pct=float(d.get("regularMarketChangePercent") or 0),
            previous_close=d.get("regularMarketPreviousClose"),
            volume=d.get("regularMarketVolume"),
            updated_at=datetime.fromisoformat(updated.replace("Z", "+00:00")) if isinstance(updated, str) else None,
            logo_url=d.get("logourl"),
            price_to_book=d.get("priceToBook"),
            history=history,
            dividends=dividends,
        )
