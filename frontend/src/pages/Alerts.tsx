import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type Alert, type AlertCheck, type AlertKind } from "../api";
import { Field, PageHead } from "../components/ui";
import { date, number } from "../format";
import { useApi } from "../hooks";
import { notifyUnreadChanged } from "../notifications";

const KINDS: Record<AlertKind, { label: string; unit?: string }> = {
  PRICE_ABOVE: { label: "Preço acima de", unit: "R$" },
  PRICE_BELOW: { label: "Preço abaixo de", unit: "R$" },
  DY_ABOVE: { label: "DY 12m acima de", unit: "%" },
  RSI_BELOW: { label: "RSI abaixo de" },
  RSI_ABOVE: { label: "RSI acima de" },
  SIGNAL_BUY: { label: "Sinal técnico de compra" },
  SIGNAL_SELL: { label: "Sinal técnico de venda" },
};

const needsThreshold = (k: AlertKind) => !k.startsWith("SIGNAL");

export default function Alerts() {
  const { data, reload } = useApi<Alert[]>("/alerts");
  const [form, setForm] = useState<{ ticker: string; kind: AlertKind; threshold: string }>({ ticker: "", kind: "PRICE_BELOW", threshold: "" });
  const [error, setError] = useState<string | null>(null);
  const [check, setCheck] = useState<AlertCheck | null>(null);
  const [checking, setChecking] = useState(false);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/alerts", {
        method: "POST",
        body: {
          ticker: form.ticker.toUpperCase(),
          kind: form.kind,
          threshold: needsThreshold(form.kind) ? Number(form.threshold.replace(",", ".")) : null,
        },
      });
      setForm({ ...form, ticker: "", threshold: "" });
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggle(a: Alert) {
    await api(`/alerts/${a.id}`, { method: "PUT", body: { ticker: a.ticker, kind: a.kind, threshold: a.threshold, active: !a.active } });
    reload();
  }

  async function remove(a: Alert) {
    await api(`/alerts/${a.id}`, { method: "DELETE" });
    reload();
  }

  async function runCheck() {
    setChecking(true);
    try {
      setCheck(await api<AlertCheck>("/alerts/check", { method: "POST" }));
      reload();
      notifyUnreadChanged();
    } finally {
      setChecking(false);
    }
  }

  const status = new Map(check?.results.map((r) => [r.alert_id, r]));

  return (
    <div className="stack">
      <PageHead title="Alertas" subtitle="Seja avisado quando um ativo atingir o preço, o yield ou o sinal que você procura">
        <button className="btn" onClick={runCheck} disabled={checking}>
          {checking ? "Verificando…" : "Verificar agora"}
        </button>
      </PageHead>

      <form className="card" onSubmit={add}>
        <h2>Novo alerta</h2>
        <div className="form-row">
          <Field label="Ativo">
            <input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} required size={9} placeholder="MXRF11" />
          </Field>
          <Field label="Condição">
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as AlertKind })}>
              {Object.entries(KINDS).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </Field>
          {needsThreshold(form.kind) && (
            <Field label={`Valor ${KINDS[form.kind].unit ? `(${KINDS[form.kind].unit})` : ""}`}>
              <input inputMode="decimal" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} required size={8} />
            </Field>
          )}
          <button className="btn">Criar alerta</button>
        </div>
        {error && <p className="error" style={{ marginTop: 10 }}>{error}</p>}
      </form>

      <div className="card">
        <h2>Meus alertas</h2>
        {!data?.length ? (
          <div className="empty">Nenhum alerta criado.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ativo</th>
                  <th>Condição</th>
                  <th>Situação</th>
                  <th>Último disparo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.map((a) => {
                  const s = status.get(a.id);
                  const k = KINDS[a.kind];
                  return (
                    <tr key={a.id}>
                      <td className="ticker">{a.ticker}</td>
                      <td>
                        {k.label}
                        {a.threshold != null && ` ${k.unit === "R$" ? "R$ " : ""}${number(a.threshold)}${k.unit === "%" ? "%" : ""}`}
                      </td>
                      <td>
                        {!a.active ? (
                          <span className="badge">Pausado</span>
                        ) : s ? (
                          <span className={`badge ${s.triggered ? "buy" : ""}`} title={s.message}>
                            {s.triggered ? "⚑ Disparado" : "Aguardando"}
                          </span>
                        ) : (
                          <span className="badge">Ativo</span>
                        )}
                        {s && <div className="muted small">{s.message}</div>}
                      </td>
                      <td className="muted">{a.last_triggered_at ? date(a.last_triggered_at) : "—"}</td>
                      <td className="num">
                        <button className="btn ghost sm" onClick={() => toggle(a)}>{a.active ? "Pausar" : "Ativar"}</button>{" "}
                        <button className="btn danger sm" onClick={() => remove(a)}>Excluir</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted small" style={{ marginTop: 12 }}>
          Os alertas são verificados automaticamente durante o pregão, ao abrir a Carteira ou em “Verificar agora”.
          Cada alerta avisa no máximo uma vez por dia — configure Telegram ou e-mail em <Link to="/configuracoes">Configurações</Link>.
        </p>
      </div>
    </div>
  );
}
