import { useState } from "react";
import type { TaxAnnual, TaxMonthly } from "../api";
import { Disclaimer, Kpi, PageHead } from "../components/ui";
import { date, money, monthLabel, number, pct, tone, TYPE_LABEL } from "../format";
import { useApi } from "../hooks";

const CAT_LABEL = { FII: "FIIs (20%)", ETF: "ETFs (15%)", ETF_DT: "ETFs day trade (20%)" } as const;

export default function Tax() {
  const monthly = useApi<TaxMonthly>("/tax/monthly");
  const [year, setYear] = useState(new Date().getFullYear() - 1);
  const annual = useApi<TaxAnnual>(`/tax/annual?year=${year}`);
  const m = monthly.data;
  const nextDarf = m?.months.find((x) => x.darf_value > 0 && x.darf_due_date && x.darf_due_date >= new Date().toISOString().slice(0, 10));

  return (
    <div className="stack">
      <PageHead title="Imposto de Renda" subtitle="Apuração mensal de ganho de capital (operações comuns e day trade) e apoio à declaração anual" />
      {monthly.error && <div className="error">{monthly.error}</div>}
      {m && (
        <>
          <div className="grid grid-kpi">
            <Kpi
              label="Próximo DARF"
              value={nextDarf ? money(nextDarf.darf_value) : "—"}
              sub={nextDarf ? `Vence em ${date(nextDarf.darf_due_date)} · código 6015` : "Nada a pagar"}
            />
            <Kpi label="Prejuízo a compensar — FIIs" value={money(m.accumulated_losses.FII)} />
            <Kpi
              label="Prejuízo a compensar — ETFs"
              value={money(m.accumulated_losses.ETF)}
              sub={m.accumulated_losses.ETF_DT ? `Day trade: ${money(m.accumulated_losses.ETF_DT)}` : undefined}
            />
            <Kpi label="IR abaixo de R$ 10 acumulado" value={money(m.pending_below_minimum)} sub="Pago junto ao próximo DARF" />
          </div>

          <div className="card">
            <h2>Apuração mensal</h2>
            {m.months.length === 0 ? (
              <div className="empty">Nenhuma venda registrada — sem imposto sobre ganho de capital.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Mês</th>
                      <th>Categoria</th>
                      <th className="num">Vendas</th>
                      <th className="num">Resultado</th>
                      <th className="num">Prejuízo compensado</th>
                      <th className="num">Base de cálculo</th>
                      <th className="num">IR devido</th>
                      <th className="num">IRRF</th>
                      <th className="num">Prejuízo acumulado</th>
                      <th className="num">DARF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {m.months.flatMap((month) =>
                      month.categories.map((c, i) => (
                        <tr key={`${month.month}-${c.category}`}>
                          <td>{i === 0 && <b>{monthLabel(month.month)}</b>}</td>
                          <td>
                            {CAT_LABEL[c.category]}
                            {c.category === "FII" && c.day_trade_result !== 0 && (
                              <div className="muted small">inclui day trade: {money(c.day_trade_result)}</div>
                            )}
                          </td>
                          <td className="num">{money(c.gross_sales)}</td>
                          <td className={`num ${tone(c.result)}`}>{money(c.result)}</td>
                          <td className="num">{money(c.loss_compensated)}</td>
                          <td className="num">{money(c.taxable)}</td>
                          <td className="num">{money(c.tax_due)}</td>
                          <td className="num">{money(c.irrf)}</td>
                          <td className="num">{money(c.loss_carried)}</td>
                          <td className="num">
                            {i === 0 &&
                              (month.darf_value > 0 ? (
                                <>
                                  <b>{money(month.darf_value)}</b>
                                  <div className="muted small">vence {date(month.darf_due_date)}</div>
                                </>
                              ) : month.pending_below_minimum > 0 ? (
                                <span className="muted small">acumulado (&lt; R$ 10)</span>
                              ) : (
                                "—"
                              ))}
                          </td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </div>
            )}
            <ul className="muted small" style={{ marginTop: 12, paddingLeft: 18 }}>
              <li>FIIs: 20% sobre o lucro; prejuízos de FIIs só compensam lucros de FIIs. Rendimentos mensais de FIIs são isentos para pessoa física (regras de enquadramento aplicáveis).</li>
              <li>ETFs de renda variável: 15% sobre o lucro, sem a isenção de R$ 20 mil das ações.</li>
              <li>ETFs de renda fixa têm IR retido na fonte pelo administrador e não entram no DARF.</li>
              <li>Day trade (compra e venda do mesmo ativo no mesmo dia): 20%. Em ETFs, o prejuízo de day trade só compensa lucro de day trade.</li>
              <li>IRRF dedutível: 0,005% sobre as vendas comuns e 1% sobre o lucro de day trade. Alíquotas configuráveis no backend.</li>
            </ul>
          </div>
        </>
      )}

      <div className="card">
        <div className="chart-head">
          <h2>Declaração anual (IRPF)</h2>
          <select className="inline" value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i).map((y) => (
              <option key={y} value={y}>Ano-calendário {y}</option>
            ))}
          </select>
        </div>
        {annual.data && (
          <div className="stack">
            <div>
              <h2 className="small muted" style={{ fontWeight: 600 }}>Bens e Direitos — grupo 07 (Fundos)</h2>
              {annual.data.assets.length === 0 ? (
                <p className="muted">Nenhuma posição no período.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Ativo</th>
                        <th>Discriminação sugerida</th>
                        <th className="num">31/12/{year - 1}</th>
                        <th className="num">31/12/{year}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {annual.data.assets.map((a) => (
                        <tr key={a.ticker}>
                          <td>
                            <span className="ticker">{a.ticker}</span> <span className="badge">{TYPE_LABEL[a.asset_type]}</span>
                          </td>
                          <td className="small">{a.description}</td>
                          <td className="num">{money(a.value_previous_year)}</td>
                          <td className="num">{money(a.value_current_year)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="grid grid-2">
              <div>
                <h2 className="small muted" style={{ fontWeight: 600 }}>Proventos recebidos no ano</h2>
                {annual.data.income.length === 0 ? (
                  <p className="muted">Nenhum provento registrado.</p>
                ) : (
                  <table>
                    <tbody>
                      {annual.data.income.map((i) => (
                        <tr key={`${i.ticker}-${i.kind}`}>
                          <td className="ticker">{i.ticker}</td>
                          <td className="muted small">{i.kind}</td>
                          <td className="num">{money(i.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              <div>
                <h2 className="small muted" style={{ fontWeight: 600 }}>Vendas no ano</h2>
                <p>
                  {number(annual.data.sales.count, 0)} venda(s) · total {money(annual.data.sales.gross)} · resultado{" "}
                  <span className={tone(annual.data.sales.result)}>{money(annual.data.sales.result)}</span>
                </p>
                <p className="muted small">
                  Informe ganhos e perdas mês a mês em “Renda Variável — Operações Comuns” (ETFs) e “Operações de Fundos de
                  Investimento Imobiliário” (FIIs). Taxa de IRRF: {pct(0.005, 3)}.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
      <Disclaimer />
    </div>
  );
}
