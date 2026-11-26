import { useState, type FormEvent } from "react";
import { api, type Dividend } from "../api";
import { Field, PageHead } from "../components/ui";
import { date, money, number, today } from "../format";
import { useApi } from "../hooks";

const KINDS = { RENDIMENTO: "Rendimento", DIVIDENDO: "Dividendo", JCP: "JCP", AMORTIZACAO: "Amortização" } as const;

export default function Dividends() {
  const { data, error, reload } = useApi<Dividend[]>("/dividends");
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ ticker: "", kind: "RENDIMENTO", payment_date: today(), quantity: "", per_share: "" });
  const [formError, setFormError] = useState<string | null>(null);

  async function sync() {
    setBusy(true);
    setSyncMsg(null);
    try {
      const r = await api<{ created: number; errors: Record<string, string> }>("/dividends/sync", { method: "POST" });
      const errs = Object.keys(r.errors);
      setSyncMsg(
        `${r.created} provento(s) importado(s).` + (errs.length ? ` Sem dados para: ${errs.join(", ")}.` : ""),
      );
      reload();
    } catch (e) {
      setSyncMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await api("/dividends", {
        method: "POST",
        body: {
          ...form,
          ticker: form.ticker.toUpperCase(),
          quantity: Number(form.quantity.replace(",", ".")),
          per_share: Number(form.per_share.replace(",", ".")),
        },
      });
      setForm({ ...form, ticker: "", quantity: "", per_share: "" });
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  async function remove(d: Dividend) {
    if (!confirm(`Excluir provento de ${d.ticker} (${money(d.amount)})?`)) return;
    await api(`/dividends/${d.id}`, { method: "DELETE" });
    reload();
  }

  const todayIso = today();
  const received = (data ?? []).filter((d) => d.payment_date <= todayIso).reduce((s, d) => s + d.amount, 0);
  const upcoming = (data ?? []).filter((d) => d.payment_date > todayIso).reduce((s, d) => s + d.amount, 0);

  return (
    <div className="stack">
      <PageHead title="Proventos" subtitle={`Recebido: ${money(received)} · A receber: ${money(upcoming)}`}>
        <button className="btn" onClick={sync} disabled={busy}>
          {busy ? "Sincronizando…" : "↻ Sincronizar proventos"}
        </button>
      </PageHead>
      <p className="muted small" style={{ marginTop: -12 }}>
        A sincronização calcula seus proventos a partir da sua posição em cada <b>data com</b>, usando os anúncios do provedor de dados.
      </p>
      {syncMsg && <div className="notice info">{syncMsg}</div>}

      <form className="card" onSubmit={add}>
        <h2>Lançar provento manualmente</h2>
        <div className="form-row">
          <Field label="Ativo">
            <input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} required size={9} />
          </Field>
          <Field label="Tipo">
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              {Object.entries(KINDS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </Field>
          <Field label="Pagamento">
            <input type="date" value={form.payment_date} onChange={(e) => setForm({ ...form, payment_date: e.target.value })} required />
          </Field>
          <Field label="Quantidade">
            <input inputMode="decimal" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required size={8} />
          </Field>
          <Field label="Valor por cota (R$)">
            <input inputMode="decimal" value={form.per_share} onChange={(e) => setForm({ ...form, per_share: e.target.value })} required size={8} />
          </Field>
          <button className="btn">Adicionar</button>
        </div>
        {formError && <p className="error" style={{ marginTop: 10 }}>{formError}</p>}
      </form>

      <div className="card">
        <h2>Histórico de proventos</h2>
        {error && <p className="error">{error}</p>}
        {!data?.length ? (
          <div className="empty">Nenhum provento registrado.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Pagamento</th>
                  <th>Data com</th>
                  <th>Ativo</th>
                  <th>Tipo</th>
                  <th className="num">Qtd.</th>
                  <th className="num">Por cota</th>
                  <th className="num">Total</th>
                  <th>Origem</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.map((d) => (
                  <tr key={d.id}>
                    <td>
                      {date(d.payment_date)} {d.payment_date > todayIso && <span className="badge info">a receber</span>}
                    </td>
                    <td className="muted">{date(d.ex_date)}</td>
                    <td className="ticker">{d.ticker}</td>
                    <td>{KINDS[d.kind as keyof typeof KINDS] ?? d.kind}</td>
                    <td className="num">{number(d.quantity, 4)}</td>
                    <td className="num">R$ {number(d.per_share, 4)}</td>
                    <td className="num">{money(d.amount)}</td>
                    <td className="muted small">{d.source === "auto" ? "Automático" : "Manual"}</td>
                    <td className="num">
                      <button className="btn danger sm" onClick={() => remove(d)}>Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
