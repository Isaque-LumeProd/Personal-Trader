import { useEffect, useState } from "react";
import { api, type UserSettings } from "../api";
import { Field, PageHead } from "../components/ui";
import { useApi } from "../hooks";
import { notifyUnreadChanged } from "../notifications";

export default function Settings() {
  const { data, setData } = useApi<UserSettings>("/settings");
  const [chatId, setChatId] = useState("");
  const [email, setEmail] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (data) {
      setChatId(data.telegram_chat_id ?? "");
      setEmail(data.notify_email);
    }
  }, [data]);

  async function save() {
    setMsg(null);
    try {
      setData(await api<UserSettings>("/settings", { method: "PUT", body: { telegram_chat_id: chatId.trim() || null, notify_email: email } }));
      setMsg({ ok: true, text: "Preferências salvas." });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  async function test() {
    setMsg(null);
    try {
      const r = await api<{ channels: string[] }>("/settings/test-notification", { method: "POST" });
      notifyUnreadChanged();
      setMsg({ ok: true, text: `Notificação de teste enviada por: ${r.channels.join(", ")}.` });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  if (!data) return null;
  const av = data.channels_available;

  return (
    <div className="stack">
      <PageHead title="Configurações" subtitle="Como você quer ser avisado quando um alerta disparar" />
      <div className="card stack" style={{ maxWidth: 720 }}>
        <div>
          <h2>Verificação automática</h2>
          <p className="muted small">
            {data.alert_check_minutes > 0
              ? `Seus alertas são verificados a cada ${data.alert_check_minutes} minutos${data.alert_market_hours_only ? ", em dias úteis das 10h às 18h30" : ""}. Cada alerta avisa no máximo uma vez por dia.`
              : "A verificação automática está desativada no servidor; use “Verificar agora” na tela de Alertas."}
          </p>
        </div>

        <div>
          <h2>Telegram</h2>
          {!av.telegram && <p className="notice">O servidor ainda não tem um bot configurado (TELEGRAM_BOT_TOKEN).</p>}
          <p className="muted small">
            Envie uma mensagem para o bot do Personal Trader e informe aqui o seu <i>chat id</i> (o @userinfobot mostra o seu).
          </p>
          <Field label="Chat id do Telegram">
            <input value={chatId} onChange={(e) => setChatId(e.target.value)} inputMode="numeric" placeholder="123456789" style={{ maxWidth: 240 }} />
          </Field>
        </div>

        <div>
          <h2>E-mail</h2>
          {!av.email && <p className="notice">O servidor ainda não tem SMTP configurado.</p>}
          <label className="check-row">
            <input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} />
            Enviar alertas para {data.email}
          </label>
        </div>

        <div className="form-row">
          <button className="btn" onClick={save}>Salvar</button>
          <button className="btn ghost" onClick={test}>Enviar notificação de teste</button>
        </div>
        {msg && <p className={msg.ok ? "pos small" : "error"}>{msg.text}</p>}
      </div>
    </div>
  );
}
