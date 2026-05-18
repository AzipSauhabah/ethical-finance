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


def _yf_download_sync(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    try:
        import yfinance as yf  # lazy import

        raw = yf.download(
            tickers=tickers,
            start=str(start),
            end=str(end),
            auto_adjust=True,  # adjusts splits + dividends
            actions=True,
            progress=False,
            threads=True,
        )
        # Normalise multi vs single ticker layout
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw[["Close"]].rename(columns={"Close": tickers[0]})
        return closes.ffill().dropna(how="all")
    except Exception as exc:
        log.warning("yfinance failed for %s: %s", tickers, exc)
        return pd.DataFrame()


def _yf_info_sync(ticker: str) -> dict:
    try:
        import yfinance as yf

        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Stooq backend
# ─────────────────────────────────────────────────────────────────────────────


def _stooq_download_sync(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    try:
        import pandas_datareader as pdr

        frames = {}
        for t in tickers:
            try:
                df = pdr.get_data_stooq(t, start=str(start), end=str(end))
                if not df.empty:
                    frames[t] = df["Close"].sort_index()
            except Exception:
                pass
        if frames:
            return pd.DataFrame(frames).ffill().dropna(how="all")
    except Exception as exc:
        log.warning("Stooq failed: %s", exc)
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# GBM synthetic fallback
# ─────────────────────────────────────────────────────────────────────────────


def _gbm_prices(
    ticker: str,
    n_days: int,
    s0: float = 100.0,
    mu: float = 0.08,
    sigma: float = 0.20,
    seed: int | None = None,
) -> pd.Series:
    """Geometric Brownian Motion path — purely synthetic fallback.

    :param s0:    starting price
    :param mu:    annual drift
    :param sigma: annual volatility
    """
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    daily = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * math.sqrt(dt), n_days)
    prices = s0 * np.exp(np.cumsum(daily))
    idx = pd.bdate_range(end=date.today(), periods=n_days)
    return pd.Series(prices, index=idx, name=ticker)


def _gbm_frame(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    n = len(pd.bdate_range(start, end))
    return pd.DataFrame({t: _gbm_prices(t, n, seed=hash(t) % 2**31) for t in tickers})


# ─────────────────────────────────────────────────────────────────────────────
# Waterfall fetch
# ─────────────────────────────────────────────────────────────────────────────


async def _fetch_prices_raw(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    """Try data sources in priority order, return first non-empty result."""
    loop = asyncio.get_event_loop()

    for source in DATA_SOURCES:
        if source == "yfinance":
            df = await loop.run_in_executor(None, partial(_yf_download_sync, tickers, start, end))
        elif source == "stooq":
            df = await loop.run_in_executor(
                None, partial(_stooq_download_sync, tickers, start, end)
            )
        elif source == "gbm_synthetic":
            df = await loop.run_in_executor(None, partial(_gbm_frame, tickers, start, end))
        else:
            continue

        if not df.empty:
            log.info("Prices fetched via %s for %s", source, tickers)
            return df

    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def _fetch_prices_supabase(tickers, start, end):
    import logging
    import os

    import httpx
    import pandas as pd

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not supabase_key:
        return pd.DataFrame()
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    all_rows = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for ticker in tickers:
                params = {
                    "ticker": f"eq.{ticker}",
                    "date": f"gte.{start.isoformat()}",
                    "select": "date,adj_close,close",
                    "order": "date.asc",
                    "limit": "10000",
                }
                r = await client.get(
                    f"{supabase_url}/rest/v1/ohlcv", headers=headers, params=params
                )
                if r.status_code == 200:
                    for row in r.json():
                        if row.get("date", "") <= end.isoformat():
                            all_rows.append(
                                {
                                    "date": row["date"],
                                    "ticker": ticker,
                                    "close": float(row.get("adj_close") or row.get("close") or 0),
                                }
                            )
    except Exception as e:
        logging.getLogger("api").warning("Supabase prices failed: %s", e)
        return pd.DataFrame()
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.pivot(index="date", columns="ticker", values="close")
    df.columns.name = None
    return df


async def _fetch_prices_postgres(
    tickers: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """Lit les prix adj_close depuis PostgreSQL ohlcv — source principale."""
    import os

    import sqlalchemy as sa

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return pd.DataFrame()

    sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        loop = asyncio.get_event_loop()

        def _query():
            with engine.connect() as conn:
                rows = conn.execute(
                    sa.text("""
                    SELECT ticker, date, adj_close
                    FROM ohlcv
                    WHERE ticker = ANY(:tickers)
                      AND date >= :start
                      AND date <= :end
                      AND adj_close IS NOT NULL
                    ORDER BY date ASC
                """),
                    {"tickers": tickers, "start": start, "end": end},
                ).fetchall()
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=["ticker", "date", "adj_close"])
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
    df = await _fetch_prices_postgres(tickers, start, end)

    # 2. Fallback yfinance uniquement si aucune donnée en base
    if df.empty:
        log.warning("get_prices: aucune donnée en base pour %s — fallback yfinance", tickers)
        for chunk in _ticker_chunks(tickers):
            part = await _fetch_prices_raw(chunk, start, end)
            df = part if df.empty else df.join(part, how="outer")

    await cache.set(cache_key, df.to_json(), PRICE_CACHE_TTL)
    return df


async def get_live_quote(ticker: str) -> dict:
    """Return latest quote from local PostgreSQL ohlcv table."""
    import asyncio

    import sqlalchemy as sa

    from backend.core.db import engine

    cache_key = f"live:{ticker}"
    hit = await cache.get(cache_key)
    if hit:
        return hit

    empty = {
        "ticker": ticker,
        "last": 0.0,
        "bid": 0.0,
        "ask": 0.0,
        "volume": 0,
        "change_pct": 0.0,
        "timestamp": pd.Timestamp.utcnow().isoformat(),
        "currency": "USD",
    }

    def _fetch():
        from sqlalchemy.orm import Session

        with Session(engine) as session:
            rows = session.execute(
                sa.text("""
                    SELECT date, adj_close, close, volume
                    FROM ohlcv
                    WHERE ticker = :ticker
                    ORDER BY date DESC
                    LIMIT 2
                """),
                {"ticker": ticker},
            ).fetchall()
        return rows

    try:
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _fetch)
        if not rows:
            return empty
        last_row = rows[0]
        price = float(last_row[1] or last_row[2] or 0)
        prev_price = float(rows[1][1] or rows[1][2] or price) if len(rows) > 1 else price
        change_pct = ((price - prev_price) / prev_price * 100) if prev_price else 0.0
        result = {
            "ticker": ticker,
            "last": price,
            "bid": price,
            "ask": price,
            "volume": int(last_row[3] or 0),
            "change_pct": round(change_pct, 2),
            "timestamp": pd.Timestamp.utcnow().isoformat(),
            "currency": "USD",
        }
        await cache.set(cache_key, result, ttl=300)
        return result
    except Exception as exc:
        log.warning("DB live quote error %s: %s", ticker, exc)
        return empty

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")

    if not supabase_url or not supabase_key:
        return empty

    try:
        url = f"{supabase_url}/rest/v1/ohlcv"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }
        params = {
            "ticker": f"eq.{ticker}",
            "select": "date,close,high,low,volume,adj_close",
            "order": "date.desc",
            "limit": "2",
        }
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url, headers=headers, params=params)
            if r.status_code != 200 or not r.json():
                return empty
            rows = r.json()
            last_row = rows[0]
            prev_row = rows[1] if len(rows) > 1 else last_row

            last = float(last_row.get("adj_close") or last_row.get("close") or 0)
            prev = float(prev_row.get("adj_close") or prev_row.get("close") or last)
            chg = (last - prev) / prev * 100 if prev else 0.0
            bid = float(last_row.get("low") or last)
            ask = float(last_row.get("high") or last)
            vol = int(last_row.get("volume") or 0)

            quote = {
                "ticker": ticker,
                "last": round(last, 2),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "volume": vol,
                "change_pct": round(chg, 4),
                "timestamp": pd.Timestamp.utcnow().isoformat(),
                "currency": "USD",
            }
            await cache.set(cache_key, quote, LIVE_PRICE_CACHE_TTL)
            return quote
    except Exception as e:
        log.warning("Live quote from DB failed for %s: %s", ticker, e)
        return empty


