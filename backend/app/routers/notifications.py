from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Notification, User
from ..security import current_user
from ..services.alerts_engine import deliver
from ..services.notify import channels_available

router = APIRouter(prefix="/api", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    message: str
    read: bool
    channels: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        # SQLite não guarda fuso: os horários são gravados em UTC
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


class SettingsIn(BaseModel):
    telegram_chat_id: str | None = Field(default=None, max_length=64, pattern=r"^-?\d*$")
    notify_email: bool = False


@router.get("/notifications")
def list_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(100)
    )
    unread = db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))
    )
    return {"unread": unread or 0, "items": [NotificationOut.model_validate(n) for n in items]}


@router.post("/notifications/read-all", status_code=204)
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(read=True))
    db.commit()


@router.delete("/notifications/{note_id}", status_code=204)
def delete_notification(note_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = db.get(Notification, note_id)
    if not note or note.user_id != user.id:
        raise HTTPException(404, "Notificação não encontrada")
    db.delete(note)
    db.commit()


def _settings_out(user: User) -> dict:
    s = get_settings()
    return {
        "telegram_chat_id": user.telegram_chat_id,
        "notify_email": user.notify_email,
        "email": user.email,
        "channels_available": channels_available(s),
        "alert_check_minutes": s.alert_check_minutes,
        "alert_market_hours_only": s.alert_market_hours_only,
    }


@router.get("/settings")
def get_user_settings(user: User = Depends(current_user)):
    return _settings_out(user)


@router.put("/settings")
def update_user_settings(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.telegram_chat_id = body.telegram_chat_id or None
    user.notify_email = body.notify_email
    db.commit()
    return _settings_out(user)


@router.post("/settings/test-notification")
async def test_notification(user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = await deliver(get_settings(), db, user, "Notificação de teste: seus canais estão configurados.")
    db.commit()
    return {"channels": note.channels.split(",")}
