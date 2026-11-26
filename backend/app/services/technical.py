"""Indicadores técnicos e geração de sinais (funções puras)."""

import math
from dataclasses import asdict, dataclass

Series = list[float | None]


def sma(values: list[float], n: int) -> Series:
    out: Series = [None] * len(values)
    window = 0.0
    for i, v in enumerate(values):
        window += v
        if i >= n:
            window -= values[i - n]
        if i >= n - 1:
            out[i] = window / n
    return out


def ema(values: list[float], n: int) -> Series:
    out: Series = [None] * len(values)
    if len(values) < n:
        return out
    k = 2 / (n + 1)
    prev = sum(values[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: list[float], n: int = 14) -> Series:
    """RSI com suavização de Wilder."""
    out: Series = [None] * len(values)
    if len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0)
        losses += max(-delta, 0)
    avg_gain, avg_loss = gains / n, losses / n

    def value(g: float, lo: float) -> float:
        if lo == 0:
            return 100.0 if g > 0 else 50.0
        return 100 - 100 / (1 + g / lo)

    out[n] = value(avg_gain, avg_loss)
    for i in range(n + 1, len(values)):
        delta = values[i] - values[i - 1]
        avg_gain = (avg_gain * (n - 1) + max(delta, 0)) / n
        avg_loss = (avg_loss * (n - 1) + max(-delta, 0)) / n
        out[i] = value(avg_gain, avg_loss)
    return out


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[Series, Series, Series]:
    ema_fast, ema_slow = ema(values, fast), ema(values, slow)
    line: Series = [f - s if f is not None and s is not None else None for f, s in zip(ema_fast, ema_slow)]
    start = next((i for i, v in enumerate(line) if v is not None), None)
    sig: Series = [None] * len(values)
    if start is not None:
        sig_part = ema([v for v in line[start:] if v is not None], signal)
        sig[start:] = sig_part
    hist: Series = [m - s if m is not None and s is not None else None for m, s in zip(line, sig)]
    return line, sig, hist


def bollinger(values: list[float], n: int = 20, k: float = 2.0) -> tuple[Series, Series, Series]:
    mid = sma(values, n)
    upper: Series = [None] * len(values)
    lower: Series = [None] * len(values)
    for i in range(n - 1, len(values)):
        window = values[i - n + 1 : i + 1]
        m = mid[i]
        assert m is not None
        sd = math.sqrt(sum((v - m) ** 2 for v in window) / n)
        upper[i], lower[i] = m + k * sd, m - k * sd
    return mid, upper, lower


