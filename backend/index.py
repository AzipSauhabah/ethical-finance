"""
:file: api/index.py
:brief: FastAPI thin layer — routes only.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

from fastapi import HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app import app

# ─── DB URL constants ────────────────────────────────────────────────────────
_PG_SCHEME = "postgresql://"
_PG_PSYCOPG2_SCHEME = "postgresql+psycopg2://"
from backend.ws.intraday import router as ws_router

app.include_router(ws_router)
from backend.backtest.engine import BacktestEngine
from backend.config import (
    API_VERSION,
    BENCHMARKS,
    COPYRIGHT,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_PERIOD,
    DISCLAIMER,
)
from backend.core.data import get_fx_rate, get_live_quote, get_prices
from backend.core.queue import subscribe, unsubscribe, watch
from backend.core.registry import registry, ticker_to_dict
from backend.quant.montecarlo import run_simulation
from backend.report.pdf import generate_pdf
from backend.report.tearsheet import build_tearsheet
from backend.signals.daily import compute_daily_signals
from backend.signals.rebalance import compute_rebalance_orders
from backend.strategies.base import StrategyParams
from backend.strategies.custom import build_custom_strategy
from backend.strategies.registry import strategy_registry

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

strategy_registry.auto_discover()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class TickerListIn(BaseModel):
    tickers: list[str]


class BacktestIn(BaseModel):
    tickers: list[str]
    strategy: str
    period: str = DEFAULT_PERIOD
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    monthly_contribution: float = 0.0
    broker: str = "default"
    account_type: str = "CTO"
    rebalance_frequency: str = "monthly"
    max_position_pct: float = 0.25
    stop_loss_pct: float | None = 0.10
    benchmark: str = "^GSPC"
    custom_params: dict = Field(default_factory=dict)
    require_ethical: bool = False
    allow_fractional: bool = False  # Revolut uniquement
    use_adjusted_close: bool = True  # True = dividendes réinvestis
    require_sharia: bool = False
    use_var_constraint: bool = False


class CustomStrategyIn(BaseModel):
    name: str
    description: str = ""
    rules: list[dict]
    combination: str = "majority"
    benchmark: str = "^GSPC"


class RebalanceIn(BaseModel):
    positions: dict[str, dict]
    target_weights: dict[str, float]
    cash_eur: float
    broker: str = "default"


class MonteCarloIn(BaseModel):
    ticker: str
    period: str = DEFAULT_PERIOD
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    n_paths: int = 5_000
    n_days: int = 252
    method: str = "gbm"


class ScreenerIn(BaseModel):
    method: str = "magic_formula"  # magic_formula | momentum | low_vol | ml | combined
    top_n: int = 20
    require_ethical: bool = False
    allow_fractional: bool = False  # Revolut uniquement
    use_adjusted_close: bool = True  # True = dividendes réinvestis
    require_sharia: bool = False
    min_market_cap: float = 1e9
    universe: str = "all"


# ─── Health & meta ───────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": API_VERSION, "strategies": len(strategy_registry)}


@app.get("/api/meta")
async def meta():
    return {
        "version": API_VERSION,
        "copyright": COPYRIGHT,
        "disclaimer": DISCLAIMER,
        "benchmarks": BENCHMARKS,
    }


# ─── Tickers & screening ─────────────────────────────────────────────────────


@app.post("/api/tickers/screen")
async def screen_tickers(payload: TickerListIn):
    records = await registry.load_many(payload.tickers)
    watch(payload.tickers)
    return {"tickers": [ticker_to_dict(r) for r in records]}



@app.get("/api/tickers/search")
async def search_tickers(q: str = Query("", min_length=1)):
    """Search tickers by symbol or name from the database."""
    import sqlalchemy as sa
    import os
    database_url = os.environ.get("DATABASE_URL", "")
    sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)
    loop = asyncio.get_event_loop()

    def _search():
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(sa.text("""
                SELECT ticker, name, sector, universe
                FROM ticker_fundamentals
                WHERE ticker ILIKE :q OR name ILIKE :q
                ORDER BY market_cap DESC NULLS LAST
                LIMIT 20
            """), {"q": f"%{q}%"}).fetchall()
        return [{"ticker": r[0], "name": r[1], "sector": r[2], "universe": r[3]} for r in rows]

    results = await loop.run_in_executor(None, _search)
    return {"results": results}


@app.get("/api/tickers/{ticker}/screening")
async def screening_detail(ticker: str):
    """Detailed breakdown for one ticker."""
    rec = await registry.load(ticker.upper())
    return ticker_to_dict(rec)


@app.post("/api/portfolio/analytics")
async def portfolio_analytics(payload: dict):
    """Portfolio Analytics — Sharpe, Sortino, corrélations, risk contribution."""
    from backend.core.portfolio_analytics import compute_portfolio_analytics
    from backend.core.db import engine
    positions = payload.get("positions", {})
    days = payload.get("days", 365)
    return compute_portfolio_analytics(positions, engine, days)


@app.get("/api/tickers/{ticker}/buffett")
async def buffett_detail(ticker: str):
    """Buffett Score — ROE / Dette / FCF Yield / Moat."""
    from backend.core.buffett import compute_buffett_score
    from backend.core.data import get_ticker_fundamentals
    info = await get_ticker_fundamentals(ticker.upper())
    mc = float(info.get("market_cap") or 0) or None
    return compute_buffett_score(info, mc)


@app.get("/api/quote/{ticker}")
async def quote(ticker: str):
    return await get_live_quote(ticker.upper())


@app.get("/api/quote/stream/{ticker}")
async def quote_stream(ticker: str):
    aq = subscribe(ticker.upper())

    async def gen():
        try:
            initial = await get_live_quote(ticker.upper())
            yield f"data: {json.dumps(initial)}\n\n"
            while True:
                try:
                    q = await asyncio.wait_for(aq.get(), timeout=120)
                    yield f"data: {json.dumps(q)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unsubscribe(ticker.upper(), aq)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/prices/intraday")
async def prices_intraday(ticker: str = Query(...), hours: int = Query(48)):
    """Lit les données OHLCV 1h depuis ohlcv_intraday — pour Elliott Wave intraday."""
    import os
    from datetime import datetime, timedelta, timezone

    import sqlalchemy as sa

    database_url = os.environ.get("DATABASE_URL", "")
    sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)
    engine = sa.create_engine(sync_url, pool_pre_ping=True)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("""
            SELECT datetime::text, open, high, low, close, volume
            FROM ohlcv_intraday
            WHERE ticker = :ticker AND datetime >= :since AND interval = '1h'
            ORDER BY datetime ASC
        """),
            {"ticker": ticker.upper(), "since": since},
        ).fetchall()

    data = [
        {
            "datetime": r[0],
            "open": float(r[1] or 0),
            "high": float(r[2] or 0),
            "low": float(r[3] or 0),
            "close": float(r[4] or 0),
            "volume": int(r[5] or 0),
        }
        for r in rows
    ]
    return {
        "ticker": ticker.upper(),
        "interval": "1h",
        "hours": hours,
        "data": data,
        "count": len(data),
    }


@app.get("/api/prices/db")
async def prices_from_db(tickers: str = Query(...), period: str = Query("6mo")):
    """Lit les prix OHLCV directement depuis PostgreSQL — rapide, pas de yfinance."""
    import os
    from datetime import date, timedelta

    import sqlalchemy as sa

    PERIODS = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
    days = PERIODS.get(period, 180)
    start = date.today() - timedelta(days=days)
    ts = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    database_url = os.environ.get("DATABASE_URL", "")
    sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)
    engine = sa.create_engine(sync_url, pool_pre_ping=True)

    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("""
            SELECT ticker, date::text, adj_close
            FROM ohlcv
            WHERE ticker = ANY(:tickers)
              AND date >= :start
              AND adj_close IS NOT NULL
            ORDER BY date ASC
        """),
            {"tickers": ts, "start": start},
        ).fetchall()

    # Pivot : [{date, AAPL, MSFT, ...}]
    from collections import defaultdict

    by_date: dict = defaultdict(dict)
    for ticker, dt, close in rows:
        by_date[dt][ticker] = float(close)

    data = [{"date": dt, **vals} for dt, vals in sorted(by_date.items())]
    return {"tickers": ts, "period": period, "data": data}


@app.get("/api/prices")
async def prices(tickers: str = Query(...), period: str = Query(DEFAULT_PERIOD)):
    ts = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    df = await get_prices(ts, period=period)
    import math

    return {
        "tickers": ts,
        "period": period,
        "data": [
            {
                "date": str(idx.date()),
                **{
                    c: (
                        None
                        if (isinstance(row[c], float) and math.isnan(row[c]))
                        else float(row[c])
                    )
                    for c in df.columns
                },
            }
            for idx, row in df.iterrows()
        ],
    }


# ─── Strategies ──────────────────────────────────────────────────────────────


@app.get("/api/strategies")
async def list_strategies():
    return {"strategies": strategy_registry.list_all()}


@app.post("/api/strategies/custom")
async def create_custom_strategy(payload: CustomStrategyIn):
    inst = build_custom_strategy(payload.dict())
    return {"name": inst.name, "description": inst.description, "registered": True}


# ─── Screener ────────────────────────────────────────────────────────────────


def _screener_load_fundamentals(engine, payload) -> "pd.DataFrame":
    import pandas as pd
    import sqlalchemy as sa
    if payload.universe == "all":
        universe_filter = ""
        qparams = {"min_cap": payload.min_market_cap}
    elif payload.universe in ("etf_broad", "etf_precious_metals"):
        universe_filter = "AND universe = :universe"
        qparams = {"min_cap": 0, "universe": payload.universe}
    else:
        universe_filter = "AND universe = :universe"
        qparams = {"min_cap": payload.min_market_cap, "universe": payload.universe}
    with engine.connect() as conn:
        rows = conn.execute(sa.text(f"""
            SELECT tf.ticker, tf.name, tf.sector, tf.industry, tf.market_cap,
                   tf.total_debt, tf.total_revenue, tf.beta, tf.dividend_yield,
                   tf.earning_yield_sec, tf.roic_sec, tf.pe_ratio, tf.ev_ebitda,
                   tf.net_margin, tf.fcf_yield, tf.debt_equity, tf.current_ratio,
                   tf.haram_revenue_ratio, tf.sharia_debt_ratio, tf.sharia_income_ratio,
                   iv.iv_30d
            FROM ticker_fundamentals tf
            LEFT JOIN (
                SELECT DISTINCT ON (ticker) ticker, iv
                FROM implied_vol ORDER BY ticker, date DESC
            ) iv ON tf.ticker = iv.ticker
            WHERE tf.market_cap >= :min_cap {universe_filter}
            ORDER BY tf.market_cap DESC
        """), qparams).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=[
        "ticker","name","sector","industry","market_cap","total_debt","total_revenue",
        "beta","dividend_yield","earning_yield_sec","roic_sec","pe_ratio","ev_ebitda",
        "net_margin","fcf_yield","debt_equity","current_ratio",
        "haram_revenue_ratio","sharia_debt_ratio","sharia_income_ratio","iv_30d"])


# ─── Sharia screening constants (AAOIFI / MSCI Islamic Index) ───────────────

# Secteurs exclus (haram par nature)
_SHARIA_SECTOR_BLACKLIST = [
    "bank", "insurance", "financial services", "diversified financial",
    "alcohol", "beverage", "distiller", "brewer", "winery",
    "casino", "gambling", "gaming", "lottery",
    "tobacco",
    "adult entertainment", "pornograph",
    "weapon", "defense", "aerospace & defense",
    "pork", "swine",
]

# Entreprises explicitement non-conformes (revenues haram > 5%)
# Sources : MSCI Islamic, Dow Jones Islamic Market Index
_SHARIA_TICKER_BLACKLIST = {
    # Alcool
    "MC.PA",   # LVMH — Moët Hennessy (alcool > 5% CA)
    "RI.PA",   # Pernod Ricard
    "BN.PA",   # Danone (alcool dans certaines filiales)
    "ABI",     # AB InBev
    "SAB",     # SABMiller
    "HNZ",     # Heineken
    "DEO",     # Diageo
    "BF.B",    # Brown-Forman
    # Banques / finance intérêt
    "JPM", "BAC", "WFC", "C", "GS", "MS",
    "BNP.PA", "SAN.PA", "ACA.PA", "GLE.PA", "BNPP.PA",
    # Tabac
    "PM", "MO", "BTI", "IMBBY",
    # Casinos / jeux
    "LVS", "WYNN", "MGM", "CZR",
    # Défense/armes
    "LMT", "RTX", "NOC", "GD", "BA",
    "AIR.PA", "HO.PA",
}


def _screener_apply_filters(df, payload):
    if payload.require_ethical:
        ethical_bl = ["weapons","tobacco","gambling","fossil","coal","oil","defense","arms"]
        df = df[~df["sector"].str.lower().apply(
            lambda s: any(b in s for b in ethical_bl)
        )]
    if payload.require_sharia:
        # Critère 1 — Exclusion sectorielle (haram par nature)
        df = df[~df["sector"].str.lower().apply(
            lambda s: any(b in s for b in _SHARIA_SECTOR_BLACKLIST)
        )]
        df = df[~df["industry"].str.lower().apply(
            lambda s: any(b in s for b in _SHARIA_SECTOR_BLACKLIST)
        )]

        # Critère 2 — Blacklist explicite (revenus haram > 5%)
        df = df[~df["ticker"].isin(_SHARIA_TICKER_BLACKLIST)]

        # Critère 3 — Ratio dette / market cap ≤ 33% (AAOIFI)
        df["_debt_ratio"] = df["total_debt"] / (df["market_cap"] + 1)
        df = df[df["_debt_ratio"] <= 0.33]

        # Critère 4 — Ratio revenus / market cap (proxy liquidité) ≤ 70%
        # Filtre les holdings financières déguisées
        df["_rev_ratio"] = df["total_revenue"] / (df["market_cap"] + 1)
        df = df[df["_rev_ratio"] <= 0.70]

        # Nettoyage colonnes temporaires
        df = df.drop(columns=["_debt_ratio", "_rev_ratio"], errors="ignore")

    return df


def _screener_load_prices(engine, tickers):
    import pandas as pd
    import sqlalchemy as sa
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT ticker, date, adj_close FROM ohlcv
            WHERE ticker = ANY(:tickers) AND date >= CURRENT_DATE - INTERVAL '300 days'
            ORDER BY ticker, date
        """), {"tickers": tickers}).fetchall()
    if not rows:
        return pd.DataFrame()
    price_df = pd.DataFrame(rows, columns=["ticker","date","price"])
    return price_df.pivot(index="date", columns="ticker", values="price")




