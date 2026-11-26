from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

TICKER_PATTERN = r"^[A-Z]{4}[0-9]{1,2}$"

AssetType = Literal["FII", "ETF", "ETF_RF"]


def _upper(v: str) -> str:
    return v.strip().upper()


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TransactionIn(BaseModel):
    ticker: str = Field(pattern=TICKER_PATTERN)
    asset_type: AssetType | None = None
    side: Literal["BUY", "SELL"]
    date: date
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=255)

    _norm = field_validator("ticker", mode="before")(_upper)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    asset_type: str
    side: str
    date: date
    quantity: float
    price: float
    fees: float
    notes: str | None
    total: float = 0


class DividendIn(BaseModel):
    ticker: str = Field(pattern=TICKER_PATTERN)
    kind: Literal["RENDIMENTO", "DIVIDENDO", "JCP", "AMORTIZACAO"] = "RENDIMENTO"
    ex_date: date | None = None
    payment_date: date
    quantity: float = Field(gt=0)
    per_share: float = Field(gt=0)

    _norm = field_validator("ticker", mode="before")(_upper)


class DividendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    kind: str
    ex_date: date | None
    payment_date: date
    quantity: float
    per_share: float
    amount: float
    source: str


class TargetIn(BaseModel):
    ticker: str = Field(pattern=TICKER_PATTERN)
    target_pct: float = Field(gt=0, le=100)

    _norm = field_validator("ticker", mode="before")(_upper)


class RebalanceIn(BaseModel):
    contribution: float = Field(ge=0)
    mode: Literal["aporte", "completo"] = "aporte"


AlertKind = Literal["PRICE_ABOVE", "PRICE_BELOW", "RSI_ABOVE", "RSI_BELOW", "DY_ABOVE", "SIGNAL_BUY", "SIGNAL_SELL"]


class AlertIn(BaseModel):
    ticker: str = Field(pattern=TICKER_PATTERN)
    kind: AlertKind
    threshold: float | None = None
    active: bool = True

    _norm = field_validator("ticker", mode="before")(_upper)


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    kind: str
    threshold: float | None
    active: bool
    last_triggered_at: datetime | None
