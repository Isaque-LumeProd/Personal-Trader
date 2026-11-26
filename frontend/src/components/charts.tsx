import type { ReactNode } from "react";

export const AXIS = { stroke: "var(--axis)", tick: { fill: "var(--text-2)", fontSize: 12 }, tickLine: false } as const;
export const GRID = { stroke: "var(--grid)", strokeDasharray: "0", vertical: false } as const;

export interface TipRow {
  label: string;
  value: string;
  color?: string;
}

/** Conteúdo de tooltip padronizado (texto sempre com as cores de texto). */
export function Tip({ title, rows }: { title: ReactNode; rows: TipRow[] }) {
  return (
    <div className="tooltip">
      <div className="t-title">{title}</div>
      {rows.map((r) => (
        <div className="t-row" key={r.label}>
          <span>
            {r.color && <i style={{ background: r.color }} />} {r.label}
          </span>
          <b>{r.value}</b>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string; kind?: "line" | "box" | "dash" }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.label}>
          <i
            className={i.kind === "box" ? "box" : undefined}
            style={
              i.kind === "dash"
                ? { background: `repeating-linear-gradient(90deg, ${i.color} 0 4px, transparent 4px 7px)` }
                : { background: i.color }
            }
          />
          {i.label}
        </span>
      ))}
    </div>
  );
}

export function AllocationBars({ items, format }: { items: { label: string; value: number; pct: number }[]; format: (v: number) => string }) {
  if (!items.length) return <div className="empty">Sem posições</div>;
  const max = Math.max(...items.map((i) => i.pct));
  return (
    <div className="alloc">
      {items.map((i) => (
        <div className="alloc-row" key={i.label} title={`${i.label}: ${format(i.value)}`}>
          <span>{i.label}</span>
          <div className="alloc-track">
            <div className="alloc-fill" style={{ width: `${(100 * i.pct) / max}%` }} />
          </div>
          <span className="num">{i.pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%</span>
        </div>
      ))}
    </div>
  );
}