def _price_returns(ser) -> tuple:
    """Compute momentum and volatility from price series."""
    ret_1m = float(ser.pct_change(21).iloc[-1]) if len(ser) >= 22 else 0.0
    ret_6m = float(ser.pct_change(126).iloc[-1]) if len(ser) >= 127 else 0.0
    ret_12m = float(ser.pct_change(252).iloc[-1]) if len(ser) >= 253 else 0.0
    vol_20 = float(ser.pct_change().iloc[-20:].std()) if len(ser) >= 21 else 1.0
    return ret_1m, ret_6m, ret_12m, vol_20


def _proxy_fundamentals(mc: float, total_debt: float, total_revenue: float) -> tuple:
    """Compute proxy earning yield and ROIC when SEC data unavailable."""
    ev = mc + total_debt
    ebit = total_revenue * 0.15
    ey = (ebit / ev) if ev > 0 else 0.0
    roic = ebit / max(mc * 0.5, 1)
    return ey, roic

def _ticker_score(ticker: str, row, price_pivot) -> dict:
    """Compute score dict for a single ticker."""
    import pandas as pd
    mc = float(row["market_cap"] or 1)
    ey = float(row["earning_yield_sec"] or 0.0)
    roic = float(row["roic_sec"] or 0.0)
    if ey == 0.0 and roic == 0.0:
        ey, roic = _proxy_fundamentals(mc, float(row["total_debt"] or 0), float(row["total_revenue"] or 0))
    ser = price_pivot[ticker].dropna() if ticker in price_pivot.columns else pd.Series(dtype=float)
    ret_1m, ret_6m, ret_12m, vol_20 = _price_returns(ser)
    return {
        "ticker": ticker, "name": str(row["name"]), "sector": str(row["sector"]),
        "market_cap": mc, "earning_yield": round(ey,4), "roic": round(roic,4),
        "beta": round(float(row["beta"] or 1.0),2),
        "ret_1m": round(ret_1m*100,2), "ret_6m": round(ret_6m*100,2),
        "ret_12m": round(ret_12m*100,2), "vol_20": round(vol_20*100,2),
        "dividend_yield": round(float(row["dividend_yield"] or 0),2),
    }

