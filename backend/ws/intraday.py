"""
backend/ws/intraday.py
WebSocket intraday — pousse le prix live toutes les N secondes.

Sources (par priorité) :
  1. Twelve Data /price  (plan gratuit, ~8 req/min)
  2. Dernier prix ohlcv en base (fallback)

Usage : ws://host/ws/intraday/{ticker}?interval=10
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
import sqlalchemy as sa
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()

TWELVE_BASE = "https://api.twelvedata.com"


def _normalize_ticker(ticker: str) -> tuple[str, str]:
    """Convertit ticker yfinance → Twelve Data format."""
    EXCHANGE_MAP = {
        ".PA": ("", "XPAR"),
        ".L": ("", "XLON"),
        ".DE": ("", "XETR"),
        ".AS": ("", "XAMS"),
        ".SW": ("", "XSWX"),
        ".ST": ("", "XSTO"),
        ".OL": ("", "XOSL"),
        ".CO": ("", "XCSE"),
        ".T": ("", "XTKS"),
        ".AX": ("", "XASX"),
        ".JO": ("", "XJSE"),
    }
    for suffix, (_, exchange) in EXCHANGE_MAP.items():
        if ticker.endswith(suffix):
            return ticker.replace(suffix, ""), exchange
    # Indices / FX
    if ticker.startswith("^"):
        return ticker[1:], ""
    if ticker.endswith("=X"):
        return ticker.replace("=X", ""), "FOREX"
    return ticker, ""


async def _fetch_twelve_price(ticker: str, api_key: str) -> float | None:
    """Fetch prix live depuis Twelve Data /price."""
    sym, exchange = _normalize_ticker(ticker)
    params = {"symbol": sym, "apikey": api_key}
    if exchange and exchange not in ("FOREX",):
        params["exchange"] = exchange

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{TWELVE_BASE}/price", params=params)
            data = r.json()
            if "price" in data:
                return float(data["price"])
    except Exception as e:
        log.debug("Twelve Data price error %s: %s", ticker, e)
    return None


async def _fetch_db_price(ticker: str) -> dict | None:
    """Dernier prix depuis PostgreSQL ohlcv — fallback."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return None

    sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        loop = asyncio.get_event_loop()

        def _query():
            with engine.connect() as conn:
                rows = conn.execute(
                    sa.text("""
                    SELECT date, adj_close, close, volume
                    FROM ohlcv
                    WHERE ticker = :ticker
                      AND adj_close IS NOT NULL
                    ORDER BY date DESC
                    LIMIT 2
                """),
                    {"ticker": ticker},
                ).fetchall()
            return rows

        rows = await loop.run_in_executor(None, _query)
        if not rows:
            return None

        last = rows[0]
        prev = rows[1] if len(rows) > 1 else rows[0]
        price = float(last[1] or last[2] or 0)
        prev_price = float(prev[1] or prev[2] or price)
        change_pct = ((price - prev_price) / prev_price * 100) if prev_price else 0.0

        return {
            "price": price,
            "change_pct": round(change_pct, 3),
            "volume": int(last[3] or 0),
            "date": str(last[0]),
            "source": "db",
        }
    except Exception as e:
        log.warning("DB price error %s: %s", ticker, e)
        return None


@router.websocket("/ws/intraday/{ticker}")
async def intraday_ws(websocket: WebSocket, ticker: str, interval: int = 10):
    """
    WebSocket live intraday.

    Envoie un message JSON toutes les `interval` secondes :
    {
        "ticker": "AAPL",
        "price": 185.42,
        "change_pct": 0.34,
        "volume": 12345678,
        "timestamp": "2026-05-18T14:32:00Z",
        "source": "twelve_data" | "db"
    }
    """
    await websocket.accept()
    ticker = ticker.upper()
    api_key = os.environ.get("TWELVE_DATA_API_KEY", "")

    log.info("WS intraday opened: %s (interval=%ds)", ticker, interval)

    # Prix de référence pour le calcul de variation
    ref_price: float | None = None

    try:
        while True:
            timestamp = datetime.now(timezone.utc).isoformat()
            price = None
            source = "db"

            # 1. Twelve Data si clé disponible
            if api_key:
                price = await _fetch_twelve_price(ticker, api_key)
                if price:
                    source = "twelve_data"

            # 2. Fallback DB
            if not price:
                db_data = await _fetch_db_price(ticker)
                if db_data:
                    price = db_data["price"]
                    source = db_data["source"]

            if price is None:
                await websocket.send_json(
                    {
                        "ticker": ticker,
                        "error": "Prix non disponible",
                        "timestamp": timestamp,
                    }
                )
            else:
                if ref_price is None:
                    ref_price = price

                change_pct = ((price - ref_price) / ref_price * 100) if ref_price else 0.0

                # Récupère volume depuis DB
                db_data = await _fetch_db_price(ticker)
                volume = db_data["volume"] if db_data else 0

                await websocket.send_json(
                    {
                        "ticker": ticker,
                        "price": round(price, 4),
                        "change_pct": round(change_pct, 3),
                        "change_abs": round(price - ref_price, 4),
                        "volume": volume,
                        "timestamp": timestamp,
                        "source": source,
                    }
                )

            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        log.info("WS intraday closed: %s", ticker)
    except Exception as e:
        log.warning("WS intraday error %s: %s", ticker, e)
        try:
            await websocket.close()
        except Exception:
            pass
