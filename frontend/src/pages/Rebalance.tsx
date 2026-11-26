import { useEffect, useState } from "react";
import { api, type RebalanceResult, type Summary } from "../api";
import { Field, PageHead, Segmented } from "../components/ui";
import { money, number, pct } from "../format";
import { useApi } from "../hooks";

interface TargetRow {
  ticker: string;
  target_pct: string;
}

export default function Rebalance() {
  const targets = useApi<{ ticker: string; target_pct: number }[]>("/rebalance/targets");
  const summary = useApi<Summary>("/portfolio/summary");
  const [rows, setRows] = useState<TargetRow[]>([]);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [contribution, setContribution] = useState("1000");
  const [mode, setMode] = useState<"aporte" | "completo">("aporte");
  const [result, setResult] = useState<RebalanceResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (targets.data) setRows(targets.data.map((t) => ({ ticker: t.ticker, target_pct: String(t.target_pct) })));
  }, [targets.data]);

  const total = rows.reduce((s, r) => s + (Number(r.target_pct.replace(",", ".")) || 0), 0);

  function update(i: number, patch: Partial<TargetRow>) {
    setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

  function fromPortfolio() {
    const positions = summary.data?.positions ?? [];
    setRows(positions.map((p) => ({ ticker: p.ticker, target_pct: String(p.weight) })));
  }

  function equalWeights() {
    if (!rows.length) return;
    const base = Math.floor((10000 / rows.length)) / 100;
    setRows(rows.map((r, i) => ({ ...r, target_pct: String(i === 0 ? +(100 - base * (rows.length - 1)).toFixed(2) : base) })));
  }

  async function save() {
    setSaveMsg(null);
    try {
      const body = rows
        .filter((r) => r.ticker.trim())
        .map((r) => ({ ticker: r.ticker.trim().toUpperCase(), target_pct: Number(r.target_pct.replace(",", ".")) }));
      await api("/rebalance/targets", { method: "PUT", body });
      setSaveMsg({ ok: true, text: "Alocação-alvo salva." });
      targets.reload();
    } catch (e) {
      setSaveMsg({ ok: false, text: (e as Error).message });
    }
  }

  async function run() {
    setRunError(null);
    try {
      setResult(
        await api<RebalanceResult>("/rebalance", {
          method: "POST",
          body: { contribution: Number(contribution.replace(",", ".")) || 0, mode },
        }),
      );
    } catch (e) {
      setRunError((e as Error).message);
    }
  }

  return (
    <div className="stack">
      <PageHead title="Rebalanceamento" subtitle="Defina a alocação-alvo e descubra quanto comprar de cada ativo no próximo aporte" />
      <div className="grid grid-2">
        <div className="card">
          <div className="chart-head">
            <h2>Alocação-alvo</h2>
            <span className={`small ${Math.abs(total - 100) < 0.01 ? "pos" : "neg"}`}>Soma: {pct(total)}</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Ativo</th>
                <th className="num">% alvo</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>
                    <input className="inline" value={r.ticker} onChange={(e) => update(i, { ticker: e.target.value.toUpperCase() })} size={9} placeholder="TICKER11" />
                  </td>
                  <td className="num">
                    <input className="inline" inputMode="decimal" value={r.target_pct} onChange={(e) => update(i, { target_pct: e.target.value })} size={6} style={{ textAlign: "right" }} />
                  </td>
                  <td className="num">
                    <button className="btn danger sm" onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label="Remover">✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <div className="empty">Nenhum alvo definido.</div>}
          <div className="form-row" style={{ marginTop: 12 }}>
            <button className="btn ghost sm" onClick={() => setRows([...rows, { ticker: "", target_pct: "" }])}>+ Ativo</button>
            <button className="btn ghost sm" onClick={fromPortfolio}>Usar pesos atuais</button>
            <button className="btn ghost sm" onClick={equalWeights}>Pesos iguais</button>
            <button className="btn sm" onClick={save}>Salvar alvo</button>
          </div>
          {saveMsg && <p className={saveMsg.ok ? "pos small" : "error"} style={{ marginTop: 8 }}>{saveMsg.text}</p>}
        </div>

        <div className="card">
          <h2>Simular</h2>
          <div className="form-row">
            <Field label="Valor do aporte (R$)">
              <input inputMode="decimal" value={contribution} onChange={(e) => setContribution(e.target.value)} size={10} />
            </Field>
            <Segmented
              value={mode}
              onChange={setMode}
              options={[
                { value: "aporte", label: "Só comprar" },
                { value: "completo", label: "Comprar e vender" },
              ]}
            />
            <button className="btn" onClick={run}>Calcular</button>
          </div>
          <p className="muted small" style={{ marginTop: 10 }}>
            “Só comprar” direciona o aporte aos ativos mais abaixo do alvo, sem vendas (sem gerar imposto).
            “Comprar e vender” leva a carteira o mais perto possível do alvo — vendas podem gerar IR.
          </p>
          {runError && <p className="error">{runError}</p>}
          {result && (
            <div className="grid grid-kpi" style={{ marginTop: 12 }}>
              <div><div className="muted small">Carteira atual</div><b>{money(result.current_total)}</b></div>
              <div><div className="muted small">Após operações</div><b>{money(result.final_total)}</b></div>
              <div><div className="muted small">Sobra em caixa</div><b>{money(result.cash_left)}</b></div>
            </div>
          )}
        </div>
      </div>

      {result && (
        <div className="card">
          <h2>Ordens sugeridas</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ativo</th>
                  <th className="num">Cotação</th>
                  <th className="num">Atual</th>
                  <th className="num">Alvo</th>
                  <th>Ação</th>
                  <th className="num">Qtd.</th>
                  <th className="num">Valor</th>
                  <th className="num">% final</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.ticker}>
                    <td className="ticker">{r.ticker}</td>
                    <td className="num">{money(r.price)}</td>
                    <td className="num">{pct(r.current_pct)}</td>
                    <td className="num">{pct(r.target_pct)}</td>
                    <td>
                      <span className={`badge ${r.action === "COMPRAR" ? "buy" : r.action === "VENDER" ? "sell" : ""}`}>
                        {r.action === "COMPRAR" ? "▲ " : r.action === "VENDER" ? "▼ " : "● "}
                        {r.action}
                      </span>
                    </td>
                    <td className="num">{number(Math.abs(r.trade_quantity), 0)}</td>
                    <td className="num">{money(Math.abs(r.trade_value))}</td>
                    <td className="num">{pct(r.final_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
