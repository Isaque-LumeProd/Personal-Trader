const TOKEN_KEY = "pt_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* armazenamento indisponível */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const isForm = options.body instanceof FormData;
  const headers: Record<string, string> = isForm ? {} : { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : isForm ? (options.body as FormData) : JSON.stringify(options.body),
  });
  if (res.status === 401 && token) onUnauthorized();
  if (!res.ok) {
    let message = `Erro ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* sem corpo JSON */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------- Tipos ----------
export type AssetType = "FII" | "ETF" | "ETF_RF";

export interface User {
  id: number;
  name: string;
  email: string;
}

export interface Transaction {
  id: number;
  ticker: string;
  asset_type: AssetType;
  side: "BUY" | "SELL";
  date: string;
  quantity: number;
  price: number;
  fees: number;
  notes: string | null;
  total: number;
}

export interface Dividend {
  id: number;
  ticker: string;
  kind: string;
  ex_date: string | null;
  payment_date: string;
  quantity: number;
  per_share: number;
  amount: number;
  source: "manual" | "auto" | "import";
}

export interface PositionRow {
  ticker: string;
  name: string;
  asset_type: AssetType;
  segment: string;
  quantity: number;
  avg_price: number;
  price: number;
  price_available: boolean;
  change_pct: number | null;
  cost: number;
  market_value: number;
  unrealized: number;
  unrealized_pct: number;
  realized: number;
  dividends_total: number;
  dividends_12m: number;
  yield_on_cost_12m: number;
  weight: number;
}

export interface AllocationSlice {
  label: string;
  value: number;
  pct: number;
}

export interface Summary {
  provider: string;
  market_errors: Record<string, string>;
  totals: {
    market_value: number;
    cost: number;
    unrealized: number;
    unrealized_pct: number;
    realized: number;
    dividends_total: number;
    dividends_12m: number;
    yield_on_cost_12m: number;
    total_return: number;
    day_change: number;
  };
  positions: PositionRow[];
  allocation_by_type: AllocationSlice[];
  allocation_by_segment: AllocationSlice[];
  dividends_monthly: { month: string; amount: number }[];
  upcoming_dividends: { ticker: string; payment_date: string; amount: number }[];
}

export interface Metrics {
  ticker: string;
  name: string;
  asset_type: AssetType | null;
  segment: string | null;
  price: number;
  change_pct: number;
  dividends_12m: number;
  dy_12m: number | null;
  last_dividend: number | null;
  last_dividend_yield: number | null;
  pvp: number | null;
  avg_daily_liquidity: number | null;
  return_1m: number | null;
  return_3m: number | null;
  return_12m: number | null;
  volatility: number | null;
  rsi14: number | null;
  signal_score: number;
  recommendation: string;
}

export interface ScreenerRow extends Metrics {
  score: number | null;
  in_portfolio: boolean;
}

export interface SignalItem {
  name: string;
  direction: "BUY" | "SELL" | "NEUTRAL";
  weight?: number;
  description: string;
}

export interface SeriesPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  bb_upper: number | null;
  bb_lower: number | null;
  rsi: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
}

export interface Analysis {
  provider: string;
  metrics: Metrics;
  technical: { score: number; recommendation: string; signals: SignalItem[] };
  fundamentals: SignalItem[];
  series: SeriesPoint[];
  dividends: { ex_date: string; payment_date: string | null; rate: number; label: string }[];
}

export interface RebalanceRow {
  ticker: string;
  price: number;
  quantity: number;
  current_value: number;
  current_pct: number;
  target_pct: number;
  target_value: number;
  action: "COMPRAR" | "VENDER" | "MANTER";
  trade_quantity: number;
  trade_value: number;
  final_pct: number;
}

export interface RebalanceResult {
  mode: string;
  contribution: number;
  current_total: number;
  final_total: number;
  cash_left: number;
  rows: RebalanceRow[];
}

export interface TaxCategory {
  category: "FII" | "ETF" | "ETF_DT";
  day_trade_result: number;
  rate: number;
  gross_sales: number;
  result: number;
  loss_compensated: number;
  taxable: number;
  tax_due: number;
  irrf: number;
  tax_net: number;
  loss_carried: number;
}

export interface TaxMonth {
  month: string;
  categories: TaxCategory[];
  withheld_at_source: { ticker: string; date: string; result: number }[];
  tax: number;
  darf_value: number;
  darf_due_date: string | null;
  darf_code: string;
  pending_below_minimum: number;
}

export interface TaxMonthly {
  months: TaxMonth[];
  accumulated_losses: Record<string, number>;
  pending_below_minimum: number;
  total_darf: number;
}

export interface TaxAnnual {
  year: number;
  assets: {
    ticker: string;
    asset_type: AssetType;
    quantity: number;
    avg_price: number;
    value_previous_year: number;
    value_current_year: number;
    description: string;
  }[];
  income: { ticker: string; kind: string; amount: number }[];
  sales: { count: number; gross: number; result: number };
}

export type AlertKind = "PRICE_ABOVE" | "PRICE_BELOW" | "RSI_ABOVE" | "RSI_BELOW" | "DY_ABOVE" | "SIGNAL_BUY" | "SIGNAL_SELL";

export interface Alert {
  id: number;
  ticker: string;
  kind: AlertKind;
  threshold: number | null;
  active: boolean;
  last_triggered_at: string | null;
}

export interface AlertCheck {
  results: { alert_id: number; ticker: string; kind: AlertKind; triggered: boolean; notified: boolean; value: number | null; message: string }[];
  errors: Record<string, string>;
}

export interface CatalogAsset {
  ticker: string;
  name: string;
  asset_type: AssetType;
  segment: string;
}

export interface ImportRow {
  line: number;
  kind: "trade" | "dividend";
  ticker: string;
  date: string | null;
  quantity: number;
  price: number;
  fees: number;
  side: "BUY" | "SELL" | null;
  asset_type: AssetType | null;
  dividend_kind: string | null;
  amount: number;
  status: "ok" | "duplicate" | "ignored" | "error";
  reason: string | null;
}

export interface ImportPreview {
  format: "b3_negociacao" | "b3_movimentacao" | "modelo";
  rows: ImportRow[];
  summary: Partial<Record<ImportRow["status"], number>>;
}

export interface CorporateEvent {
  id: number;
  ticker: string;
  kind: "SPLIT" | "REVERSE_SPLIT";
  date: string;
  factor: number;
  notes: string | null;
}

export interface AppNotification {
  id: number;
  message: string;
  read: boolean;
  channels: string;
  created_at: string;
}

export interface UserSettings {
  telegram_chat_id: string | null;
  notify_email: boolean;
  email: string;
  channels_available: { telegram: boolean; email: boolean };
  alert_check_minutes: number;
  alert_market_hours_only: boolean;
}
