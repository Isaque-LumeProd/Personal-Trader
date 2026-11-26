from datetime import date

import pytest

from app.config import Settings
from app.services.portfolio import Sale
from app.services.tax import last_business_day_of_next_month, monthly_tax

S = Settings(irrf_rate=0.0)


def sale(d, gain, asset_type="FII", gross=1000.0):
    return Sale(d, "XPTO11", asset_type, 10, gross, gross, gross - gain, gain)


def test_fii_gain_taxed_at_20_percent():
    out = monthly_tax([sale(date(2025, 3, 5), 1000)], S)
    m = out["months"][0]
    assert m["tax"] == pytest.approx(200)
    assert m["darf_value"] == pytest.approx(200)
    assert m["darf_due_date"] == "2025-04-30"


def test_losses_only_offset_same_category():
    out = monthly_tax([
        sale(date(2025, 1, 5), -500, "FII"),
        sale(date(2025, 2, 5), 1000, "ETF"),
        sale(date(2025, 3, 5), 800, "FII"),
    ], S)
    by_month = {m["month"]: m for m in out["months"]}
    assert by_month["2025-02"]["tax"] == pytest.approx(150)  # ETF não usa prejuízo de FII
    assert by_month["2025-03"]["tax"] == pytest.approx(60)  # (800 - 500) * 20%
    assert out["accumulated_losses"] == {"FII": 0.0, "ETF": 0.0}


def test_darf_below_minimum_is_carried():
    out = monthly_tax([sale(date(2025, 1, 5), 30), sale(date(2025, 2, 5), 30)], S)
    by_month = {m["month"]: m for m in out["months"]}
    assert by_month["2025-01"]["darf_value"] == 0
    assert by_month["2025-01"]["pending_below_minimum"] == pytest.approx(6)
    assert by_month["2025-02"]["darf_value"] == pytest.approx(12)


def test_irrf_is_deducted():
    out = monthly_tax([sale(date(2025, 1, 5), 1000, gross=100_000)], Settings())
    assert out["months"][0]["categories"][0]["irrf"] == pytest.approx(5)
    assert out["months"][0]["tax"] == pytest.approx(195)


def test_fixed_income_etf_excluded_from_darf():
    out = monthly_tax([sale(date(2025, 1, 5), 1000, "ETF_RF")], S)
    assert out["months"][0]["tax"] == 0
    assert len(out["months"][0]["withheld_at_source"]) == 1


def test_due_date_skips_weekend():
    assert last_business_day_of_next_month(2025, 4) == date(2025, 5, 30)  # 31/05/2025 é sábado
    assert last_business_day_of_next_month(2025, 12) == date(2026, 1, 30)
