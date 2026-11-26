from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Transaction, User
from .services.portfolio import TxInput


def user_transactions(db: Session, user: User) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.date, Transaction.id)
    return list(db.scalars(stmt))


def to_inputs(rows: list[Transaction]) -> list[TxInput]:
    return [TxInput(r.ticker, r.asset_type, r.side, r.date, r.quantity, r.price, r.fees or 0.0, r.id) for r in rows]
