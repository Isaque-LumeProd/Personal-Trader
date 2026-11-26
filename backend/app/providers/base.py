from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol


class MarketDataError(Exception):
    def __init__(self, ticker: str, message: str):
        super().__init__(f"{ticker}: {message}")
        self.ticker = ticker
        self.message = message


@dataclass
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class CashDividend:
    ex_date: date  # data com (último dia com direito)
    payment_date: date | None
    rate: float  # valor por cota
    label: str


@dataclass
class AssetData:
    ticker: str
    name: str
    price: float
    change_pct: float
    previous_close: float | None
    volume: float | None
    updated_at: datetime | None
    logo_url: str | None = None
    price_to_book: float | None = None
    history: list[Bar] = field(default_factory=list)
    dividends: list[CashDividend] = field(default_factory=list)


class MarketDataProvider(Protocol):
    name: str

    async def fetch(self, ticker: str) -> AssetData: ...
