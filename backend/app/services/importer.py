"""Leitura de extratos da B3 (Área do Investidor) e de planilhas no modelo próprio.

Formatos aceitos (.xlsx ou .csv):
- B3 "Negociação": Data do Negócio, Tipo de Movimentação, Código de Negociação, Quantidade, Preço...
- B3 "Movimentação": Entrada/Saída, Data, Movimentação, Produto, Quantidade, Preço unitário, Valor da Operação
  (importa rendimentos, dividendos, JCP e amortizações).
- Modelo próprio: ticker, operacao (compra/venda), data, quantidade, preco, taxas (opcional), classe (opcional).
"""

import csv
import io
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime

from ..catalog import CATALOG_BY_TICKER

TICKER_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")


class ImportError_(ValueError):
    pass


@dataclass
class ParsedRow:
    line: int
    kind: str  # trade | dividend
    ticker: str
    date: date | None
    quantity: float
    price: float = 0.0  # preço (trade) ou valor por cota (dividend)
    fees: float = 0.0
    side: str | None = None  # BUY | SELL
    asset_type: str | None = None
    dividend_kind: str | None = None
    amount: float = 0.0
    status: str = "ok"  # ok | duplicate | ignored | error
    reason: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat() if self.date else None
        return d


def _norm(text: object) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def parse_number(value: object) -> float:
    if value is None or value == "" or value == "-":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace("R$", "").replace("\xa0", "").strip()
    if re.search(r",\d{1,}$", s) or ("," in s and "." in s and s.rfind(",") > s.rfind(".")):
        s = s.replace(".", "").replace(",", ".")  # 1.234,56
    else:
        s = s.replace(",", "")  # 1,234.56
    try:
        return float(s)
    except ValueError as exc:
        raise ValueError(f"número inválido: {value!r}") from exc


def parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {value!r}")


def normalize_ticker(raw: object) -> str:
    t = str(raw or "").strip().upper().split(" ")[0]
    if re.fullmatch(r"[A-Z]{4}\d{1,2}F", t):  # mercado fracionário
        t = t[:-1]
    return t


def guess_type(ticker: str) -> str:
    meta = CATALOG_BY_TICKER.get(ticker)
    return meta.asset_type if meta else "FII"


def read_table(filename: str, content: bytes) -> list[list[object]]:
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:  # arquivo corrompido ou não-xlsx
            raise ImportError_("Não foi possível ler a planilha .xlsx") from exc
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows
    if name.endswith((".csv", ".txt")):
        for enc in ("utf-8-sig", "latin-1"):
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sample = text[:4096]
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]
    raise ImportError_("Formato não suportado: envie um arquivo .xlsx ou .csv")


DIVIDEND_KINDS = {
    "rendimento": "RENDIMENTO",
    "dividendo": "DIVIDENDO",
    "juros sobre capital proprio": "JCP",
    "amortizacao": "AMORTIZACAO",
}


def _col(header: list[str], *names: str) -> int | None:
    for n in names:
        if n in header:
            return header.index(n)
    return None


def parse_file(filename: str, content: bytes) -> tuple[str, list[ParsedRow]]:
    table = [r for r in read_table(filename, content) if any(c not in (None, "") for c in r)]
    if not table:
        raise ImportError_("Arquivo vazio")
    header = [_norm(c) for c in table[0]]
    body = table[1:]

    if "data do negocio" in header and "codigo de negociacao" in header:
        return "b3_negociacao", _parse_b3_trades(header, body)
    if "movimentacao" in header and "produto" in header:
        return "b3_movimentacao", _parse_b3_movements(header, body)
    if "ticker" in header and ("operacao" in header or "tipo" in header):
        return "modelo", _parse_template(header, body)
    raise ImportError_(
        "Cabeçalho não reconhecido. Use o extrato de Negociação ou Movimentação da B3, "
        "ou o modelo: ticker;operacao;data;quantidade;preco;taxas"
    )


def _cell(row: list[object], idx: int | None) -> object:
    return row[idx] if idx is not None and idx < len(row) else None


def _side(value: object) -> str | None:
    v = _norm(value)
    if v.startswith(("compra", "c", "buy")):
        return "BUY"
    if v.startswith(("venda", "v", "sell")):
        return "SELL"
    return None