def _screener_compute_scores(df, price_pivot):
    import pandas as pd
    scores = [
        _ticker_score(ticker, df[df["ticker"] == ticker].iloc[0], price_pivot)
        for ticker in df["ticker"].tolist()
    ]
    return pd.DataFrame(scores)



def _rank_magic_formula(df):
    df["score"] = df["earning_yield"].rank(ascending=False) + df["roic"].rank(ascending=False)
    return df.sort_values("score")

def _rank_momentum(df):
    df["score"] = df["ret_12m"]*0.5 + df["ret_6m"]*0.3 + df["ret_1m"]*0.2
    return df.sort_values("score", ascending=False)

def _rank_low_vol(df):
    df["score"] = df["vol_20"]
    return df.sort_values("score")

def _rank_ml(df):
    try:
        from sklearn.preprocessing import StandardScaler
        features = ["earning_yield","roic","ret_1m","ret_6m","ret_12m","vol_20","beta"]
        x_scaled = StandardScaler().fit_transform(df[features].fillna(0).values)
        df["score"] = x_scaled @ np.array([1,1,1,1,1,-1,-1], dtype=float)
        return df.sort_values("score", ascending=False)
    except Exception:
        df["score"] = df["earning_yield"]
        return df.sort_values("score", ascending=False)

