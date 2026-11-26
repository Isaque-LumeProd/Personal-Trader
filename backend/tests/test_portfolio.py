from datetime import date

import pytest

from app.services.portfolio import PortfolioError, TxInput, build_ledger, quantity_held


def tx(side, d, qty, price, fees=0.0, ticker="HGLG11", asset_type="FII", id=0):
    return TxInput(ticker, asset_type, side, d, qty, price, fees, id)


def test_average_price_includes_fees():
    ledger = build_ledger([
        tx("BUY", date(2025, 1, 10), 10, 100, fees=5),
        tx("BUY", date(2025, 2, 10), 10, 110, fees=5),
    ])
    pos = ledger.positions["HGLG11"]
    assert pos.quantity == 20
    assert pos.avg_price == pytest.approx((1000 + 5 + 1100 + 5) / 20)


def test_sell_realizes_gain_and_keeps_average():
    ledger = build_ledger([
        tx("BUY", date(2025, 1, 10), 10, 100),
        tx("SELL", date(2025, 3, 1), 4, 120, fees=2),
    ])
    pos = ledger.positions["HGLG11"]
    assert pos.quantity == 6
    assert pos.avg_price == pytest.approx(100)
    sale = ledger.sales[0]
    assert sale.gain == pytest.approx(4 * 120 - 2 - 400)


def test_cannot_sell_more_than_held():
    with pytest.raises(PortfolioError):
        build_ledger([tx("BUY", date(2025, 1, 10), 1, 100), tx("SELL", date(2025, 1, 11), 2, 100)])


def test_same_day_buy_then_sell_is_ordered():
    ledger = build_ledger([tx("SELL", date(2025, 1, 10), 1, 110, id=1), tx("BUY", date(2025, 1, 10), 1, 100, id=2)])
    assert ledger.sales[0].gain == pytest.approx(10)


def test_quantity_held_on_date():
    txs = [tx("BUY", date(2025, 1, 10), 10, 100), tx("SELL", date(2025, 2, 10), 4, 100)]
    assert quantity_held(txs, "HGLG11", date(2025, 1, 9)) == 0
    assert quantity_held(txs, "HGLG11", date(2025, 1, 31)) == 10
    assert quantity_held(txs, "HGLG11", date(2025, 2, 10)) == 6


from app.services.portfolio import EventInput  # noqa: E402


def test_day_trade_matched_against_same_day_buys():
    ledger = build_ledger([
        tx("BUY", date(2025, 1, 2), 10, 100),
        tx("BUY", date(2025, 1, 10), 5, 120, ticker="BOVA11", asset_type="ETF", id=1),
        tx("SELL", date(2025, 1, 10), 3, 125, ticker="BOVA11", asset_type="ETF", id=2),
    ])
    sale = ledger.sales[0]
    assert sale.day_trade and sale.quantity == 3
    assert sale.gain == pytest.approx(3 * 5)
    pos = ledger.positions["BOVA11"]
    assert pos.quantity == 2 and pos.avg_price == pytest.approx(120)


def test_day_trade_with_existing_position_sells_rest_as_swing():
    ledger = build_ledger([
        tx("BUY", date(2025, 1, 2), 10, 100),
        tx("BUY", date(2025, 1, 10), 2, 110, id=1),
        tx("SELL", date(2025, 1, 10), 5, 120, id=2),
    ])
    dt, swing = sorted(ledger.sales, key=lambda s: not s.day_trade)
    assert dt.day_trade and dt.quantity == 2 and dt.gain == pytest.approx(2 * 10)
    assert not swing.day_trade and swing.quantity == 3 and swing.gain == pytest.approx(3 * 20)
    assert ledger.positions["HGLG11"].quantity == 7
    assert ledger.positions["HGLG11"].avg_price == pytest.approx(100)


def test_split_and_reverse_split_keep_total_cost():
    txs = [tx("BUY", date(2025, 1, 2), 10, 100)]
    ledger = build_ledger(txs, [EventInput("HGLG11", date(2025, 3, 1), "SPLIT", factor=10)])
    pos = ledger.positions["HGLG11"]
    assert pos.quantity == 100 and pos.avg_price == pytest.approx(10)
    ledger = build_ledger(txs, [EventInput("HGLG11", date(2025, 3, 1), "REVERSE_SPLIT", factor=5)])
    assert ledger.positions["HGLG11"].quantity == 2
    assert ledger.positions["HGLG11"].avg_price == pytest.approx(500)


def test_split_applies_before_trades_on_same_day():
    ledger = build_ledger(
        [tx("BUY", date(2025, 1, 2), 10, 100), tx("SELL", date(2025, 3, 1), 50, 11, id=1)],
        [EventInput("HGLG11", date(2025, 3, 1), "SPLIT", factor=10)],
    )
    assert ledger.positions["HGLG11"].quantity == 50
    assert ledger.sales[0].gain == pytest.approx(50 * 11 - 50 * 10)


def test_amortization_reduces_cost():
    ledger = build_ledger(
        [tx("BUY", date(2025, 1, 2), 10, 100)],
        [EventInput("HGLG11", date(2025, 2, 1), "AMORTIZATION", amount=50)],
    )
    assert ledger.positions["HGLG11"].avg_price == pytest.approx(95)
