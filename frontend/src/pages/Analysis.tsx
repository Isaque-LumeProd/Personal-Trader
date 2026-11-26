import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Area, Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Analysis as AnalysisData, SeriesPoint } from "../api";
import { AXIS, GRID, Legend, Tip } from "../components/charts";
import { DirectionBadge, Disclaimer, PageHead, ProviderNotice, RecBadge, Segmented } from "../components/ui";
import { compactMoney, date, fixed, money, number, pct, signedPct, tone } from "../format";
import { useApi } from "../hooks";

const RANGES = [
  { value: "90", label: "3M" },
  { value: "180", label: "6M" },
  { value: "365", label: "1A" },
];

const fmt = (v: number | null | undefined, d = 2) => (v == null ? "—" : number(v, d));
const tickDate = (d: string) => date(d).slice(0, 5);

export default function Analysis() {
  const { ticker = "HGLG11" } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState(ticker);
  const [range, setRange] = useState("180");
  const { data, error, loading } = useApi<AnalysisData>(`/market/analysis/${ticker}?days=${range}`);

  function go(e: FormEvent) {
    e.preventDefault();
    const t = input.trim().toUpperCase();
    if (t) navigate(`/analise/${t}`);
  }

  const m = data?.metrics;
  // banda de Bollinger como área de intervalo [inferior, superior]
  const series = (data?.series ?? []).map((p) => ({
    ...p,
    bb_range: p.bb_upper != null && p.bb_lower != null ? [p.bb_lower, p.bb_upper] : null,
  }));
  const priceDomain = (() => {
    const vals = series.flatMap((p) => [p.close, p.bb_upper, p.bb_lower, p.sma50].filter((v): v is number => v != null));
    if (!vals.length) return ["auto", "auto"] as const;
    const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * 0.05;
    return [Math.floor((lo - pad) * 100) / 100, Math.ceil((hi + pad) * 100) / 100] as const;
  })();

  return (
    <div className="stack">
      <PageHead title="Análise técnica" subtitle="Indicadores, sinais de compra e venda e fundamentos">
        <form onSubmit={go} className="form-row">
          <input className="inline" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ticker (ex.: MXRF11)" size={14} />
          <button className="btn">Analisar</button>
        </form>
      </PageHead>
      <ProviderNotice provider={data?.provider} />
      {error && <div className="error">{error}</div>}
      {loading && !data && <div className="empty">Carregando {ticker}…</div>}

      {data && m && (
        <>
          <div className="card">
            <div className="chart-head" style={{ alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0 }}>
                  {m.ticker} <span className="muted" style={{ fontWeight: 400 }}>· {m.name}</span>
                </h2>
                <div style={{ fontSize: "1.6rem", fontWeight: 650 }}>
                  {money(m.price)} <span className={`small ${tone(m.change_pct)}`}>{signedPct(m.change_pct)} hoje</span>
                </div>
              </div>
              <div style={{ minWidth: 220 }}>
                <div className="muted small">Sinal técnico consolidado</div>
                <RecBadge rec={data.technical.recommendation} />
                <div className="gauge" title={`Pontuação ${data.technical.score} (de -100 a 100)`}>
                  <i style={{ left: `${(data.technical.score + 100) / 2}%` }} />
                </div>
                <div className="legend" style={{ justifyContent: "space-between" }}>
                  <span>Venda</span><span>{data.technical.score}</span><span>Compra</span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-stats">
            <Stat label="DY 12 meses" value={pct(m.dy_12m)} sub={`R$ ${number(m.dividends_12m, 4)} por cota`} />
            <Stat label="Último provento" value={m.last_dividend ? `R$ ${number(m.last_dividend, 4)}` : "—"} sub={m.last_dividend_yield ? `${pct(m.last_dividend_yield)} no mês` : undefined} />
            <Stat label="P/VP" value={m.pvp == null ? "—" : fixed(m.pvp)} sub={m.pvp == null ? "Não informado pela fonte" : undefined} />
            <Stat label="Liquidez média diária" value={compactMoney(m.avg_daily_liquidity)} />
            <Stat label="Retorno 12 meses" value={<span className={tone(m.return_12m)}>{signedPct(m.return_12m)}</span>} sub={`3m: ${signedPct(m.return_3m)}`} />
            <Stat label="Volatilidade anual" value={pct(m.volatility, 1)} />
          </div>

          <div className="card">
            <div className="chart-head">
              <h2>Preço</h2>
              <Segmented value={range} options={RANGES} onChange={setRange} />
            </div>
            <Legend
              items={[
                { label: "Fechamento", color: "var(--s1)" },
                { label: "Média 20", color: "var(--s2)" },
                { label: "Média 50", color: "var(--s3)" },
                { label: "Bandas de Bollinger", color: "var(--band)", kind: "box" },
              ]}
            />
            <div style={{ height: 320, marginTop: 8 }}>
              <ResponsiveContainer>
                <ComposedChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="date" {...AXIS} tickFormatter={tickDate} minTickGap={40} />
                  <YAxis {...AXIS} axisLine={false} width={56} domain={priceDomain as never} allowDataOverflow tickFormatter={(v: number) => number(v, 2)} />
                  <Tooltip cursor={{ stroke: "var(--axis)" }} content={({ active, payload }) => (active && payload?.length ? <PriceTip p={payload[0].payload} /> : null)} />
                  <Area dataKey="bb_range" stroke="none" fill="var(--band)" fillOpacity={1} isAnimationActive={false} activeDot={false} />
                  <Line dataKey="sma20" stroke="var(--s2)" strokeWidth={1.5} dot={false} isAnimationActive={false} activeDot={false} />
                  <Line dataKey="sma50" stroke="var(--s3)" strokeWidth={1.5} dot={false} isAnimationActive={false} activeDot={false} />
                  <Line dataKey="close" stroke="var(--s1)" strokeWidth={2} dot={false} isAnimationActive={false} activeDot={{ r: 4 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <div className="chart-head">
                <h2>RSI (14)</h2>
                <span className="muted small">Acima de 70: sobrecompra · abaixo de 30: sobrevenda</span>
              </div>
              <div style={{ height: 180 }}>
                <ResponsiveContainer>
                  <ComposedChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid {...GRID} />
                    <XAxis dataKey="date" {...AXIS} tickFormatter={tickDate} minTickGap={40} />
                    <YAxis {...AXIS} axisLine={false} width={40} domain={[0, 100]} ticks={[0, 30, 50, 70, 100]} />
                    <ReferenceLine y={70} stroke="var(--axis)" strokeDasharray="4 4" />
                    <ReferenceLine y={30} stroke="var(--axis)" strokeDasharray="4 4" />
                    <Tooltip
                      cursor={{ stroke: "var(--axis)" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? <Tip title={date(payload[0].payload.date)} rows={[{ label: "RSI", value: fmt(payload[0].payload.rsi, 1), color: "var(--s1)" }]} /> : null
                      }
                    />
                    <Line dataKey="rsi" stroke="var(--s1)" strokeWidth={2} dot={false} isAnimationActive={false} activeDot={{ r: 4 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="card">
              <div className="chart-head">
                <h2>MACD (12, 26, 9)</h2>
                <Legend
                  items={[
                    { label: "MACD", color: "var(--s1)" },
                    { label: "Sinal", color: "var(--s2)" },
                    { label: "Histograma", color: "var(--muted-series)", kind: "box" },
                  ]}
                />
              </div>
              <div style={{ height: 180 }}>
                <ResponsiveContainer>
                  <ComposedChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid {...GRID} />
                    <XAxis dataKey="date" {...AXIS} tickFormatter={tickDate} minTickGap={40} />
                    <YAxis {...AXIS} axisLine={false} width={48} tickFormatter={(v: number) => number(v, 2)} />
                    <ReferenceLine y={0} stroke="var(--axis)" />
                    <Tooltip
                      cursor={{ fill: "var(--surface-2)" }}
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const p = payload[0].payload as SeriesPoint;
                        return (
                          <Tip
                            title={date(p.date)}
                            rows={[
                              { label: "MACD", value: fmt(p.macd, 3), color: "var(--s1)" },
                              { label: "Sinal", value: fmt(p.macd_signal, 3), color: "var(--s2)" },
                              { label: "Histograma", value: fmt(p.macd_hist, 3), color: "var(--muted-series)" },
                            ]}
                          />
                        );
                      }}
                    />
                    <Bar dataKey="macd_hist" isAnimationActive={false} maxBarSize={6}>
                      {series.map((p) => (
                        <Cell key={p.date} fill={(p.macd_hist ?? 0) >= 0 ? "var(--pos)" : "var(--neg)"} fillOpacity={0.45} />
                      ))}
                    </Bar>
                    <Line dataKey="macd" stroke="var(--s1)" strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line dataKey="macd_signal" stroke="var(--s2)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <h2>Sinais</h2>
              <ul className="signal-list">
                {[...data.technical.signals, ...data.fundamentals].map((s) => (
                  <li key={s.name}>
                    <DirectionBadge direction={s.direction} />
                    <div>
                      <b>{s.name}</b>
                      <div className="muted small">{s.description}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div className="card">
              <h2>Últimos proventos</h2>
              {data.dividends.length === 0 ? (
                <p className="muted">Sem proventos no período.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Data com</th>
                        <th>Pagamento</th>
                        <th>Tipo</th>
                        <th className="num">Valor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.dividends.map((d) => (
                        <tr key={`${d.ex_date}-${d.rate}`}>
                          <td>{date(d.ex_date)}</td>
                          <td>{date(d.payment_date)}</td>
                          <td className="muted small">{d.label}</td>
                          <td className="num">R$ {number(d.rate, 4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}
      <Disclaimer />
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className="value" style={{ fontSize: "1.3rem" }}>{value}</div>
      {sub && <div className="sub muted">{sub}</div>}
    </div>
  );
}

function PriceTip({ p }: { p: SeriesPoint }) {
  return (
    <Tip
      title={date(p.date)}
      rows={[
        { label: "Fechamento", value: money(p.close), color: "var(--s1)" },
        { label: "Média 20", value: fmt(p.sma20), color: "var(--s2)" },
        { label: "Média 50", value: fmt(p.sma50), color: "var(--s3)" },
        { label: "Bollinger sup.", value: fmt(p.bb_upper) },
        { label: "Bollinger inf.", value: fmt(p.bb_lower) },
        { label: "Volume", value: number(p.volume, 0) },
      ]}
    />
  );
}
