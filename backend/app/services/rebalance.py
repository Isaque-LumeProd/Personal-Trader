"""Sugestão de aportes/rebalanceamento a partir de uma alocação-alvo."""

import math
from dataclasses import dataclass


@dataclass
class Holding:
    ticker: str
    quantity: float
    price: float

    @property
    def value(self) -> float:
        return self.quantity * self.price


def rebalance(holdings: dict[str, Holding], targets: dict[str, float], contribution: float, mode: str = "aporte") -> dict:
    """
    targets: ticker -> percentual (0-100). Ativos sem alvo têm alvo 0.
    mode "aporte": só compra, distribuindo o aporte para os ativos mais abaixo do alvo.
    mode "completo": compra e vende para chegar o mais perto possível do alvo.
    """
    tickers = sorted(set(holdings) | set(targets))
    current_total = sum(h.value for h in holdings.values())
    total_after = current_total + contribution
    target_value = {t: total_after * targets.get(t, 0.0) / 100 for t in tickers}
    buy_qty = {t: 0 for t in tickers}

    if mode == "completo":
        cash = contribution
        for t in tickers:
            h = holdings[t]
            diff = target_value[t] - h.value
            if diff < 0:
                sell = math.floor(-diff / h.price + 1e-9)
                buy_qty[t] = -min(sell, int(h.quantity))
                cash += -buy_qty[t] * h.price
        for t in tickers:
            h = holdings[t]
            diff = target_value[t] - h.value
            if diff > 0:
                qty = min(math.floor(diff / h.price + 1e-9), math.floor(cash / h.price + 1e-9))
                buy_qty[t] = qty
                cash -= qty * h.price
    else:
        deficits = {t: max(target_value[t] - holdings[t].value, 0.0) for t in tickers}
        total_deficit = sum(deficits.values())
        cash = contribution
        if total_deficit > 0:
            scale = min(1.0, contribution / total_deficit)
            for t in tickers:
                qty = math.floor(deficits[t] * scale / holdings[t].price + 1e-9)
                buy_qty[t] = qty
                cash -= qty * holdings[t].price

    # Sobras: compra 1 cota por vez do ativo mais distante do alvo que caiba no caixa.
    while True:
        candidates = [
            t
            for t in tickers
            if targets.get(t, 0) > 0
            and holdings[t].price <= cash + 1e-9
            and target_value[t] - (holdings[t].quantity + buy_qty[t]) * holdings[t].price > 0
        ]
        if not candidates:
            break
        best = max(candidates, key=lambda t: target_value[t] - (holdings[t].quantity + buy_qty[t]) * holdings[t].price)
        buy_qty[best] += 1
        cash -= holdings[best].price

    final_total = sum((holdings[t].quantity + buy_qty[t]) * holdings[t].price for t in tickers)
    rows = []
    for t in tickers:
        h = holdings[t]
        new_value = (h.quantity + buy_qty[t]) * h.price
        rows.append(
            {
                "ticker": t,
                "price": round(h.price, 2),
                "quantity": h.quantity,
                "current_value": round(h.value, 2),
                "current_pct": round(100 * h.value / current_total, 2) if current_total else 0.0,
                "target_pct": targets.get(t, 0.0),
                "target_value": round(target_value[t], 2),
                "action": "COMPRAR" if buy_qty[t] > 0 else "VENDER" if buy_qty[t] < 0 else "MANTER",
                "trade_quantity": buy_qty[t],
                "trade_value": round(buy_qty[t] * h.price, 2),
                "final_pct": round(100 * new_value / final_total, 2) if final_total else 0.0,
            }
        )
    rows.sort(key=lambda r: -abs(r["trade_value"]))
    return {
        "mode": mode,
        "contribution": contribution,
        "current_total": round(current_total, 2),
        "final_total": round(final_total, 2),
        "cash_left": round(cash, 2),
        "rows": rows,
    }
