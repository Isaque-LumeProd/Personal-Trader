import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { onUnreadChanged } from "../notifications";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";

const LINKS = [
  { to: "/", label: "Carteira", icon: "◧" },
  { to: "/lancamentos", label: "Lançamentos", icon: "⇄" },
  { to: "/importar", label: "Importar da B3", icon: "⇪" },
  { to: "/proventos", label: "Proventos", icon: "◎" },
  { to: "/screener", label: "Screener", icon: "☰" },
  { to: "/analise", label: "Análise técnica", icon: "∿" },
  { to: "/rebalanceamento", label: "Rebalanceamento", icon: "⚖" },
  { to: "/ir", label: "Imposto de Renda", icon: "§" },
  { to: "/alertas", label: "Alertas", icon: "⚑" },
  { to: "/notificacoes", label: "Notificações", icon: "✉" },
  { to: "/configuracoes", label: "Configurações", icon: "⚙" },
];

export function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill="var(--accent)" />
      <path d="M7 21l6-6 4 4 8-9" fill="none" stroke="var(--accent-ink)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const refreshUnread = useCallback(() => {
    api<{ unread: number }>("/notifications").then((r) => setUnread(r.unread)).catch(() => {});
  }, []);
  useEffect(() => {
    refreshUnread();
    const timer = setInterval(refreshUnread, 60_000);
    const off = onUnreadChanged(refreshUnread);
    return () => {
      clearInterval(timer);
      off();
    };
  }, [refreshUnread]);
  const location = useLocation();
  const [lastPath, setLastPath] = useState(location.pathname);
  if (lastPath !== location.pathname) {
    setLastPath(location.pathname);
    setOpen(false);
  }

  return (
    <>
      <div className="mobile-bar">
        <div className="brand" style={{ padding: 0 }}>
          <Logo /> Personal Trader
        </div>
        <button className="btn ghost sm" onClick={() => setOpen((o) => !o)} aria-label="Menu">
          ☰{unread > 0 && <span className="count" style={{ marginLeft: 6 }}>{unread}</span>}
        </button>
      </div>
      <div className="shell">
        <aside className={`sidebar ${open ? "open" : ""}`}>
          <div className="brand">
            <Logo /> Personal Trader
          </div>
          <nav className="nav">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.to === "/"}>
                <span aria-hidden style={{ width: 18, textAlign: "center" }}>{l.icon}</span>
                {l.label}
                {l.to === "/notificacoes" && unread > 0 && <span className="count">{unread}</span>}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-footer">
            <div style={{ fontWeight: 600 }}>{user?.name}</div>
            <div className="muted" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{user?.email}</div>
            <button className="btn ghost sm" style={{ marginTop: 8 }} onClick={logout}>
              Sair
            </button>
          </div>
        </aside>
        <main className="main">
          <Outlet />
        </main>
      </div>
    </>
  );
}