def _rank_combined(df):
    df["score"] = (
        df["earning_yield"].rank(ascending=False)
        + df["roic"].rank(ascending=False)
        + (df["ret_6m"] + df["ret_12m"]).rank(ascending=False) * 0.5
        + df["vol_20"].rank(ascending=True) * 0.3
    )
    return df.sort_values("score")

_RANKERS = {
    "magic_formula": _rank_magic_formula,
    "momentum": _rank_momentum,
    "low_vol": _rank_low_vol,
    "ml": _rank_ml,
    "combined": _rank_combined,
}

def _screener_rank(scores_df, method, top_n):
    ranker = _RANKERS.get(method, _rank_magic_formula)
    scores_df = ranker(scores_df)
    scores_df = scores_df.head(top_n).reset_index(drop=True)
    scores_df["rank"] = scores_df.index + 1
    scores_df["score"] = scores_df["score"].round(2)
    return scores_df


@app.post("/api/screener")
async def screener(payload: ScreenerIn):
    """
    Rank the full universe of tickers by the chosen method and return top N.
    Results can be fed directly into the backtest panel.
    """
    import os

    import numpy as np
    import sqlalchemy as sa

    loop = asyncio.get_event_loop()

    def _run_screener():
        import sqlalchemy as sa
        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        df = _screener_load_fundamentals(engine, payload)
        if df.empty:
            return []
        df = _screener_apply_filters(df, payload)
        if df.empty:
            return []
        tickers = df["ticker"].tolist()
        price_pivot = _screener_load_prices(engine, tickers)
        scores_df = _screener_compute_scores(df, price_pivot)
        if scores_df.empty:
            return []
        scores_df = _screener_rank(scores_df, payload.method, payload.top_n)
        # Finance Islamique — merger depuis df original apres ranking
        import numpy as np
        sharia_cols = [c for c in ["haram_revenue_ratio","sharia_debt_ratio","sharia_income_ratio"] if c in df.columns]
        if sharia_cols:
            scores_df = scores_df.merge(df[["ticker"]+sharia_cols], on="ticker", how="left", suffixes=("","_y"))
        for col in ["haram_revenue_ratio","sharia_debt_ratio","sharia_income_ratio"]:
            if col not in scores_df.columns:
                scores_df[col] = None
        has_data = scores_df["sharia_debt_ratio"].notna() | scores_df["sharia_income_ratio"].notna()
        scores_df["is_sharia"] = np.where(
            has_data,
            (scores_df["sharia_debt_ratio"].fillna(0.0) <= 0.33) & (scores_df["sharia_income_ratio"].fillna(0.0) <= 0.05),
            None
        )
        return scores_df.to_dict(orient="records")

    results = await loop.run_in_executor(None, _run_screener)
    return {"results": results, "method": payload.method, "count": len(results)}