def annualized_volatility(values: list[float], window: int = 60) -> float | None:
    if len(values) < 3:
        return None
    vals = values[-(window + 1) :]
    rets = [math.log(b / a) for a, b in zip(vals, vals[1:]) if a > 0 and b > 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


@dataclass
class Signal:
    name: str
    direction: str  # BUY | SELL | NEUTRAL
    weight: float
    description: str


def _crossed(a: Series, b: Series, lookback: int) -> str | None:
    """Detecta cruzamento de `a` sobre `b` nas últimas `lookback` barras."""
    n = len(a)
    for i in range(n - 1, max(n - 1 - lookback, 0), -1):
        a0, a1, b0, b1 = a[i - 1], a[i], b[i - 1], b[i]
        if None in (a0, a1, b0, b1):
            return None
        if a0 <= b0 and a1 > b1:  # type: ignore[operator]
            return "UP"
        if a0 >= b0 and a1 < b1:  # type: ignore[operator]
            return "DOWN"
    return None


def generate_signals(closes: list[float]) -> dict:
    """Combina indicadores clássicos em uma recomendação com pontuação de -100 a 100."""
    signals: list[Signal] = []
    if len(closes) < 30:
        return {"score": 0, "recommendation": "DADOS INSUFICIENTES", "signals": [], "indicators": {}}

    price = closes[-1]
    s20, s50, s200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    r = rsi(closes)
    _, _, hist = macd(closes)
    _, upper, lower = bollinger(closes)

    if s50[-1] is not None:
        long_ma = s200[-1]
        if long_ma is not None:
            if price > s50[-1] > long_ma:
                signals.append(Signal("Tendência", "BUY", 2, "Preço acima das médias de 50 e 200 dias (tendência de alta)."))
            elif price < s50[-1] < long_ma:
                signals.append(Signal("Tendência", "SELL", 2, "Preço abaixo das médias de 50 e 200 dias (tendência de baixa)."))
            else:
                signals.append(Signal("Tendência", "NEUTRAL", 2, "Médias de 50 e 200 dias sem tendência definida."))
        else:
            direction = "BUY" if price > s50[-1] else "SELL"
            signals.append(Signal("Tendência", direction, 1.5, f"Preço {'acima' if direction == 'BUY' else 'abaixo'} da média de 50 dias."))

        cross = _crossed(s20, s50, 5)
        if cross == "UP":
            signals.append(Signal("Cruzamento MM20/MM50", "BUY", 1.5, "Média de 20 cruzou para cima a de 50 nos últimos 5 pregões."))
        elif cross == "DOWN":
            signals.append(Signal("Cruzamento MM20/MM50", "SELL", 1.5, "Média de 20 cruzou para baixo a de 50 nos últimos 5 pregões."))

    if r[-1] is not None:
        if r[-1] < 30:
            signals.append(Signal("RSI(14)", "BUY", 1.5, f"RSI em {round(r[-1])}: ativo sobrevendido."))
        elif r[-1] > 70:
            signals.append(Signal("RSI(14)", "SELL", 1.5, f"RSI em {round(r[-1])}: ativo sobrecomprado."))
        else:
            signals.append(Signal("RSI(14)", "NEUTRAL", 1, f"RSI em {round(r[-1])}: zona neutra."))

    if len(hist) >= 2 and hist[-1] is not None and hist[-2] is not None:
        if hist[-2] <= 0 < hist[-1]:
            signals.append(Signal("MACD", "BUY", 1.5, "MACD cruzou a linha de sinal para cima."))
        elif hist[-2] >= 0 > hist[-1]:
            signals.append(Signal("MACD", "SELL", 1.5, "MACD cruzou a linha de sinal para baixo."))
        else:
            direction = "BUY" if hist[-1] > 0 else "SELL"
            signals.append(Signal("MACD", direction, 0.75, f"Histograma do MACD {'positivo' if hist[-1] > 0 else 'negativo'}."))

    if upper[-1] is not None and lower[-1] is not None:
        if price < lower[-1]:
            signals.append(Signal("Bollinger", "BUY", 1, "Preço abaixo da banda inferior de Bollinger."))
        elif price > upper[-1]:
            signals.append(Signal("Bollinger", "SELL", 1, "Preço acima da banda superior de Bollinger."))

    score = score_signals(signals)
    return {
        "score": score,
        "recommendation": recommendation(score),
        "signals": [asdict(s) for s in signals],
        "indicators": {
            "price": price,
            "sma20": s20[-1],
            "sma50": s50[-1],
            "sma200": s200[-1],
            "rsi14": r[-1],
            "macd_hist": hist[-1],
            "bb_upper": upper[-1],
            "bb_lower": lower[-1],
        },
    }


def score_signals(signals: list[Signal]) -> int:
    total = sum(s.weight for s in signals)
    if not total:
        return 0
    value = {"BUY": 1, "SELL": -1, "NEUTRAL": 0}
    return round(100 * sum(value[s.direction] * s.weight for s in signals) / total)


def recommendation(score: int) -> str:
    if score >= 50:
        return "COMPRA FORTE"
    if score >= 20:
        return "COMPRA"
    if score <= -50:
        return "VENDA FORTE"
    if score <= -20:
        return "VENDA"
    return "NEUTRO"
