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
        return pd.read_json(cached_df)

    df = pd.DataFrame()
    for chunk in _ticker_chunks(tickers):
        part = await _fetch_prices_raw(chunk, start, end)
        df = part if df.empty else df.join(part, how="outer")

    await cache.set(cache_key, df.to_json(), PRICE_CACHE_TTL)
    return df


async def get_live_quote(ticker: str) -> dict:
    """Return latest quote derived from OHLCV data (yf.info unreliable)."""
    cache_key = f"live:{ticker}"
    hit = await cache.get(cache_key)
    if hit:
        return hit

    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            partial(
                yf.download, ticker, period="5d", interval="1d", auto_adjust=True, progress=False
            ),
        )
        if df.empty:
            raise ValueError("empty")

        # Aplatit les colonnes MultiIndex si nécessaire
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else last
        vol = int(df["Volume"].iloc[-1])
        chg = (last - prev) / prev * 100 if prev else 0.0
        high = float(df["High"].iloc[-1])
        low = float(df["Low"].iloc[-1])

        # Bid/Ask estimés depuis High/Low du jour
        bid = round(low, 2)
        ask = round(high, 2)

        info = await loop.run_in_executor(None, partial(_yf_info_sync, ticker))
        currency = info.get("currency", "USD")

    except Exception:
        last, bid, ask, vol, chg, currency = 0.0, 0.0, 0.0, 0, 0.0, "USD"

    quote = {
        "ticker": ticker,
        "last": round(last, 2),
        "bid": bid,
        "ask": ask,
        "volume": vol,
        "change_pct": round(chg, 4),
        "timestamp": pd.Timestamp.utcnow().isoformat(),
        "currency": currency,
    }
    await cache.set(cache_key, quote, LIVE_PRICE_CACHE_TTL)
    return quote


async def get_fx_rate(from_ccy: str = "USD", to_ccy: str = "EUR") -> float:
    """Fetch latest FX rate *from_ccy* → *to_ccy* via yfinance."""
    if from_ccy == to_ccy:
        return 1.0
    key = f"fx:{from_ccy}{to_ccy}"
    hit = await cache.get(key)
    if hit:
        return float(hit)
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, partial(_yf_info_sync, f"{from_ccy}{to_ccy}=X"))
    rate = float(info.get("regularMarketPrice", 1.0) or 1.0)
    await cache.set(key, rate, 300)  # 5 min TTL for FX
    return rate


async def _fetch_fundamentals_db(ticker: str) -> dict | None:
    """Fetch fundamentals from Supabase DB."""
    import os
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None
    try:
        import psycopg2
        sync_url = db_url.replace("postgresql+psycopg2://", "postgresql://").replace("postgres://", "postgresql://")
        conn = psycopg2.connect(sync_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT name, sector, industry, country, currency, exchange,
                   market_cap, beta, dividend_yield, total_debt, total_revenue
            FROM ticker_fundamentals WHERE ticker = %s
        """, (ticker,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "ticker": ticker,
                "name": row[0] or ticker,
                "sector": row[1] or "",
                "industry": row[2] or "",
                "country": row[3] or "",
                "currency": row[4] or "USD",
                "exchange": row[5] or "",
                "market_cap": int(row[6] or 0),
                "beta": float(row[7] or 1.0),
                "dividend_yield": float(row[8] or 0.0),
                "total_debt": int(row[9] or 0),
                "total_revenue": int(row[10] or 0),
                "interest_expense": 0,
                "esg_scores": {},
            }
    except Exception as e:
        log.warning("DB fundamentals failed for %s: %s", ticker, e)
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
