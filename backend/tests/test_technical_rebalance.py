import math

import pytest

from app.services import technical as ta
from app.services.rebalance import Holding, rebalance


def test_sma_and_rsi_basics():
    values = [float(i) for i in range(1, 31)]
    assert ta.sma(values, 5)[4] == pytest.approx(3)
    assert ta.rsi(values)[-1] == pytest.approx(100)
    down = list(reversed(values))
    assert ta.rsi(down)[-1] == pytest.approx(0)


def test_uptrend_generates_buy():
    closes = [100 * math.exp(0.002 * i) for i in range(260)]
    out = ta.generate_signals(closes)
    assert out["score"] > 0
    assert out["recommendation"] in {"COMPRA", "COMPRA FORTE", "NEUTRO"}


def test_rebalance_aporte_buys_underweight_only():
    holdings = {"AAAA11": Holding("AAAA11", 10, 100), "BBBB11": Holding("BBBB11", 0, 50)}
    out = rebalance(holdings, {"AAAA11": 50, "BBBB11": 50}, contribution=1000, mode="aporte")
    rows = {r["ticker"]: r for r in out["rows"]}
    assert rows["AAAA11"]["trade_quantity"] == 0
    assert rows["BBBB11"]["trade_quantity"] == 20
    assert out["cash_left"] == pytest.approx(0)


def test_rebalance_completo_sells_overweight():
    holdings = {"AAAA11": Holding("AAAA11", 20, 100), "BBBB11": Holding("BBBB11", 0, 50)}
    out = rebalance(holdings, {"AAAA11": 50, "BBBB11": 50}, contribution=0, mode="completo")
    rows = {r["ticker"]: r for r in out["rows"]}
    assert rows["AAAA11"]["trade_quantity"] == -10
    assert rows["BBBB11"]["trade_quantity"] == 20
