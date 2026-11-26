"""Cálculo de posições pelo preço médio (regra da Receita Federal).

Processa o histórico dia a dia:
1. Desdobramentos e grupamentos com data no dia (antes das negociações).
2. Negociações do dia, por ativo. Compras e vendas do mesmo ativo no mesmo dia formam
   day trade na quantidade casada (com o preço médio das compras do dia); o restante
   é operação comum (swing trade) contra o preço médio da posição.
3. Amortizações com data no dia (depois das negociações), que reduzem o custo.
"""

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
class EventInput:
    """SPLIT/REVERSE_SPLIT: `factor` (ex.: 10 = 1 cota vira 10 / 10 cotas viram 1).
    AMORTIZATION: `amount` total devolvido, abatido do custo."""

    ticker: str
    date: date
    kind: str
    factor: float | None = None
    amount: float | None = None


@dataclass
class Sale:
    date: date
    ticker: str
    asset_type: str
    quantity: float
    gross_value: float  # quantidade x preço
    net_value: float  # descontadas as taxas
    cost: float  # custo médio x quantidade
    gain: float
    day_trade: bool = False


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

    def quantity(self, ticker: str) -> float:
        pos = self.positions.get(ticker)
        return pos.quantity if pos else 0.0


def _apply_trades(ledger: Ledger, ticker: str, txs: list[TxInput]) -> None:
    buys = [t for t in txs if t.side == "BUY"]
    sells = [t for t in txs if t.side == "SELL"]
    for t in txs:
        if t.side not in ("BUY", "SELL"):
            raise PortfolioError(f"Tipo de operação inválido: {t.side}")
    asset_type = txs[-1].asset_type
    day = txs[0].date
    pos = ledger.positions.setdefault(ticker, Position(ticker, asset_type))
    pos.asset_type = asset_type

    bq = sum(t.quantity for t in buys)
    bcost = sum(t.quantity * t.price + t.fees for t in buys)
    sq = sum(t.quantity for t in sells)
    sgross = sum(t.quantity * t.price for t in sells)
    snet = sgross - sum(t.fees for t in sells)
    buy_avg = bcost / bq if bq > EPS else 0.0

    dt = min(bq, sq)
    if dt > EPS:
        gross, net, cost = dt * sgross / sq, dt * snet / sq, dt * buy_avg
        ledger.sales.append(Sale(day, ticker, asset_type, dt, gross, net, cost, net - cost, day_trade=True))
        pos.realized += net - cost

    rest_buy, rest_sell = bq - dt, sq - dt
    if rest_buy > EPS:
        pos.total_cost += rest_buy * buy_avg
        pos.quantity += rest_buy
    if bq > EPS:
        pos.first_buy = pos.first_buy or day
    if rest_sell > EPS:
        if rest_sell > pos.quantity + EPS:
            raise PortfolioError(
                f"Venda de {rest_sell:g} {ticker} em {day:%d/%m/%Y} maior que a posição disponível ({pos.quantity:g})."
            )
        cost = pos.avg_price * rest_sell
        gross, net = rest_sell * sgross / sq, rest_sell * snet / sq
        ledger.sales.append(Sale(day, ticker, asset_type, rest_sell, gross, net, cost, net - cost))
        pos.realized += net - cost
        pos.quantity -= rest_sell
        pos.total_cost -= cost
        if pos.quantity <= EPS:
            pos.quantity, pos.total_cost = 0.0, 0.0


def _apply_event(ledger: Ledger, ev: EventInput) -> None:
    pos = ledger.positions.get(ev.ticker)
    if pos is None or pos.quantity <= EPS:
        return
    if ev.kind == "SPLIT" and ev.factor:
        pos.quantity *= ev.factor
    elif ev.kind == "REVERSE_SPLIT" and ev.factor:
        pos.quantity /= ev.factor
    elif ev.kind == "AMORTIZATION" and ev.amount:
        pos.total_cost = max(pos.total_cost - ev.amount, 0.0)


def build_ledger(
    transactions: list[TxInput], events: list[EventInput] | None = None, until: date | None = None
) -> Ledger:
    ledger = Ledger()
    tx_by_day: dict[date, dict[str, list[TxInput]]] = defaultdict(lambda: defaultdict(list))
    for tx in sorted(transactions, key=lambda t: (t.date, t.id)):
        tx_by_day[tx.date][tx.ticker].append(tx)
    ev_by_day: dict[date, list[EventInput]] = defaultdict(list)
    for ev in events or []:
        ev_by_day[ev.date].append(ev)

    for day in sorted(set(tx_by_day) | set(ev_by_day)):
        if until and day > until:
            break
        for ev in ev_by_day.get(day, []):
            if ev.kind in ("SPLIT", "REVERSE_SPLIT"):
                _apply_event(ledger, ev)
        for ticker, txs in sorted(tx_by_day.get(day, {}).items()):
            _apply_trades(ledger, ticker, txs)
        for ev in ev_by_day.get(day, []):
            if ev.kind == "AMORTIZATION":
                _apply_event(ledger, ev)
    return ledger


def quantity_held(
    transactions: list[TxInput], ticker: str, on: date, events: list[EventInput] | None = None
) -> float:
    """Quantidade em carteira ao final do dia `on` (já considerando desdobramentos)."""
    relevant = [t for t in transactions if t.ticker == ticker]
    rel_events = [e for e in events or [] if e.ticker == ticker and e.kind != "AMORTIZATION"]
    return build_ledger(relevant, rel_events, until=on).quantity(ticker)
