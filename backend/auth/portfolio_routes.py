"""
backend/auth/portfolio_routes.py
Routes portfolio — authentification par device_id anonyme (sans JWT).
"""

from typing import Optional
from fastapi import APIRouter, Request
import sqlalchemy as sa
from backend.core.db import engine

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _device_id(request: Request) -> str:
    return request.headers.get("X-Device-ID", "anonymous")


# Positions
@router.get("/positions")
async def get_positions(request: Request):
    did = _device_id(request)
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT ticker, qty, avg_price, currency FROM device_positions WHERE device_id = :did ORDER BY ticker"
        ), {"did": did}).fetchall()
    return [{"ticker": r[0], "qty": r[1], "avg_price": r[2], "currency": r[3]} for r in rows]


@router.post("/positions", status_code=201)
async def save_position(request: Request):
    did = _device_id(request)
    body = await request.json()
    ticker = str(body.get("ticker", "")).upper()
    qty = float(body.get("qty", 0))
    avg_price = float(body.get("avg_price", 0))
    currency = str(body.get("currency", "EUR"))
    if not ticker:
        return {"status": "error", "detail": "ticker required"}
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO device_positions (device_id, ticker, qty, avg_price, currency, updated_at)
            VALUES (:did, :ticker, :qty, :avg, :ccy, now())
            ON CONFLICT (device_id, ticker) DO UPDATE SET
                qty=EXCLUDED.qty, avg_price=EXCLUDED.avg_price,
                currency=EXCLUDED.currency, updated_at=now()
        """), {"did": did, "ticker": ticker, "qty": qty, "avg": avg_price, "ccy": currency})
    return {"status": "ok", "ticker": ticker}


@router.delete("/positions/{ticker}")
async def delete_position(ticker: str, request: Request):
    did = _device_id(request)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "DELETE FROM device_positions WHERE device_id = :did AND ticker = :ticker"
        ), {"did": did, "ticker": ticker.upper()})
    return {"status": "deleted"}
