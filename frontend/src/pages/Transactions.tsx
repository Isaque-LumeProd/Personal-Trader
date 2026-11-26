import { useState, type FormEvent } from "react";
import { api, type AssetType, type CatalogAsset, type Transaction } from "../api";
import { Field, PageHead } from "../components/ui";
import { date, money, number, today, TYPE_LABEL } from "../format";
import { useApi } from "../hooks";

interface FormState {
  ticker: string;
  asset_type: AssetType | "";
  side: "BUY" | "SELL";
  date: string;
  quantity: string;
  price: string;
  fees: string;
  notes: string;
}

const EMPTY: FormState = { ticker: "", asset_type: "", side: "BUY", date: today(), quantity: "", price: "", fees: "0", notes: "" };

export default function Transactions() {
  const { data, error, reload } = useApi<Transaction[]>("/transactions");
  const catalog = useApi<CatalogAsset[]>("/market/assets");
  const [form, setForm] = useState<FormState>(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  const set = (k: keyof FormState) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  function onTicker(value: string) {
    const ticker = value.toUpperCase();
    const known = catalog.data?.find((a) => a.ticker === ticker);
    setForm({ ...form, ticker, asset_type: known ? known.asset_type : form.asset_type });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    const body = {
      ticker: form.ticker.trim(),
      asset_type: form.asset_type || null,
      side: form.side,
      date: form.date,
      quantity: Number(form.quantity.replace(",", ".")),
      price: Number(form.price.replace(",", ".")),
      fees: Number(form.fees.replace(",", ".") || 0),
      notes: form.notes || null,
    };
    try {
      await api(editing ? `/transactions/${editing}` : "/transactions", { method: editing ? "PUT" : "POST", body });
      setForm({ ...EMPTY, date: form.date });
      setEditing(null);
      reload();
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function edit(t: Transaction) {
    setEditing(t.id);
    setForm({
      ticker: t.ticker,
      asset_type: t.asset_type,
      side: t.side,
      date: t.date,
      quantity: String(t.quantity),
      price: String(t.price),
      fees: String(t.fees),
      notes: t.notes ?? "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function remove(t: Transaction) {
    if (!confirm(`Excluir ${t.side === "BUY" ? "compra" : "venda"} de ${t.quantity} ${t.ticker}?`)) return;
    try {
      await api(`/transactions/${t.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      alert((err as Error).message);
    }
  }

  const rows = (data ?? []).filter((t) => !filter || t.ticker.includes(filter.toUpperCase()));

  return (
    <div className="stack">
      <PageHead title="Lançamentos" subtitle="Compras e vendas — o preço médio inclui corretagem e taxas" />
      <form className="card" onSubmit={submit}>
        <h2>{editing ? "Editar lançamento" : "Novo lançamento"}</h2>
        <div className="form-row">
          <Field label="Operação">
            <select value={form.side} onChange={set("side")}>
              <option value="BUY">Compra</option>
              <option value="SELL">Venda</option>
            </select>
          </Field>
          <Field label="Ativo">
            <input list="catalog" value={form.ticker} onChange={(e) => onTicker(e.target.value)} placeholder="HGLG11" required size={9} pattern="[A-Za-z]{4}[0-9]{1,2}" />
          </Field>
          <datalist id="catalog">
            {catalog.data?.map((a) => (
              <option key={a.ticker} value={a.ticker}>{a.name}</option>
            ))}
          </datalist>
          <Field label="Classe">
            <select value={form.asset_type} onChange={set("asset_type")}>
              <option value="">Automática</option>
              <option value="FII">FII</option>
              <option value="ETF">ETF (renda variável)</option>
              <option value="ETF_RF">ETF (renda fixa)</option>
            </select>
          </Field>
          <Field label="Data">
            <input type="date" value={form.date} onChange={set("date")} required max={today()} />
          </Field>
          <Field label="Quantidade">
            <input inputMode="decimal" value={form.quantity} onChange={set("quantity")} required size={8} />
          </Field>
          <Field label="Preço (R$)">
            <input inputMode="decimal" value={form.price} onChange={set("price")} required size={8} />
          </Field>
          <Field label="Taxas (R$)">
            <input inputMode="decimal" value={form.fees} onChange={set("fees")} size={6} />
          </Field>
          <Field label="Observação">
            <input value={form.notes} onChange={set("notes")} size={14} />
          </Field>
          <button className="btn" disabled={busy}>{editing ? "Salvar" : "Adicionar"}</button>
          {editing && (
            <button type="button" className="btn ghost" onClick={() => { setEditing(null); setForm(EMPTY); }}>
              Cancelar
            </button>
          )}
        </div>
        {formError && <p className="error" style={{ marginTop: 10 }}>{formError}</p>}
      </form>

      <div className="card">
        <div className="chart-head">
          <h2>Histórico</h2>
          <input className="inline" placeholder="Filtrar ativo" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        {error && <p className="error">{error}</p>}
        {rows.length === 0 ? (
          <div className="empty">Nenhum lançamento ainda.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Operação</th>
                  <th>Ativo</th>
                  <th className="num">Qtd.</th>
                  <th className="num">Preço</th>
                  <th className="num">Taxas</th>
                  <th className="num">Total</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td>{date(t.date)}</td>
                    <td>
                      <span className={`badge ${t.side === "BUY" ? "buy" : "sell"}`}>{t.side === "BUY" ? "▲ Compra" : "▼ Venda"}</span>
                    </td>
                    <td>
                      <span className="ticker">{t.ticker}</span> <span className="badge">{TYPE_LABEL[t.asset_type]}</span>
                      {t.notes && <div className="muted small">{t.notes}</div>}
                    </td>
                    <td className="num">{number(t.quantity, 4)}</td>
                    <td className="num">{money(t.price)}</td>
                    <td className="num">{money(t.fees)}</td>
                    <td className="num">{money(t.total)}</td>
                    <td className="num">
                      <button className="btn ghost sm" onClick={() => edit(t)}>Editar</button>{" "}
                      <button className="btn danger sm" onClick={() => remove(t)}>Excluir</button>
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
