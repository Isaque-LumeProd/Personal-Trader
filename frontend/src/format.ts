const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const num = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

export const money = (v: number | null | undefined) => (v == null ? "—" : brl.format(v));
export const number = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
export const fixed = (v: number, digits = 2) =>
  v.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const pct = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : `${v.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
export const signedPct = (v: number | null | undefined) => (v == null ? "—" : `${v > 0 ? "+" : ""}${pct(v)}`);
export const compactMoney = (v: number | null | undefined) => (v == null ? "—" : `R$ ${compact.format(v)}`);
export const qty = (v: number) => num.format(v);

export function date(iso: string | null | undefined) {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
export function monthLabel(ym: string) {
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1]}/${y.slice(2)}`;
}

export const tone = (v: number | null | undefined) => (v == null || v === 0 ? "" : v > 0 ? "pos" : "neg");

export const TYPE_LABEL: Record<string, string> = { FII: "FII", ETF: "ETF", ETF_RF: "ETF RF" };

export function today() {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}
