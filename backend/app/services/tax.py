"""Apuração mensal de IR sobre ganho de capital em FIIs e ETFs (pessoa física).

Categorias e regras:
- FII: 20% (operações comuns e day trade); prejuízos de FII só compensam lucros de FII.
- ETF (operações comuns): 15%; sem isenção de R$ 20 mil.
- ETF_DT (day trade em ETFs): 20%; prejuízos de day trade só compensam lucros de day trade.
- ETF de renda fixa: IR retido na fonte pelo administrador -> fora do DARF.
- IRRF: 0,005% sobre o valor das vendas comuns e 1% sobre o resultado positivo de day trade,
  ambos dedutíveis do imposto devido no mês.
- DARF (código 6015) abaixo de R$ 10,00 é acumulado para os meses seguintes.
- Vencimento: último dia útil do mês seguinte (feriados não considerados).
"""

from collections import defaultdict
from datetime import date, timedelta

from ..config import Settings
from .portfolio import Sale

CATEGORIES = ("FII", "ETF", "ETF_DT")


def category_of(sale: Sale) -> str | None:
    if sale.asset_type == "FII":
        return "FII"
    if sale.asset_type == "ETF":
        return "ETF_DT" if sale.day_trade else "ETF"
    return None  # ETF_RF: retido na fonte


def last_business_day_of_next_month(year: int, month: int) -> date:
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    first_after = date(ny + (nm == 12), nm % 12 + 1, 1)
    d = first_after - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _irrf(sales: list[Sale], settings: Settings) -> float:
    swing = sum(s.gross_value for s in sales if not s.day_trade) * settings.irrf_rate
    dt = sum(max(s.gain, 0.0) for s in sales if s.day_trade) * settings.irrf_daytrade_rate
    return swing + dt


def monthly_tax(sales: list[Sale], settings: Settings) -> dict:
    rates = {"FII": settings.tax_rate_fii, "ETF": settings.tax_rate_etf, "ETF_DT": settings.tax_rate_daytrade}
    by_month: dict[tuple[int, int], list[Sale]] = defaultdict(list)
    for s in sales:
        by_month[(s.date.year, s.date.month)].append(s)

    carried_loss = {c: 0.0 for c in CATEGORIES}
    pending_darf = 0.0
    months = []
    for (year, month) in sorted(by_month):
        month_sales = by_month[(year, month)]
        categories = []
        month_tax = 0.0
        for cat in CATEGORIES:
            cat_sales = [s for s in month_sales if category_of(s) == cat]
            if not cat_sales:
                continue
            gross = sum(s.gross_value for s in cat_sales)
            gain = sum(s.gain for s in cat_sales)
            loss_before = carried_loss[cat]
            if gain >= 0:
                compensated = min(gain, loss_before)
                taxable = gain - compensated
                carried_loss[cat] = loss_before - compensated
            else:
                compensated, taxable = 0.0, 0.0
                carried_loss[cat] = loss_before - gain
            tax_due = taxable * rates[cat]
            irrf = _irrf(cat_sales, settings)
            tax_net = max(tax_due - irrf, 0.0)
            month_tax += tax_net
            categories.append(
                {
                    "category": cat,
                    "rate": rates[cat],
                    "gross_sales": round(gross, 2),
                    "day_trade_result": round(sum(s.gain for s in cat_sales if s.day_trade), 2),
                    "result": round(gain, 2),
                    "loss_compensated": round(compensated, 2),
                    "taxable": round(taxable, 2),
                    "tax_due": round(tax_due, 2),
                    "irrf": round(irrf, 2),
                    "tax_net": round(tax_net, 2),
                    "loss_carried": round(carried_loss[cat], 2),
                }
            )

        withheld = [s for s in month_sales if category_of(s) is None]
        total = month_tax + pending_darf
        if total >= settings.darf_minimum:
            darf, pending_darf = total, 0.0
        else:
            darf, pending_darf = 0.0, total
        months.append(
            {
                "month": f"{year:04d}-{month:02d}",
                "categories": categories,
                "withheld_at_source": [
                    {"ticker": s.ticker, "date": s.date.isoformat(), "result": round(s.gain, 2)} for s in withheld
                ],
                "tax": round(month_tax, 2),
                "darf_value": round(darf, 2),
                "darf_due_date": last_business_day_of_next_month(year, month).isoformat() if darf else None,
                "darf_code": "6015",
                "pending_below_minimum": round(pending_darf, 2),
            }
        )

    return {
        "months": list(reversed(months)),
        "accumulated_losses": {c: round(v, 2) for c, v in carried_loss.items()},
        "pending_below_minimum": round(pending_darf, 2),
        "total_darf": round(sum(m["darf_value"] for m in months), 2),
    }
