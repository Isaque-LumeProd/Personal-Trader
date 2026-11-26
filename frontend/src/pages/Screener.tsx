import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ScreenerRow } from "../api";
import { Field, PageHead, ProviderNotice, RecBadge, Segmented } from "../components/ui";
import { compactMoney, fixed, money, number, pct, signedPct, tone, TYPE_LABEL } from "../format";
import { useApi } from "../hooks";

type Col = { key: keyof ScreenerRow; label: string; render: (r: ScreenerRow) => React.ReactNode; types?: string[] };

const COLUMNS: Col[] = [
  {
    key: "score",
    label: "Score",
    render: (r) =>
      r.score == null ? "—" : (
        <span title="Pontuação relativa aos pares da mesma classe (0–100)">
          <span className="score-bar"><b style={{ width: `${r.score}%` }} /></span>
          {r.score}
        </span>
      ),
  },
  { key: "price", label: "Cotação", render: (r) => money(r.price) },
  { key: "dy_12m", label: "DY 12m", render: (r) => pct(r.dy_12m), types: ["FII", "ETF", ""] },
  { key: "last_dividend", label: "Últ. provento", render: (r) => (r.last_dividend ? `R$ ${number(r.last_dividend, 4)}` : "—"), types: ["FII", ""] },
  { key: "pvp", label: "P/VP", render: (r) => (r.pvp == null ? "—" : fixed(r.pvp)), types: ["FII", ""] },
  { key: "avg_daily_liquidity", label: "Liquidez diária", render: (r) => compactMoney(r.avg_daily_liquidity) },
  { key: "return_1m", label: "1 mês", render: (r) => <span className={tone(r.return_1m)}>{signedPct(r.return_1m)}</span> },
  { key: "return_12m", label: "12 meses", render: (r) => <span className={tone(r.return_12m)}>{signedPct(r.return_12m)}</span> },
  { key: "volatility", label: "Volatilidade", render: (r) => pct(r.volatility, 1) },
  { key: "rsi14", label: "RSI", render: (r) => number(r.rsi14, 0) },
];

export default function Screener() {
  const [type, setType] = useState<"FII" | "ETF" | "ETF_RF" | "">("FII");
  const [segment, setSegment] = useState("");
  const [minDy, setMinDy] = useState("");
  const [maxPvp, setMaxPvp] = useState("");
  const [minLiq, setMinLiq] = useState("");
  const [sort, setSort] = useState<keyof ScreenerRow>("score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const query = useMemo(() => {
    const p = new URLSearchParams({ sort: String(sort), order });
    if (type) p.set("asset_type", type);
    if (segment) p.set("segment", segment);
    if (minDy) p.set("min_dy", minDy.replace(",", "."));
    if (maxPvp) p.set("max_pvp", maxPvp.replace(",", "."));
    if (minLiq) p.set("min_liquidity", String(Number(minLiq) * 1000));
    return `/screener?${p}`;
  }, [type, segment, minDy, maxPvp, minLiq, sort, order]);

  const { data, error, loading } = useApi<{ provider: string; results: ScreenerRow[]; segments: string[]; errors: Record<string, string> }>(query);
  const columns = COLUMNS.filter((c) => !c.types || c.types.includes(type));

  function toggleSort(key: keyof ScreenerRow) {
    if (key === sort) setOrder(order === "desc" ? "asc" : "desc");
    else {
      setSort(key);
      setOrder(key === "pvp" || key === "volatility" ? "asc" : "desc");
    }
  }

  return (
    <div className="stack">
      <PageHead title="Screener" subtitle="Encontre FIIs e ETFs por rendimento, preço, liquidez e sinais técnicos" />
      <ProviderNotice provider={data?.provider} />
      <div className="card">
        <div className="form-row">
          <Segmented
            value={type}
            onChange={(v) => { setType(v); setSegment(""); }}
            options={[
              { value: "FII", label: "FIIs" },
              { value: "ETF", label: "ETFs" },
              { value: "ETF_RF", label: "ETFs RF" },
              { value: "", label: "Todos" },
            ]}
          />
          <Field label="Segmento">
            <select value={segment} onChange={(e) => setSegment(e.target.value)}>
              <option value="">Todos</option>
              {data?.segments.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="DY mínimo (%)">
            <input inputMode="decimal" value={minDy} onChange={(e) => setMinDy(e.target.value)} size={6} placeholder="8" />
          </Field>
          {(type === "FII" || type === "") && (
            <Field label="P/VP máximo">
              <input inputMode="decimal" value={maxPvp} onChange={(e) => setMaxPvp(e.target.value)} size={6} placeholder="1,0" />
            </Field>
          )}
          <Field label="Liquidez mín. (R$ mil/dia)">
            <input inputMode="numeric" value={minLiq} onChange={(e) => setMinLiq(e.target.value)} size={8} placeholder="500" />
          </Field>
        </div>
      </div>
      <div className="card">
        {error && <p className="error">{error}</p>}
        {Object.keys(data?.errors ?? {}).length > 0 && (
          <p className="muted small">Sem dados para: {Object.keys(data!.errors).join(", ")}</p>
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="sortable" onClick={() => toggleSort("ticker")}>Ativo {sort === "ticker" && (order === "desc" ? "↓" : "↑")}</th>
                {columns.map((c) => (
                  <th key={c.key} className="sortable num" onClick={() => toggleSort(c.key)}>
                    {c.label} {sort === c.key && (order === "desc" ? "↓" : "↑")}
                  </th>
                ))}
                <th>Sinal técnico</th>
              </tr>
            </thead>
            <tbody>
              {data?.results.map((r) => (
                <tr key={r.ticker}>
                  <td>
                    <div className="ticker">
                      <Link to={`/analise/${r.ticker}`}>{r.ticker}</Link>{" "}
                      {r.in_portfolio && <span className="badge info" title="Na sua carteira">carteira</span>}
                    </div>
                    <div className="muted small">
                      {type === "" && `${TYPE_LABEL[r.asset_type ?? "FII"]} · `}
                      {r.segment}
                    </div>
                  </td>
                  {columns.map((c) => (
                    <td key={c.key} className="num">{c.render(r)}</td>
                  ))}
                  <td><RecBadge rec={r.recommendation} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && data?.results.length === 0 && <div className="empty">Nenhum ativo atende aos filtros.</div>}
          {loading && !data && <div className="empty">Carregando…</div>}
        </div>
        <p className="muted small" style={{ marginTop: 12 }}>
          Score: FIIs ponderam DY (40%), P/VP (30%), liquidez (15%) e baixa volatilidade (15%); ETFs ponderam retorno 12m, volatilidade e liquidez.
        </p>
      </div>
    </div>
  );
}