async def get_fx_rate(from_ccy: str = "USD", to_ccy: str = "EUR") -> float:
    """Fetch latest FX rate from Supabase ohlcv DB."""
    import os

    import httpx

    if from_ccy == to_ccy:
        return 1.0
    key = f"fx:{from_ccy}{to_ccy}"
    hit = await cache.get(key)
    if hit:
        return float(hit)

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    rate = 1.0

    if supabase_url and supabase_key:
        try:
            ticker = f"{from_ccy}{to_ccy}=X"
            headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
            params = {
                "ticker": f"eq.{ticker}",
                "select": "close",
                "order": "date.desc",
                "limit": "1",
            }
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    f"{supabase_url}/rest/v1/ohlcv", headers=headers, params=params
                )
                if r.status_code == 200 and r.json():
                    rate = float(r.json()[0].get("close") or 1.0)
        except Exception as e:
            log.warning("FX rate from DB failed: %s", e)

    await cache.set(key, rate, 3600)
    return rate


async def _fetch_fundamentals_db(ticker: str) -> dict | None:
    """Fetch fundamentals from Supabase REST API."""
    import os

    import httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not supabase_key:
        return None

    try:
        url = f"{supabase_url}/rest/v1/ticker_fundamentals"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }
        params = {"ticker": f"eq.{ticker}", "select": "*", "limit": "1"}
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url, headers=headers, params=params)
            if r.status_code != 200 or not r.json():
                return None
            row = r.json()[0]
            return {
                "ticker": ticker,
                "name": row.get("name") or ticker,
                "sector": row.get("sector") or "",
                "industry": row.get("industry") or "",
                "country": row.get("country") or "",
                "currency": row.get("currency") or "USD",
                "exchange": row.get("exchange") or "",
                "market_cap": int(row.get("market_cap") or 0),
                "beta": float(row.get("beta") or 1.0),
                "dividend_yield": float(row.get("dividend_yield") or 0.0),
                "total_debt": int(row.get("total_debt") or 0),
                "total_revenue": int(row.get("total_revenue") or 0),
                "interest_expense": 0,
                "esg_scores": {},
            }
    except Exception as e:
        import logging

        logging.getLogger("api").warning("DB fundamentals failed for %s: %s", ticker, e)
    return None


