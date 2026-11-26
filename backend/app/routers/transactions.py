from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..catalog import guess_asset_type
from ..db import get_db
from ..deps import user_ledger, user_transactions
from ..models import Transaction, User
from ..schemas import TransactionIn, TransactionOut
from ..security import current_user
from ..services.portfolio import PortfolioError

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _out(t: Transaction) -> TransactionOut:
    out = TransactionOut.model_validate(t)
    sign = 1 if t.side == "BUY" else -1
    out.total = round(t.quantity * t.price + sign * (t.fees or 0), 2)
    return out


def _validate_or_rollback(db: Session, user: User) -> None:
    db.flush()
    try:
        user_ledger(db, user)
    except PortfolioError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    db.commit()


def _get_owned(db: Session, user: User, tx_id: int) -> Transaction:
    tx = db.get(Transaction, tx_id)
    if not tx or tx.user_id != user.id:
        raise HTTPException(404, "Lançamento não encontrado")
    return tx


@router.get("", response_model=list[TransactionOut])
def list_transactions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_out(t) for t in reversed(user_transactions(db, user))]


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(body: TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["asset_type"] = data["asset_type"] or guess_asset_type(body.ticker)
    tx = Transaction(user_id=user.id, **data)
    db.add(tx)
    _validate_or_rollback(db, user)
    return _out(tx)


@router.put("/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, body: TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tx = _get_owned(db, user, tx_id)
    data = body.model_dump()
    data["asset_type"] = data["asset_type"] or guess_asset_type(body.ticker)
    for key, value in data.items():
        setattr(tx, key, value)
    _validate_or_rollback(db, user)
    return _out(tx)


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_get_owned(db, user, tx_id))
    _validate_or_rollback(db, user)
