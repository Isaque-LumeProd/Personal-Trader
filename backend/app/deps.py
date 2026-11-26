from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CorporateEvent, Dividend, Transaction, User
from .services.portfolio import EventInput, Ledger, TxInput, build_ledger


def user_transactions(db: Session, user: User) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.date, Transaction.id)
    return list(db.scalars(stmt))


def to_inputs(rows: list[Transaction]) -> list[TxInput]:
    return [TxInput(r.ticker, r.asset_type, r.side, r.date, r.quantity, r.price, r.fees or 0.0, r.id) for r in rows]


def user_events(db: Session, user: User) -> list[EventInput]:
    """Desdobramentos/grupamentos cadastrados + amortizações registradas como provento."""
    events = [
        EventInput(e.ticker, e.date, e.kind, factor=e.factor)
        for e in db.scalars(select(CorporateEvent).where(CorporateEvent.user_id == user.id))
    ]
    amortizations = db.scalars(
        select(Dividend).where(Dividend.user_id == user.id, Dividend.kind == "AMORTIZACAO")
    )
    events += [EventInput(d.ticker, d.ex_date or d.payment_date, "AMORTIZATION", amount=d.amount) for d in amortizations]
    return events


def user_ledger(db: Session, user: User, until=None) -> Ledger:
    return build_ledger(to_inputs(user_transactions(db, user)), user_events(db, user), until=until)