# ─── Backtest ────────────────────────────────────────────────────────────────


def _filter_tickers_by_screen(records, require_ethical: bool, require_sharia: bool):
    """Apply user-toggled screens. Returns filtered list of records."""
    out = []
    for r in records:
        if require_ethical and not r.is_ethical:
            continue
        if require_sharia and not r.is_sharia:
            continue
        out.append(r)
    return out


@app.post("/api/backtest")
async def run_backtest(payload: BacktestIn):
    strategy = strategy_registry.get_instance(payload.strategy)
    if strategy is None:
        raise HTTPException(404, f"Strategy '{payload.strategy}' not found")

    records = await registry.load_many(payload.tickers)
    records = _filter_tickers_by_screen(records, payload.require_ethical, payload.require_sharia)
    if not records:
        raise HTTPException(400, "Aucun ticker ne passe les filtres sélectionnés")

    tickers = [r.ticker for r in records]
    currencies = {r.ticker: r.currency for r in records}

    INDICATOR_TICKERS = {
        "^VIX",
        "^GSPC",
        "^FCHI",
        "^STOXX50E",
        "^GDAXI",
        "^N225",
        "EURUSD=X",
        "USDEUR=X",
    }

    getattr(payload, "use_adjusted_close", True)
    all_tickers = list(set(tickers + [payload.benchmark, "^VIX", "^GSPC", "EURUSD=X"]))
    # Benchmark toujours adj_close — portfolio selon use_adjusted_close
    prices_full = await get_prices(all_tickers, period=payload.period)

    bench_series = (
        prices_full[payload.benchmark] if payload.benchmark in prices_full.columns else None
    )
    strat_prices = prices_full[
        [c for c in prices_full.columns if c not in INDICATOR_TICKERS and c != payload.benchmark]
    ]

    if prices_full.empty:
        raise HTTPException(400, "No price data")

    eurusd = await get_fx_rate("USD", "EUR")
    fx_rates = {"USDEUR": eurusd, "EURUSD": 1.0 / eurusd}

    params = StrategyParams(
        initial_capital=payload.initial_capital,
        monthly_contribution=payload.monthly_contribution,
        broker=payload.broker,
        account_type=payload.account_type,
        rebalance_frequency=payload.rebalance_frequency,
        max_position_pct=payload.max_position_pct,
        stop_loss_pct=payload.stop_loss_pct,
        custom=payload.custom_params,
        use_var_constraint=payload.use_var_constraint,
    )

    engine = BacktestEngine(strategy, strat_prices, currencies, fx_rates, params, bench_series)
    from backend.core.db import engine as _db_engine
    result = engine.run(db_engine=_db_engine)

    bench_returns = (
        bench_series.pct_change(fill_method=None).dropna() if bench_series is not None else None
    )
    return build_tearsheet(result, benchmark_returns=bench_returns, prices=prices_full)


