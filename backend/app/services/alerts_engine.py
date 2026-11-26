"""Avaliação de alertas, registro de notificações e envio pelos canais do usuário."""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import Alert, Notification, User
from .fmt import br
from .market import MarketService
from .metrics import asset_metrics
from .notify import send_email, send_telegram

log = logging.getLogger(__name__)
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def evaluate(kind: str, threshold: float | None, m: dict) -> tuple[bool, float | None, str]:
    price, rsi, dy, rec = m["price"], m["rsi14"], m["dy_12m"], m["recommendation"]
    t = m["ticker"]
    if kind == "PRICE_ABOVE":
        return price >= threshold, price, f"{t} a R$ {br(price)} (alvo ≥ R$ {br(threshold)})"
    if kind == "PRICE_BELOW":
        return price <= threshold, price, f"{t} a R$ {br(price)} (alvo ≤ R$ {br(threshold)})"
    if kind == "RSI_ABOVE":
        return rsi is not None and rsi >= threshold, rsi, f"RSI de {t} em {br(rsi or 0, 0)} (alvo ≥ {br(threshold, 0)})"
    if kind == "RSI_BELOW":
        return rsi is not None and rsi <= threshold, rsi, f"RSI de {t} em {br(rsi or 0, 0)} (alvo ≤ {br(threshold, 0)})"
    if kind == "DY_ABOVE":
        return dy is not None and dy >= threshold, dy, f"DY 12m de {t} em {br(dy or 0)}% (alvo ≥ {br(threshold)}%)"
    if kind == "SIGNAL_BUY":
        return rec.startswith("COMPRA"), m["signal_score"], f"Sinal técnico de {t}: {rec}"
    if kind == "SIGNAL_SELL":
        return rec.startswith("VENDA"), m["signal_score"], f"Sinal técnico de {t}: {rec}"
    return False, None, ""


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def deliver(settings: Settings, db: Session, user: User, message: str, alert_id: int | None = None) -> Notification:
    channels = ["app"]
    if user.telegram_chat_id and await send_telegram(settings, user.telegram_chat_id, f"⚑ Personal Trader\n{message}"):
        channels.append("telegram")
    if user.notify_email and await send_email(
        settings, user.email, f"Alerta: {message[:80]}", f"{message}\n\nAbra o app: {settings.app_url}"
    ):
        channels.append("email")
    note = Notification(user_id=user.id, alert_id=alert_id, message=message, channels=",".join(channels))
    db.add(note)
    return note


async def check_alerts(
    db: Session, market: MarketService, user_id: int | None = None, settings: Settings | None = None
) -> tuple[list[dict], dict[str, str]]:
    """Avalia alertas ativos (de um usuário ou de todos) e notifica os disparados fora do cooldown."""
    settings = settings or get_settings()
    stmt = select(Alert).where(Alert.active.is_(True))
    if user_id is not None:
        stmt = stmt.where(Alert.user_id == user_id)
    alerts = list(db.scalars(stmt))
    data, errors = await market.get_many([a.ticker for a in alerts])
    now = datetime.now(timezone.utc)
    cooldown = timedelta(hours=settings.alert_cooldown_hours)
    users: dict[int, User] = {}
    results = []
    for a in alerts:
        if a.ticker not in data:
            continue
        triggered, value, message = evaluate(a.kind, a.threshold, asset_metrics(data[a.ticker]))
        notified = False
        if triggered and (a.last_triggered_at is None or now - _as_aware(a.last_triggered_at) >= cooldown):
            user = users.get(a.user_id) or db.get(User, a.user_id)
            if user:
                users[a.user_id] = user
                await deliver(settings, db, user, message, a.id)
                a.last_triggered_at = now
                notified = True
        results.append(
            {
                "alert_id": a.id,
                "user_id": a.user_id,
                "ticker": a.ticker,
                "kind": a.kind,
                "triggered": triggered,
                "notified": notified,
                "value": value,
                "message": message,
            }
        )
    db.commit()
    return results, errors


def market_open(now: datetime | None = None) -> bool:
    local = (now or datetime.now(timezone.utc)).astimezone(SAO_PAULO)
    return local.weekday() < 5 and time(10, 0) <= local.time() <= time(18, 30)


async def alert_loop(session_factory, market_factory, settings: Settings) -> None:
    """Loop de verificação periódica; roda dentro do processo da API."""
    interval = settings.alert_check_minutes * 60
    while True:
        await asyncio.sleep(interval)
        if settings.alert_market_hours_only and not market_open():
            continue
        try:
            with session_factory() as db:
                results, _ = await check_alerts(db, market_factory(), settings=settings)
            sent = sum(r["notified"] for r in results)
            if sent:
                log.info("alertas: %s notificação(ões) enviada(s)", sent)
        except Exception:  # noqa: BLE001 - o loop não pode morrer
            log.exception("falha na verificação periódica de alertas")
