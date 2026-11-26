import { useState, type FormEvent } from "react";
import { api, type CorporateEvent } from "../api";
import { date, number, today } from "../format";
import { useApi } from "../hooks";
import { Field } from "./ui";

export default function CorporateEvents({ onChange }: { onChange?: () => void }) {
  const { data, reload } = useApi<CorporateEvent[]>("/events");
  const [form, setForm] = useState({ ticker: "", kind: "SPLIT", date: today(), factor: "" });
  const [error, setError] = useState<string | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/events", {
        method: "POST",
        body: { ...form, ticker: form.ticker.toUpperCase(), factor: Number(form.factor.replace(",", ".")) },
      });
      setForm({ ...form, ticker: "", factor: "" });
      reload();
      onChange?.();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(ev: CorporateEvent) {
    if (!confirm(`Excluir evento de ${ev.ticker}?`)) return;
    try {
      await api(`/events/${ev.id}`, { method: "DELETE" });
      reload();
      onChange?.();
    } catch (err) {
      alert((err as Error).message);
    }
  }

  const f = Number(form.factor.replace(",", ".")) || 0;
  const hint =
    f > 1
      ? form.kind === "SPLIT"
        ? `Cada 1 cota vira ${number(f)}; o preço médio é dividido por ${number(f)}.`
        : `Cada ${number(f)} cotas viram 1; o preço médio é multiplicado por ${number(f)}.`
      : "Informe a proporção (maior que 1).";

  return (
    <div className="card">
      <h2>Desdobramentos e grupamentos</h2>
      <p className="muted small">
        Ajustam a quantidade sem mudar o custo total. Amortizações são lançadas em Proventos (tipo “Amortização”) e reduzem o preço médio.
      </p>
      <form className="form-row" onSubmit={add} style={{ marginTop: 8 }}>
        <Field label="Ativo">
          <input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} required size={9} />
        </Field>
        <Field label="Evento">
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            <option value="SPLIT">Desdobramento (1 → N)</option>
            <option value="REVERSE_SPLIT">Grupamento (N → 1)</option>
          </select>
        </Field>
        <Field label="Data (ex)">
          <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required />
        </Field>
        <Field label="Proporção (N)">
          <input inputMode="decimal" value={form.factor} onChange={(e) => setForm({ ...form, factor: e.target.value })} required size={6} />
        </Field>
        <button className="btn">Adicionar evento</button>
      </form>
      <p className="muted small" style={{ marginTop: 6 }}>{hint}</p>
      {error && <p className="error">{error}</p>}
      {data && data.length > 0 && (
        <table style={{ marginTop: 8 }}>
          <tbody>
            {data.map((ev) => (
              <tr key={ev.id}>
                <td>{date(ev.date)}</td>
                <td className="ticker">{ev.ticker}</td>
                <td>{ev.kind === "SPLIT" ? `Desdobramento 1:${number(ev.factor)}` : `Grupamento ${number(ev.factor)}:1`}</td>
                <td className="num">
                  <button className="btn danger sm" onClick={() => remove(ev)}>Excluir</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