@app.post("/api/backtest/pdf")
async def backtest_pdf(payload: BacktestIn):
    from backend.core.data import get_ticker_fundamentals
    from backend.core.buffett import compute_buffett_score
    tearsheet = await run_backtest(payload)
    # Enrichir tearsheet avec screening + buffett par ticker
    tickers = payload.tickers or []
    screening = {}
    buffett = {}
    for t in tickers:
        try:
            rec = await registry.load(t)
            if rec:
                from backend.core.registry import ticker_to_dict
                screening[t] = ticker_to_dict(rec)
        except Exception:
            pass
        try:
            info = await get_ticker_fundamentals(t)
            mc = float(info.get("market_cap") or 0) or None
            buffett[t] = compute_buffett_score(info, mc)
        except Exception:
            pass
    tearsheet["screening"] = screening
    tearsheet["buffett"] = buffett
    tearsheet.setdefault("meta", {})["tickers"] = tickers
    # Portfolio analytics
    try:
        from backend.core.portfolio_analytics import compute_portfolio_analytics
        from backend.core.db import engine as db_engine
        positions = {t: {"qty": 1, "avg_price": 100, "last_price": 100} for t in tickers}
        tearsheet["portfolio_analytics"] = compute_portfolio_analytics(positions, db_engine)
    except Exception as e:
        log.warning("Portfolio analytics PDF error: %s", e)
        tearsheet["portfolio_analytics"] = {}
    pdf_bytes = generate_pdf(tearsheet)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport_{payload.strategy}_{date.today()}.pdf"'
        },
    )


# ─── Portfolio Tracker ───────────────────────────────────────────────────────
from backend.auth.tracker_routes import register_tracker_routes
from backend.core.db import engine as _db_engine
try:
    from backend.auth.jwt import get_current_user as _get_current_user
    register_tracker_routes(app, _get_current_user, _db_engine)
    log.info("Tracker routes registered")
except Exception as _e:
    log.warning("Tracker routes error: %s", _e)


# ─── Monte Carlo ─────────────────────────────────────────────────────────────


@app.post("/api/montecarlo")
async def monte_carlo(payload: MonteCarloIn):
    df = await get_prices([payload.ticker], period=payload.period)
    if df.empty:
        raise HTTPException(400, "No data")
    series = df[payload.ticker].dropna()
    res = run_simulation(
        series, payload.initial_capital, payload.n_paths, payload.n_days, payload.method
    )
    return {
        "final_values_summary": {
            "p5": res.percentile_5,
            "p25": res.percentile_25,
            "median": res.median,
            "p75": res.percentile_75,
            "p95": res.percentile_95,
        },
        "prob_loss": res.prob_loss,
        "var_95": res.var_95,
        "cvar_95": res.cvar_95,
        "expected_return": res.expected_return,
        "paths_sample": res.paths_sample.tolist(),
    }


# ─── Signals & rebalance ─────────────────────────────────────────────────────


