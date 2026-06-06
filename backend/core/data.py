"""
:file: api/core/data.py
:brief: Price & fundamental data fetching.
        Source priority: yfinance → Stooq → GBM synthetic.
        All public functions are async; heavy IO runs in a thread pool.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Generator, Iterator
from datetime import date, timedelta
from functools import partial

import numpy as np
import pandas as pd

from backend.config import (
    DATA_SOURCES,
    DEFAULT_PERIOD,
    LIVE_PRICE_CACHE_TTL,
    MAX_PERIOD_YEARS,
    PRICE_CACHE_TTL,
)
from backend.core.cache import cache

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _period_to_start(period: str) -> date:
    """Convert '5y', '10y', '1y', '6mo' … to a start date."""
    today = date.today()
    period = period.strip().lower()
    if period.endswith("y"):
        years = int(period[:-1])
        years = min(years, MAX_PERIOD_YEARS)
        return today.replace(year=today.year - years)
    if period.endswith("mo"):
        months = int(period[:-2])
        y, m = divmod(today.month - months - 1, 12)
        return today.replace(year=today.year + y, month=m + 1)
    return today - timedelta(days=365)


def _ticker_chunks(tickers: list[str], size: int = 50) -> Generator[list[str], None, None]:
    """Yield successive chunks of *tickers* for batched downloads."""
    for i in range(0, len(tickers), size):
        yield tickers[i : i + size]


# ─────────────────────────────────────────────────────────────────────────────
# yfinance backend (sync, run in executor)
# ─────────────────────────────────────────────────────────────────────────────


async def _fetch_prices_postgres(
    tickers: list[str],
    start: date,
    end: date,
    use_adjusted: bool = True,
) -> pd.DataFrame:
    """Lit les prix depuis PostgreSQL ohlcv.

    use_adjusted=True  → adj_close (dividendes réinvestis)
    use_adjusted=False → close (prix brut, dividendes en cash)
    """
    import os

    import sqlalchemy as sa

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return pd.DataFrame()

    price_col = "adj_close" if use_adjusted else "close"
    sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        loop = asyncio.get_event_loop()

        def _query():
            with engine.connect() as conn:
                rows = conn.execute(
                    sa.text(f"""
                    SELECT ticker, date, {price_col}
                    FROM ohlcv
                    WHERE ticker = ANY(:tickers)
                      AND date >= :start
                      AND date <= :end
                      AND {price_col} IS NOT NULL
                    ORDER BY date ASC
                """),
                    {"tickers": tickers, "start": start, "end": end},
                ).fetchall()
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=["ticker", "date", price_col])
            df["date"] = pd.to_datetime(df["date"])
            return df.pivot(index="date", columns="ticker", values="adj_close")

        return await loop.run_in_executor(None, _query)
    except Exception as e:
        log.warning("_fetch_prices_postgres error: %s", e)
        return pd.DataFrame()


async def get_prices(
    tickers: list[str],
    period: str = DEFAULT_PERIOD,
    start: date | None = None,
    end: date | None = None,
    use_adjusted: bool = True,
) -> pd.DataFrame:
    """Return adjusted close prices for *tickers* over the requested period.

    :param period: e.g. ``'5y'``, ``'10y'``, ``'6mo'``
    :param start: overrides *period* if supplied
    :param end:   defaults to today
    :returns: DataFrame[date, ticker] of adjusted closes
    """
    end = end or date.today()
    start = start or _period_to_start(period)

    cache_key = f"prices:{':'.join(sorted(tickers))}:{start}:{end}"
    cached_df = await cache.get(cache_key)
    if cached_df is not None:
        import io

        return pd.read_json(io.StringIO(cached_df))

    # 1. PostgreSQL local en priorité absolue
    df = await _fetch_prices_postgres(tickers, start, end, use_adjusted=use_adjusted)

    # 2. Fallback yfinance uniquement si aucune donnée en base
    if df.empty:
        log.warning("get_prices: aucune donnée en base pour %s — fallback yfinance", tickers)
        for chunk in _ticker_chunks(tickers):
            part = await _fetch_prices_raw(chunk, start, end)
            df = part if df.empty else df.join(part, how="outer")

    await cache.set(cache_key, df.to_json(), PRICE_CACHE_TTL)
    return df


def _build_empty_quote(ticker: str) -> dict:
    """Return an empty quote dict."""
    return {
        "ticker": ticker, "last": 0.0, "bid": 0.0, "ask": 0.0,
        "volume": 0, "change_pct": 0.0,
        "timestamp": pd.Timestamp.utcnow().isoformat(), "currency": "USD",
    }


def _build_quote_from_rows(ticker: str, rows) -> dict:
    """Build quote dict from DB rows."""
    last_row = rows[0]
    price = float(last_row[1] or last_row[2] or 0)
    prev_price = float(rows[1][1] or rows[1][2] or price) if len(rows) > 1 else price
    change_pct = ((price - prev_price) / prev_price * 100) if prev_price else 0.0
    return {
        "ticker": ticker, "last": price, "bid": price, "ask": price,
        "volume": int(last_row[3] or 0),
        "change_pct": round(change_pct, 2),
        "timestamp": pd.Timestamp.utcnow().isoformat(), "currency": "USD",
    }


async def get_live_quote(ticker: str) -> dict:
    """Return latest quote from local PostgreSQL ohlcv table."""
    import asyncio

    import sqlalchemy as sa

    from backend.core.db import engine

    cache_key = f"live:{ticker}"
    hit = await cache.get(cache_key)
    if hit:
        return hit

    empty = _build_empty_quote(ticker)

    def _fetch():
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            return session.execute(
                sa.text("SELECT date, adj_close, close, volume FROM ohlcv WHERE ticker = :ticker ORDER BY date DESC LIMIT 2"),
                {"ticker": ticker},
            ).fetchall()

    try:
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _fetch)
        if not rows:
            return empty
        result = _build_quote_from_rows(ticker, rows)
        await cache.set(cache_key, result, ttl=300)
        return result
    except Exception as exc:
        log.warning("DB live quote error %s: %s", ticker, exc)
        return empty


async def get_fx_rate(from_ccy: str = "USD", to_ccy: str = "EUR") -> float:
    """Fetch latest FX rate from local PostgreSQL ohlcv table."""
    import asyncio
    import sqlalchemy as sa
    from backend.core.db import engine

    if from_ccy == to_ccy:
        return 1.0
    key = f"fx:{from_ccy}{to_ccy}"
    hit = await cache.get(key)
    if hit:
        return float(hit)

    rate = 1.0
    try:
        ticker = f"{from_ccy}{to_ccy}=X"
        loop = asyncio.get_event_loop()
        def _query():
            with engine.connect() as conn:
                row = conn.execute(
                    sa.text("SELECT adj_close FROM ohlcv WHERE ticker = :t ORDER BY date DESC LIMIT 1"),
                    {"t": ticker},
                ).fetchone()
            return float(row[0]) if row and row[0] else 1.0
        rate = await loop.run_in_executor(None, _query)
    except Exception as e:
        log.warning("FX rate from DB failed %s/%s: %s", from_ccy, to_ccy, e)

    await cache.set(key, rate, 3600)
    return rate


async def _fetch_fundamentals_db(ticker: str) -> dict | None:
    """Fetch fundamentals depuis PostgreSQL local — source principale."""
    import os

    import sqlalchemy as sa

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return None

    sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        loop = asyncio.get_event_loop()

        def _query():
            with engine.connect() as conn:
                row = conn.execute(
                    sa.text("""
                    SELECT ticker, name, sector, industry, country, currency, exchange,
                           market_cap, beta, dividend_yield, total_debt, total_revenue,
                           revenue_segments, total_cash, haram_revenue_ratio, sharia_debt_ratio,
                           interest_expense, interest_income,
                           interest_bearing_debt, short_term_debt,
                           long_term_debt, total_assets, total_equity,
                           net_margin, fcf_yield
                    FROM ticker_fundamentals
                    WHERE ticker = :ticker
                    LIMIT 1
                """),
                    {"ticker": ticker},
                ).fetchone()
            return row

        row = await loop.run_in_executor(None, _query)
        if not row:
            return None

        return {
            "ticker": row[0],
            "name": row[1] or ticker,
            "sector": row[2] or "",
            "industry": row[3] or "",
            "country": row[4] or "",
            "currency": row[5] or "USD",
            "exchange": row[6] or "",
            "market_cap": int(row[7] or 0),
            "beta": float(row[8] or 1.0),
            "dividend_yield": float(row[9] or 0.0),
            "total_debt": int(row[10] or 0),
            "total_revenue": int(row[11] or 0),
            "revenue_segments": dict(row[12]) if row[12] else None,
            "total_cash":            int(row[13] or 0),
            "interest_expense":      int(row[14] or 0),
            "interest_income":       int(row[15] or 0),
            "interest_bearing_debt": int(row[16] or 0),
            "short_term_debt":       int(row[17] or 0),
            "long_term_debt":        int(row[18] or 0),
            "total_assets":          int(row[19] or 0),
            "total_equity":          int(row[20] or 0),
            "haram_revenue_ratio":   float(row[14]) if row[14] is not None else None,
            "sharia_debt_ratio":     float(row[15]) if row[15] is not None else None,
            "net_margin":            float(row[23]) if row[23] is not None else None,
            "fcf_yield":             float(row[24]) if row[24] is not None else None,
            "esg_scores": {},
        }
    except Exception as e:
        import logging

        logging.getLogger("api").warning("PG fundamentals failed for %s: %s", ticker, e)
    return None


async def get_ticker_fundamentals(ticker: str) -> dict:
    """Return key fundamental data used for ethical screening and metrics."""
    cache_key = f"fund:{ticker}"
    hit = await cache.get(cache_key)
    if hit:
        return hit
    data = await _fetch_fundamentals_db(ticker)
    if not data:
        log.warning("get_ticker_fundamentals: %s absent de la base locale", ticker)
        data = {"ticker": ticker, "name": ticker, "sector": "", "industry": "",
                "market_cap": 0, "total_debt": 0, "total_revenue": 0,
                "interest_expense": 0, "esg_scores": {}, "currency": "USD",
                "exchange": "", "country": "", "dividend_yield": 0.0, "beta": 1.0}
    await cache.set(cache_key, data, 86_400)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Generator utility — lazy daily return iterator
# ─────────────────────────────────────────────────────────────────────────────


def daily_returns_iter(prices: pd.Series) -> Iterator[tuple[date, float]]:
    """Lazy generator yielding (date, daily_return) pairs.

    :param prices: time-indexed price series
    """
    prev: float | None = None
    for idx, p in prices.items():
        if prev is not None and prev != 0:
            yield idx, (p - prev) / prev
        prev = p