def _parse_b3_trades(header: list[str], body: list[list[object]]) -> list[ParsedRow]:
    i_date = _col(header, "data do negocio")
    i_side = _col(header, "tipo de movimentacao")
    i_ticker = _col(header, "codigo de negociacao")
    i_qty = _col(header, "quantidade")
    i_price = _col(header, "preco")
    rows = []
    for n, r in enumerate(body, start=2):
        ticker = normalize_ticker(_cell(r, i_ticker))
        row = ParsedRow(n, "trade", ticker, None, 0.0)
        try:
            row.date = parse_date(_cell(r, i_date))
            row.side = _side(_cell(r, i_side))
            row.quantity = parse_number(_cell(r, i_qty))
            row.price = parse_number(_cell(r, i_price))
        except ValueError as exc:
            row.status, row.reason = "error", str(exc)
            rows.append(row)
            continue
        row.asset_type = guess_type(ticker)
        _check_trade(row)
        rows.append(row)
    return rows


def _check_trade(row: ParsedRow) -> None:
    if not TICKER_RE.match(row.ticker):
        row.status, row.reason = "ignored", "código de negociação não suportado"
    elif not row.ticker.endswith(("11", "12", "13")):
        row.status, row.reason = "ignored", "ação (o app acompanha FIIs e ETFs)"
    elif row.side is None:
        row.status, row.reason = "error", "operação deve ser compra ou venda"
    elif row.quantity <= 0 or row.price <= 0:
        row.status, row.reason = "error", "quantidade e preço devem ser positivos"


def _parse_b3_movements(header: list[str], body: list[list[object]]) -> list[ParsedRow]:
    i_io = _col(header, "entrada/saida")
    i_date = _col(header, "data")
    i_mov = _col(header, "movimentacao")
    i_prod = _col(header, "produto")
    i_qty = _col(header, "quantidade")
    i_unit = _col(header, "preco unitario")
    i_value = _col(header, "valor da operacao")
    rows = []
    for n, r in enumerate(body, start=2):
        mov = _norm(_cell(r, i_mov))
        ticker = normalize_ticker(_cell(r, i_prod))
        kind = DIVIDEND_KINDS.get(mov)
        row = ParsedRow(n, "dividend", ticker, None, 0.0, dividend_kind=kind)
        if kind is None or _norm(_cell(r, i_io)) != "credito":
            row.status, row.reason = "ignored", f"movimentação “{_cell(r, i_mov)}” não importada"
            rows.append(row)
            continue
        try:
            row.date = parse_date(_cell(r, i_date))
            row.quantity = parse_number(_cell(r, i_qty))
            row.amount = parse_number(_cell(r, i_value))
            row.price = parse_number(_cell(r, i_unit)) or (row.amount / row.quantity if row.quantity else 0.0)
        except ValueError as exc:
            row.status, row.reason = "error", str(exc)
            rows.append(row)
            continue
        if not TICKER_RE.match(ticker):
            row.status, row.reason = "ignored", "produto não reconhecido"
        elif row.amount <= 0 or row.quantity <= 0:
            row.status, row.reason = "ignored", "valor ainda não disponível (provisionado)"
        rows.append(row)
    return rows


def _parse_template(header: list[str], body: list[list[object]]) -> list[ParsedRow]:
    i_ticker = _col(header, "ticker")
    i_side = _col(header, "operacao", "tipo")
    i_date = _col(header, "data")
    i_qty = _col(header, "quantidade", "qtd")
    i_price = _col(header, "preco", "preco unitario")
    i_fees = _col(header, "taxas", "custos")
    i_type = _col(header, "classe")
    rows = []
    for n, r in enumerate(body, start=2):
        ticker = normalize_ticker(_cell(r, i_ticker))
        row = ParsedRow(n, "trade", ticker, None, 0.0)
        try:
            row.date = parse_date(_cell(r, i_date))
            row.side = _side(_cell(r, i_side))
            row.quantity = parse_number(_cell(r, i_qty))
            row.price = parse_number(_cell(r, i_price))
            row.fees = parse_number(_cell(r, i_fees))
        except ValueError as exc:
            row.status, row.reason = "error", str(exc)
            rows.append(row)
            continue
        cls = str(_cell(r, i_type) or "").strip().upper().replace(" ", "_")
        row.asset_type = cls if cls in ("FII", "ETF", "ETF_RF") else guess_type(ticker)
        _check_trade(row)
        if row.status == "ignored" and row.reason and row.reason.startswith("ação"):
            row.status, row.reason = "ok", None  # no modelo próprio o usuário decide
        rows.append(row)
    return rows
