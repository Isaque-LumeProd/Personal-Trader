import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type AssetType, type ImportPreview, type ImportRow } from "../api";
import { PageHead } from "../components/ui";
import { date, money, number, TYPE_LABEL } from "../format";

const FORMAT_LABEL = {
  b3_negociacao: "Extrato de Negociação da B3",
  b3_movimentacao: "Extrato de Movimentação da B3 (proventos)",
  modelo: "Planilha no modelo do Personal Trader",
};

const STATUS: Record<ImportRow["status"], { label: string; cls: string }> = {
  ok: { label: "Novo", cls: "buy" },
  duplicate: { label: "Já cadastrado", cls: "" },
  ignored: { label: "Ignorado", cls: "" },
  error: { label: "Erro", cls: "sell" },
};

const TEMPLATE = "ticker;operacao;data;quantidade;preco;taxas;classe\nHGLG11;compra;15/01/2025;10;158,50;4,90;FII\nBOVA11;venda;20/02/2025;5;130,00;2,50;ETF\n";

export default function Import() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [types, setTypes] = useState<Record<number, AssetType>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function upload(f: File) {
    setFile(f);
    setBusy(true);
    setError(null);
    setDone(null);
    setPreview(null);
    try {
      const form = new FormData();
      form.append("file", f);
      const p = await api<ImportPreview>("/import/preview", { method: "POST", body: form });
      setPreview(p);
      setSelected(new Set(p.rows.filter((r) => r.status === "ok").map((r) => r.line)));
      setTypes({});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const importable = useMemo(() => preview?.rows.filter((r) => r.status === "ok") ?? [], [preview]);
  const chosen = importable.filter((r) => selected.has(r.line));

  async function commit() {
    setBusy(true);
    setError(null);
    try {
      const trades = chosen
        .filter((r) => r.kind === "trade")
        .map((r) => ({
          ticker: r.ticker,
          asset_type: types[r.line] ?? r.asset_type ?? "FII",
          side: r.side,
          date: r.date,
          quantity: r.quantity,
          price: r.price,
          fees: r.fees,
        }));
      const dividends = chosen
        .filter((r) => r.kind === "dividend")
        .map((r) => ({ ticker: r.ticker, dividend_kind: r.dividend_kind, date: r.date, quantity: r.quantity, price: r.price, amount: r.amount }));
      const res = await api<{ trades: number; dividends: number }>("/import/commit", { method: "POST", body: { trades, dividends } });
      setDone(`${res.trades} lançamento(s) e ${res.dividends} provento(s) importados.`);
      setPreview(null);
      setFile(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function toggle(line: number) {
    const next = new Set(selected);
    if (next.has(line)) next.delete(line);
    else next.add(line);
    setSelected(next);
  }

  const templateHref = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`;

  return (
    <div className="stack">
      <PageHead title="Importar" subtitle="Traga seu histórico da B3 ou de uma planilha sem digitar lançamento por lançamento" />

      <div className="grid grid-2">
        <div className="card">
          <h2>1. Baixe o extrato</h2>
          <ol className="muted small" style={{ paddingLeft: 18, margin: 0 }}>
            <li>Entre na Área do Investidor da B3 (investidor.b3.com.br).</li>
            <li>
              Em <b>Extratos → Negociação</b>, filtre o período e baixe em Excel — importa compras e vendas.
            </li>
            <li>
              Em <b>Extratos → Movimentação</b>, baixe em Excel — importa rendimentos, dividendos e amortizações.
            </li>
          </ol>
          <p className="muted small" style={{ marginTop: 10 }}>
            Também aceita CSV no modelo próprio (<a href={templateHref} download="modelo-personal-trader.csv">baixar modelo</a>).
            O extrato da B3 não traz corretagem; se quiser, edite as taxas depois em Lançamentos.
          </p>
        </div>
        <div className="card">
          <h2>2. Envie o arquivo</h2>
          <label className="dropzone">
            <input type="file" accept=".xlsx,.csv" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} hidden />
            <span>{busy ? "Lendo arquivo…" : file ? file.name : "Clique para escolher um arquivo .xlsx ou .csv"}</span>
          </label>
          {error && <p className="error" style={{ marginTop: 10 }}>{error}</p>}
          {done && (
            <p className="notice info" style={{ marginTop: 10 }}>
              {done} Veja em <Link to="/">Carteira</Link>.
            </p>
          )}
        </div>
      </div>

      {preview && (
        <div className="card">
          <div className="chart-head">
            <div>
              <h2 style={{ marginBottom: 2 }}>3. Revise e confirme</h2>
              <span className="muted small">
                {FORMAT_LABEL[preview.format]} · {preview.summary.ok ?? 0} novo(s), {preview.summary.duplicate ?? 0} já cadastrado(s),{" "}
                {preview.summary.ignored ?? 0} ignorado(s), {preview.summary.error ?? 0} com erro
              </span>
            </div>
            <button className="btn" onClick={commit} disabled={busy || chosen.length === 0}>
              Importar {chosen.length} linha(s)
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="Selecionar todos"
                      checked={importable.length > 0 && chosen.length === importable.length}
                      onChange={(e) => setSelected(new Set(e.target.checked ? importable.map((r) => r.line) : []))}
                    />
                  </th>
                  <th>Linha</th>
                  <th>Situação</th>
                  <th>Data</th>
                  <th>Tipo</th>
                  <th>Ativo</th>
                  <th>Classe</th>
                  <th className="num">Qtd.</th>
                  <th className="num">Preço / por cota</th>
                  <th className="num">Total</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r) => (
                  <tr key={r.line} style={r.status === "ok" ? undefined : { opacity: 0.6 }}>
                    <td>{r.status === "ok" && <input type="checkbox" checked={selected.has(r.line)} onChange={() => toggle(r.line)} aria-label={`Linha ${r.line}`} />}</td>
                    <td className="muted">{r.line}</td>
                    <td>
                      <span className={`badge ${STATUS[r.status].cls}`}>{STATUS[r.status].label}</span>
                      {r.reason && <div className="muted small">{r.reason}</div>}
                    </td>
                    <td>{date(r.date)}</td>
                    <td>{r.kind === "trade" ? (r.side === "BUY" ? "Compra" : r.side === "SELL" ? "Venda" : "—") : (r.dividend_kind ?? "—").toLowerCase()}</td>
                    <td className="ticker">{r.ticker || "—"}</td>
                    <td>
                      {r.kind === "trade" && r.status === "ok" ? (
                        <select className="inline" value={types[r.line] ?? r.asset_type ?? "FII"} onChange={(e) => setTypes({ ...types, [r.line]: e.target.value as AssetType })}>
                          <option value="FII">FII</option>
                          <option value="ETF">ETF</option>
                          <option value="ETF_RF">ETF RF</option>
                        </select>
                      ) : (
                        r.asset_type && TYPE_LABEL[r.asset_type]
                      )}
                    </td>
                    <td className="num">{number(r.quantity, 4)}</td>
                    <td className="num">{r.kind === "dividend" ? `R$ ${number(r.price, 4)}` : money(r.price)}</td>
                    <td className="num">{money(r.kind === "dividend" ? r.amount : r.quantity * r.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small" style={{ marginTop: 12 }}>
            A classe é sugerida pelo catálogo; ativos desconhecidos com final 11 entram como FII — ajuste se for ETF.
            Se você já tinha cotas antes do período do extrato, importe também o histórico anterior para o preço médio ficar correto.
          </p>
        </div>
      )}
    </div>
  );
}
