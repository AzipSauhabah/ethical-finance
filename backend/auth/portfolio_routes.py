"""
backend/auth/portfolio_routes.py
Routes protégées — portfolio utilisateur et historique signaux.
Toutes nécessitent un JWT valide via Depends(get_current_user).
"""

from datetime import date
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.jwt import UserOut, get_current_user

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ─── Schemas ──────────────────────────────────────────────────────────────────
class PositionIn(BaseModel):
    ticker: str
    qty: float
    avg_price: float
    currency: str = "EUR"
    notes: Optional[str] = None


class PositionOut(PositionIn):
    id: str
    opened_at: str


class SignalHistoryOut(BaseModel):
    ticker: str
    date: str
    strategy_id: str
    signal_buy: bool
    signal_sell: bool
    composite_score: Optional[float]


# ─── Positions ────────────────────────────────────────────────────────────────
@router.get("/positions")
async def get_positions(
    request=None,
    current_user: UserOut = Depends(get_current_user),
):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, ticker, qty, avg_price, currency, notes,
                      opened_at::text
               FROM user_portfolios
               WHERE user_id = $1
               ORDER BY opened_at DESC""",
            current_user.user_id,
        )
    return [dict(r) for r in rows]


@router.post("/positions", status_code=201)
async def add_position(
    body: PositionIn,
    request=None,
    current_user: UserOut = Depends(get_current_user),
):
    pool = request.app.state.pool
    pos_id = str(uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO user_portfolios (id, user_id, ticker, qty, avg_price, currency, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            pos_id,
            current_user.user_id,
            body.ticker.upper(),
            body.qty,
            body.avg_price,
            body.currency,
            body.notes,
        )
    return {"id": pos_id, "status": "created"}


@router.delete("/positions/{position_id}")
async def delete_position(
    position_id: str,
    request=None,
    current_user: UserOut = Depends(get_current_user),
):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM user_portfolios WHERE id = $1 AND user_id = $2",
            position_id,
            current_user.user_id,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Position introuvable")
    return {"status": "deleted"}


# ─── Historique signaux ───────────────────────────────────────────────────────
@router.get("/signals/history")
async def get_signals_history(
    ticker: Optional[str] = None,
    strategy_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 90,
    request=None,
    current_user: UserOut = Depends(get_current_user),
):
    pool = request.app.state.pool
    filters = ["1=1"]
    params = []

    if ticker:
        params.append(ticker.upper())
        filters.append(f"ticker = ${len(params)}")
    if strategy_id:
        params.append(strategy_id)
        filters.append(f"strategy_id = ${len(params)}")
    if from_date:
        params.append(from_date)
        filters.append(f"date >= ${len(params)}")
    if to_date:
        params.append(to_date)
        filters.append(f"date <= ${len(params)}")

    params.append(limit)
    query = f"""
        SELECT ticker, date::text, strategy_id, signal_buy, signal_sell,
               composite_score
        FROM signals_history
        WHERE {' AND '.join(filters)}
        ORDER BY date DESC, ticker
        LIMIT ${len(params)}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]
