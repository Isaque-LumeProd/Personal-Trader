import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type AlertCheck, type Summary } from "../api";
import { AXIS, AllocationBars, GRID, Legend, Tip } from "../components/charts";
import { Disclaimer, Kpi, MoneyDelta, PageHead, ProviderNotice, Segmented } from "../components/ui";
import { compactMoney, date, money, monthLabel, number, pct, signedPct, tone, TYPE_LABEL } from "../format";
import { useApi } from "../hooks";
import { notifyUnreadChanged } from "../notifications";

const RANGES = [
  { value: "90", label: "3M" },
  { value: "180", label: "6M" },
  { value: "365", label: "1A" },
];

export default function Dashboard() {
  const { data, error, loading } = useApi<Summary>("/portfolio/summary");
  const [range, setRange] = useState("180");
  const evo = useApi<{ points: { date: string; market_value: number; invested: number }[] }>(`/portfolio/evolution?days=${range}`);
  const [allocBy, setAllocBy] = useState<"type" | "segment">("type");
  const [alerts, setAlerts] = useState<AlertCheck | null>(null);
  useEffect(() => {
    api<AlertCheck>("/alerts/check", { method: "POST" })
      .then((r) => {
        setAlerts(r);
        notifyUnreadChanged();
      })
      .catch(() => setAlerts(null));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="empty">{loading ? "Carregando carteira…" : ""}</div>;

  const t = data.totals;
  const empty = data.positions.length === 0;
  const triggered = alerts?.results.filter((r) => r.triggered) ?? [];

  return (
    <div className="stack">
      <PageHead title="Carteira" subtitle="Visão consolidada dos seus FIIs e ETFs">
        <Link className="btn" to="/lancamentos">
          + Lançamento
        </Link>
      </PageHead>
      <ProviderNotice provider={data.provider} />
      {Object.keys(data.market_errors).length > 0 && (
        <div className="notice">
          Sem cotação para {Object.keys(data.market_errors).join(", ")} — usando o preço médio.
        </div>
      )}
      {triggered.length > 0 && (
        <div className="notice info">
          {triggered.map((r) => (
            <div key={r.alert_id}>⚑ {r.message}</div>
          ))}
        </div>
      )}

      {empty ? (
        <div className="card empty">
          <h2>Sua carteira está vazia</h2>
          <p>
            Registre suas compras em <Link to="/lancamentos">Lançamentos</Link> ou explore oportunidades no{" "}
            <Link to="/screener">Screener</Link>.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-kpi">
            <Kpi
              label="Patrimônio"
              value={money(t.market_value)}
              sub={<>Hoje: <MoneyDelta value={t.day_change} /></>}
            />
            <Kpi label="Valor investido" value={money(t.cost)} sub={`Resultado realizado: ${money(t.realized)}`} />
            <Kpi
              label="Valorização"
              value={<MoneyDelta value={t.unrealized} />}
              sub={signedPct(t.unrealized_pct)}
              subTone={tone(t.unrealized_pct)}
            />
            <Kpi
              label="Proventos (12 meses)"
              value={money(t.dividends_12m)}
              sub={`Yield on cost: ${pct(t.yield_on_cost_12m)}`}
            />
            <Kpi label="Retorno total" value={<MoneyDelta value={t.total_return} />} sub="Valorização + vendas + proventos" />
          </div>

          <div className="grid grid-3-1">
            <div className="card">
              <div className="chart-head">
                <h2>Evolução do patrimônio</h2>
                <Segmented value={range} options={RANGES} onChange={setRange} />
              </div>
              <Legend
                items={[
                  { label: "Patrimônio", color: "var(--s1)" },
                  { label: "Valor investido", color: "var(--muted-series)", kind: "dash" },
                ]}
              />
              <div style={{ height: 260, marginTop: 8 }}>
                <ResponsiveContainer>
                  <AreaChart data={evo.data?.points ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="pv" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--s1)" stopOpacity={0.22} />
                        <stop offset="100%" stopColor="var(--s1)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid {...GRID} />
                    <XAxis dataKey="date" {...AXIS} tickFormatter={(d: string) => date(d).slice(0, 5)} minTickGap={40} />
                    <YAxis {...AXIS} axisLine={false} width={84} tickFormatter={(v: number) => compactMoney(v)} domain={["auto", "auto"]} />
                    <Tooltip
                      cursor={{ stroke: "var(--axis)" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <Tip
                            title={date(payload[0].payload.date)}
                            rows={[
                              { label: "Patrimônio", value: money(payload[0].payload.market_value), color: "var(--s1)" },
                              { label: "Investido", value: money(payload[0].payload.invested), color: "var(--muted-series)" },
                            ]}
                          />
                        ) : null
                      }
                    />
                    <Area type="monotone" dataKey="market_value" stroke="var(--s1)" strokeWidth={2} fill="url(#pv)" dot={false} activeDot={{ r: 4 }} />
                    <Line type="stepAfter" dataKey="invested" stroke="var(--muted-series)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="card">
              <div className="chart-head">
                <h2>Alocação</h2>
                <Segmented
                  value={allocBy}
                  options={[
                    { value: "type", label: "Classe" },
                    { value: "segment", label: "Segmento" },
                  ]}
                  onChange={setAllocBy}
                />
              </div>
              <AllocationBars items={allocBy === "type" ? data.allocation_by_type : data.allocation_by_segment} format={money} />
            </div>
          </div>

          <div className="card">
            <h2>Posições</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Ativo</th>
                    <th>Classe</th>
                    <th className="num">Qtd.</th>
                    <th className="num">Preço médio</th>
                    <th className="num">Cotação</th>
                    <th className="num">Dia</th>
                    <th className="num">Saldo</th>
                    <th className="num">Valorização</th>
                    <th className="num">Proventos 12m</th>
                    <th className="num">YoC 12m</th>
                    <th className="num">Peso</th>
                  </tr>
                </thead>
                <tbody>
                  {data.positions.map((p) => (
                    <tr key={p.ticker}>
                      <td>
                        <div className="ticker">
                          <Link to={`/analise/${p.ticker}`}>{p.ticker}</Link>
                        </div>
                        <div className="muted small">{p.segment}</div>
                      </td>
                      <td><span className="badge">{TYPE_LABEL[p.asset_type]}</span></td>
                      <td className="num">{number(p.quantity, 4)}</td>
                      <td className="num">{money(p.avg_price)}</td>
                      <td className="num">{money(p.price)}</td>
                      <td className={`num ${tone(p.change_pct)}`}>{signedPct(p.change_pct)}</td>
                      <td className="num">{money(p.market_value)}</td>
                      <td className="num">
                        <MoneyDelta value={p.unrealized} />
                        <div className={`small ${tone(p.unrealized_pct)}`}>{signedPct(p.unrealized_pct)}</div>
                      </td>
                      <td className="num">{money(p.dividends_12m)}</td>
                      <td className="num">{pct(p.yield_on_cost_12m)}</td>
                      <td className="num">{pct(p.weight, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-3-1">
            <div className="card">
              <div className="chart-head">
                <h2>Proventos recebidos por mês</h2>
                <span className="muted small">Total 12m: {money(t.dividends_12m)}</span>
              </div>
              <div style={{ height: 220 }}>
                <ResponsiveContainer>
                  <BarChart data={data.dividends_monthly} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid {...GRID} />
                    <XAxis dataKey="month" {...AXIS} tickFormatter={monthLabel} />
                    <YAxis {...AXIS} axisLine={false} width={84} tickFormatter={(v: number) => compactMoney(v)} />
                    <Tooltip
                      cursor={{ fill: "var(--surface-2)" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <Tip title={monthLabel(payload[0].payload.month)} rows={[{ label: "Proventos", value: money(payload[0].payload.amount), color: "var(--s1)" }]} />
                        ) : null
                      }
                    />
                    <Bar dataKey="amount" fill="var(--s1)" radius={[4, 4, 0, 0]} maxBarSize={36} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="card">
              <h2>Próximos pagamentos</h2>
              {data.upcoming_dividends.length === 0 ? (
                <p className="muted small">
                  Nenhum provento a receber registrado. Use <Link to="/proventos">Sincronizar proventos</Link>.
                </p>
              ) : (
                <table>
                  <tbody>
                    {data.upcoming_dividends.map((d) => (
                      <tr key={`${d.ticker}-${d.payment_date}`}>
                        <td className="ticker">{d.ticker}</td>
                        <td className="muted">{date(d.payment_date)}</td>
                        <td className="num">{money(d.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}
      <Disclaimer />
    </div>
  );
}

