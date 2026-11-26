"""Cálculo de posições pelo preço médio (regra da Receita Federal)."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

EPS = 1e-9


class PortfolioError(ValueError):
    pass


@dataclass
class TxInput:
    ticker: str
    asset_type: str
    side: str
    date: date
    quantity: float
    price: float
    fees: float = 0.0
    id: int = 0


@dataclass
class Sale:
    date: date
    ticker: str
    asset_type: str
    quantity: float
    gross_value: float  # quantidade x preço
    net_value: float  # descontadas as taxas
    cost: float  # preço médio x quantidade
    gain: float


@dataclass
class Position:
    ticker: str
    asset_type: str
    quantity: float = 0.0
    total_cost: float = 0.0
    realized: float = 0.0
    first_buy: date | None = None

    @property
    def avg_price(self) -> float:
        return self.total_cost / self.quantity if self.quantity > EPS else 0.0


@dataclass
class Ledger:
    positions: dict[str, Position] = field(default_factory=dict)
    sales: list[Sale] = field(default_factory=list)

    def open_positions(self) -> list[Position]:
        return [p for p in self.positions.values() if p.quantity > EPS]


def sort_key(tx: TxInput):
    # Na mesma data, compras antes das vendas (evita "vender a descoberto" em lançamentos do mesmo dia).
    return (tx.date, 0 if tx.side == "BUY" else 1, tx.id)


def build_ledger(transactions: list[TxInput], until: date | None = None) -> Ledger:
    ledger = Ledger()
    for tx in sorted(transactions, key=sort_key):
        if until and tx.date > until:
            break
        pos = ledger.positions.setdefault(tx.ticker, Position(tx.ticker, tx.asset_type))
        pos.asset_type = tx.asset_type
        if tx.side == "BUY":
            pos.total_cost += tx.quantity * tx.price + tx.fees
            pos.quantity += tx.quantity
            pos.first_buy = pos.first_buy or tx.date
        elif tx.side == "SELL":
            if tx.quantity > pos.quantity + EPS:
                raise PortfolioError(
                    f"Venda de {tx.quantity:g} {tx.ticker} em {tx.date:%d/%m/%Y} maior que a posição "
                    f"disponível ({pos.quantity:g})."
                )
            cost = pos.avg_price * tx.quantity
            gross = tx.quantity * tx.price
            net = gross - tx.fees
            gain = net - cost
            ledger.sales.append(Sale(tx.date, tx.ticker, pos.asset_type, tx.quantity, gross, net, cost, gain))
            pos.realized += gain
            pos.quantity -= tx.quantity
            pos.total_cost -= cost
            if pos.quantity <= EPS:
                pos.quantity, pos.total_cost = 0.0, 0.0
        else:
            raise PortfolioError(f"Tipo de operação inválido: {tx.side}")
    return ledger


def quantity_held(transactions: list[TxInput], ticker: str, on: date) -> float:
    qty = 0.0
    for tx in transactions:
        if tx.ticker == ticker and tx.date <= on:
            qty += tx.quantity if tx.side == "BUY" else -tx.quantity
    return max(qty, 0.0)


def quantity_timeline(transactions: list[TxInput]) -> dict[str, list[tuple[date, float]]]:
    """Quantidade acumulada por ticker após cada data de operação."""
    timeline: dict[str, list[tuple[date, float]]] = defaultdict(list)
    running: dict[str, float] = defaultdict(float)
    for tx in sorted(transactions, key=sort_key):
        running[tx.ticker] += tx.quantity if tx.side == "BUY" else -tx.quantity
        points = timeline[tx.ticker]
        if points and points[-1][0] == tx.date:
            points[-1] = (tx.date, running[tx.ticker])
        else:
            points.append((tx.date, running[tx.ticker]))
    return timeline
