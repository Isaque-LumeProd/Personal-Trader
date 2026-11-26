import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api, type AppNotification } from "../api";
import { PageHead } from "../components/ui";
import { useApi } from "../hooks";
import { notifyUnreadChanged } from "../notifications";

const CHANNEL = { app: "App", telegram: "Telegram", email: "E-mail" } as const;

function when(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export default function Notifications() {
  const { data, reload } = useApi<{ unread: number; items: AppNotification[] }>("/notifications");

  useEffect(() => {
    if (data && data.unread > 0) {
      api("/notifications/read-all", { method: "POST" }).then(notifyUnreadChanged);
    }
  }, [data]);

  async function remove(n: AppNotification) {
    await api(`/notifications/${n.id}`, { method: "DELETE" });
    reload();
  }

  return (
    <div className="stack">
      <PageHead title="Notificações" subtitle="Histórico dos alertas disparados">
        <Link className="btn ghost" to="/configuracoes">Canais de aviso</Link>
      </PageHead>
      <div className="card">
        {!data?.items.length ? (
          <div className="empty">
            Nenhuma notificação ainda. Crie alertas em <Link to="/alertas">Alertas</Link>.
          </div>
        ) : (
          <table>
            <tbody>
              {data.items.map((n) => (
                <tr key={n.id}>
                  <td style={{ width: 20 }}>{!n.read && <span className="status-dot" style={{ background: "var(--accent)" }} aria-label="não lida" />}</td>
                  <td>
                    <div style={{ fontWeight: n.read ? 400 : 600 }}>{n.message}</div>
                    <div className="muted small">
                      {when(n.created_at)} · {n.channels.split(",").map((c) => CHANNEL[c as keyof typeof CHANNEL] ?? c).join(", ")}
                    </div>
                  </td>
                  <td className="num">
                    <button className="btn ghost sm" onClick={() => remove(n)} aria-label="Excluir">✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