@app.get("/api/stats")
async def platform_stats():
    """Stats temps réel de la plateforme pour la Home page."""
    import sqlalchemy as sa
    from backend.core.db import engine
    with engine.connect() as conn:
        ohlcv = conn.execute(sa.text("SELECT COUNT(*) FROM ohlcv")).scalar()
        tickers = conn.execute(sa.text("SELECT COUNT(DISTINCT ticker) FROM ticker_fundamentals")).scalar()
        fundamentals = conn.execute(sa.text("SELECT COUNT(*) FROM ticker_fundamentals")).scalar()
        signals = conn.execute(sa.text("SELECT COUNT(DISTINCT strategy_id) FROM signals_history")).scalar()
        universes = conn.execute(sa.text("SELECT COUNT(DISTINCT universe) FROM ticker_fundamentals")).scalar()
        last_ohlcv = conn.execute(sa.text("SELECT MAX(date) FROM ohlcv")).scalar()
    def fmt(n):
        if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
        if n >= 1_000: return f"{n/1_000:.1f}k"
        return str(n)
    return {
        "tickers": {"value": str(tickers), "sub": f"{universes} universes"},
        "ohlcv": {"value": fmt(ohlcv), "sub": f"up to {last_ohlcv}"},
        "fundamentals": {"value": str(fundamentals), "sub": "SEC EDGAR records"},
        "signals": {"value": f"{signals} strat", "sub": "stored 20h30 UTC"},
    }


@app.get("/api/tickers")
async def list_tickers(universe: str = "all", limit: int = 600):
    """Liste les tickers par univers depuis ticker_fundamentals."""
    import sqlalchemy as sa
    from backend.core.db import engine
    with engine.connect() as conn:
        if universe == "all":
            rows = conn.execute(sa.text(
                "SELECT ticker, name, universe FROM ticker_fundamentals ORDER BY ticker LIMIT :limit"
            ), {"limit": limit}).fetchall()
        else:
            rows = conn.execute(sa.text(
                "SELECT ticker, name, universe FROM ticker_fundamentals WHERE universe = :u ORDER BY ticker LIMIT :limit"
            ), {"u": universe, "limit": limit}).fetchall()
    return {"tickers": [{"ticker": r[0], "name": r[1], "universe": r[2]} for r in rows]}


@app.get("/api/signals/latest")
async def signals_latest(limit: int = 20, universe: str = "all", strategy: str = "epr5"):
    """Derniers signaux depuis signals_history — pour la Home page."""
    import sqlalchemy as sa
    from backend.core.db import engine
    try:
        with engine.connect() as conn:
            universe_filter = ""
            if universe != "all":
                universe_filter = "AND tf.universe = :universe"
            rows = conn.execute(sa.text(f"""
                SELECT sh.ticker, sh.date, sh.strategy_id,
                       sh.signal_buy, sh.signal_sell, sh.composite_score,
                       sh.sentiment_score, sh.fundamental_score, sh.rf_score,
                       tf.universe
                FROM signals_history sh
                LEFT JOIN ticker_fundamentals tf ON sh.ticker = tf.ticker
                WHERE sh.strategy_id = :strategy
                {universe_filter}
                ORDER BY sh.date DESC, sh.composite_score DESC
                LIMIT :limit
            """), {"strategy": strategy, "universe": universe, "limit": limit}).fetchall()
        return {"signals": [
            {
                "ticker": r[0], "date": str(r[1]), "strategy": r[2],
                "signal": "BUY" if r[3] else "SELL" if r[4] else "HOLD",
                "composite": round(float(r[5] or 0), 2),
                "sentiment": round(float(r[6] or 0), 2),
                "fundamental": round(float(r[7] or 0), 2),
                "epr5": round(float(r[8] or 0), 2),
                "universe": r[9] or "sp500",
            }
            for r in rows
        ]}
    except Exception as e:
        log.warning("signals_latest error: %s", e)
        return {"signals": []}


