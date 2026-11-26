import type { ReactNode } from "react";
import { money, signedPct, tone } from "../format";

export function Kpi({ label, value, sub, subTone }: { label: string; value: ReactNode; sub?: ReactNode; subTone?: string }) {
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub != null && <div className={`sub ${subTone ?? "muted"}`}>{sub}</div>}
    </div>
  );
}

export function MoneyDelta({ value, pct }: { value: number; pct?: number | null }) {
  return (
    <span className={tone(value)}>
      {value > 0 ? "+" : ""}
      {money(value)}
      {pct != null && ` (${signedPct(pct)})`}
    </span>
  );
}

export function RecBadge({ rec }: { rec: string }) {
  const cls = rec.startsWith("COMPRA") ? "buy" : rec.startsWith("VENDA") ? "sell" : "";
  const icon = rec.startsWith("COMPRA") ? "▲" : rec.startsWith("VENDA") ? "▼" : "●";
  return (
    <span className={`badge ${cls}`}>
      <span aria-hidden>{icon}</span>
      {rec}
    </span>
  );
}

export function DirectionBadge({ direction }: { direction: "BUY" | "SELL" | "NEUTRAL" }) {
  const map = { BUY: ["buy", "▲ Compra"], SELL: ["sell", "▼ Venda"], NEUTRAL: ["", "● Neutro"] } as const;
  const [cls, label] = map[direction];
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function PageHead({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {children && <div className="form-row">{children}</div>}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      {label}
      {children}
    </label>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="segmented" role="group">
      {options.map((o) => (
        <button key={o.value} type="button" className={o.value === value ? "on" : ""} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ProviderNotice({ provider }: { provider?: string }) {
  if (provider !== "demo") return null;
  return (
    <div className="notice">
      Modo demonstração: cotações e proventos são <b>simulados</b>. Configure <code>BRAPI_TOKEN</code> no backend para
      usar dados reais da B3.
    </div>
  );
}

export function Disclaimer() {
  return (
    <p className="disclaimer">
      As informações e sinais exibidos são ferramentas de apoio e não constituem recomendação de investimento.
      Rentabilidade passada não garante rentabilidade futura. Confira cálculos de imposto com um contador.
    </p>
  );
}