async def _fetch_fundamentals_httpx(ticker: str) -> dict:
    """Fetch fundamentals via Yahoo Finance API with rotating User-Agents."""
    import random

    import httpx

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    ]

    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
    params = {"modules": "summaryDetail,assetProfile,defaultKeyStatistics,financialData"}
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    empty = {
        "ticker": ticker,
        "name": ticker,
        "sector": "",
        "industry": "",
        "market_cap": 0,
        "total_debt": 0,
        "total_revenue": 0,
        "interest_expense": 0,
        "esg_scores": {},
        "currency": "USD",
        "exchange": "",
        "country": "",
        "dividend_yield": 0.0,
        "beta": 1.0,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                return empty
            js = r.json()
            result = js.get("quoteSummary", {}).get("result", [{}])[0] or {}
            sd = result.get("summaryDetail", {})
            ap = result.get("assetProfile", {})
            ks = result.get("defaultKeyStatistics", {})
            fd = result.get("financialData", {})

            def val(d, k):
                v = d.get(k, 0)
                return v.get("raw", 0) if isinstance(v, dict) else (v or 0)

            return {
                "ticker": ticker,
                "name": ap.get("longName", ap.get("shortName", ticker)),
                "sector": ap.get("sector", ""),
                "industry": ap.get("industry", ""),
                "market_cap": val(sd, "marketCap") or val(ks, "marketCap"),
                "total_debt": val(fd, "totalDebt"),
                "total_revenue": val(fd, "totalRevenue"),
                "interest_expense": val(fd, "interestExpense"),
                "esg_scores": {},
                "currency": sd.get("currency", "USD"),
                "exchange": ap.get("exchange", ""),
                "country": ap.get("country", ""),
                "dividend_yield": val(sd, "dividendYield"),
                "beta": val(sd, "beta") or val(ks, "beta") or 1.0,
            }
    except Exception as e:
        log.warning("Fundamentals fetch failed for %s: %s", ticker, e)
        return empty


async def get_ticker_fundamentals(ticker: str) -> dict:
    """Return key fundamental data used for ethical screening and metrics."""
    cache_key = f"fund:{ticker}"
    hit = await cache.get(cache_key)
    if hit:
        return hit
    # Essaie d'abord la DB Supabase
    data = await _fetch_fundamentals_db(ticker)
    if not data:
        # Fallback vers httpx
        data = await _fetch_fundamentals_httpx(ticker)
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