@app.post("/api/signals/daily")
async def daily_signals(payload: TickerListIn, strategy: str = "epr5"):
    """Signaux journaliers pondérés selon la stratégie choisie.

    Stratégies disponibles : epr5, momentum, mean_reversion, sma_crossover, dual_momentum, buy_hold
    Les poids de chaque vote varient selon la stratégie.
    """
    STRATEGY_WEIGHTS = {
        "epr5": {"sma": 0.20, "rsi": 0.20, "macd": 0.20, "momentum": 0.20, "sentiment": 0.20},
        "momentum": {"sma": 0.10, "rsi": 0.15, "macd": 0.20, "momentum": 0.35, "sentiment": 0.20},
        "mean_reversion": {
            "sma": 0.15,
            "rsi": 0.35,
            "macd": 0.15,
            "momentum": 0.10,
            "sentiment": 0.25,
        },
        "sma_crossover": {
            "sma": 0.55,
            "rsi": 0.10,
            "macd": 0.15,
            "momentum": 0.10,
            "sentiment": 0.10,
        },
        "dual_momentum": {
            "sma": 0.10,
            "rsi": 0.15,
            "macd": 0.15,
            "momentum": 0.30,
            "sentiment": 0.30,
        },
        "buy_hold": {"sma": 0.20, "rsi": 0.20, "macd": 0.20, "momentum": 0.15, "sentiment": 0.25},
    }
    weights = STRATEGY_WEIGHTS.get(strategy, STRATEGY_WEIGHTS["epr5"])
    raw = await compute_daily_signals(payload.tickers)

    results = []
    for s in raw:
        ind = s.get("indicators", {})

        # Normalise chaque vote de -1/0/+1 vers 0..1
        def norm(v):
            return (v + 1) / 2.0

        technical = (
            norm(ind.get("sma_crossover", 0)) * weights["sma"]
            + norm(ind.get("rsi", 0)) * weights["rsi"]
            + norm(ind.get("macd", 0)) * weights["macd"]
            + norm(ind.get("momentum", 0)) * weights["momentum"]
            + norm(ind.get("sentiment", 0)) * weights["sentiment"]
        )
        composite = round(technical, 4)
        if composite >= 0.60:
            signal = "BUY"
        elif composite <= 0.40:
            signal = "SELL"
        else:
            signal = "HOLD"
        results.append(
            {
                "ticker": s["ticker"],
                "date": s["date"],
                "strategy": strategy,
                "signal": signal,
                "composite_score": composite,
                "rf_score": norm(ind.get("sma_crossover", 0)),
                "lstm_score": norm(ind.get("macd", 0)),
                "sentiment_score": norm(ind.get("sentiment", 0)),
                "fundamental_score": norm(ind.get("rsi", 0)),
                "technical_score": norm(ind.get("momentum", 0)),
                "raw_indicators": ind,
                "sentiment_detail": s.get("sentiment", {}),
            }
        )
    return {"signals": results, "strategy": strategy, "weights": weights}


@app.post("/api/sentiment")
async def sentiment_analysis(payload: TickerListIn):
    """Analyse de sentiment RSS Yahoo Finance + VADER pour une liste de tickers."""
    import asyncio

    from backend.quant.sentiment import analyze_market_sentiment, analyze_portfolio_sentiment

    loop = asyncio.get_event_loop()

    def _run():
        market = analyze_market_sentiment()
        portfolio = analyze_portfolio_sentiment(payload.tickers[:10], delay=0.3)
        return {"market": market, "tickers": portfolio}

    result = await loop.run_in_executor(None, _run)
    return result


@app.post("/api/admin/drive-sync")
async def admin_drive_sync():
    """Déclenche manuellement la synchronisation Google Drive → DB."""
    from backend.core.drive_sync import trigger_drive_sync

    return await trigger_drive_sync()


@app.get("/api/stats")
async def platform_stats():
    """Statistiques temps réel de la plateforme."""
    import asyncio
    import os

    import sqlalchemy as sa

    loop = asyncio.get_event_loop()

    def _get_stats():
        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        with engine.connect() as conn:
            ohlcv = conn.execute(
                sa.text("SELECT COUNT(*), COUNT(DISTINCT ticker) FROM ohlcv")
            ).fetchone()
            fundamentals = conn.execute(
                sa.text("SELECT COUNT(*) FROM ticker_fundamentals")
            ).fetchone()
            last_date = conn.execute(sa.text("SELECT MAX(date) FROM ohlcv")).fetchone()
        return {
            "ohlcv_rows": ohlcv[0],
            "tickers": ohlcv[1],
            "fundamentals": fundamentals[0],
            "last_update": str(last_date[0]) if last_date[0] else None,
        }

    stats = await loop.run_in_executor(None, _get_stats)
    return stats


@app.get("/api/sentiment/market")
async def market_sentiment():
    """Sentiment global du marché (SP500 + Nasdaq)."""
    import asyncio

    from backend.quant.sentiment import analyze_market_sentiment

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, analyze_market_sentiment)
    return result


@app.post("/api/signals/rebalance")
async def rebalance(payload: RebalanceIn):
    all_tickers = sorted(set(payload.positions) | set(payload.target_weights))
    prices_df = await get_prices(all_tickers, period="3mo")
    eurusd = await get_fx_rate("USD", "EUR")
    prices_eur = {}
    for t in all_tickers:
        if t not in prices_df.columns or prices_df[t].dropna().empty:
            continue
        last_native = float(prices_df[t].dropna().iloc[-1])
        ccy = payload.positions.get(t, {}).get("currency", "USD")
        prices_eur[t] = last_native * (eurusd if ccy != "EUR" else 1.0)

    orders = compute_rebalance_orders(
        payload.positions,
        prices_eur,
        payload.target_weights,
        payload.cash_eur,
        payload.broker,
    )
    return {"orders": orders, "date": str(date.today())}


handler = app
