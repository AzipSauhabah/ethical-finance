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


@app.get("/api/tickers/{ticker}/screening")
async def screening_detail(ticker: str):
    """Detailed breakdown for one ticker."""
    rec = await registry.load(ticker.upper())
    return ticker_to_dict(rec)


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
        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)
        engine = sa.create_engine(sync_url, pool_pre_ping=True)

        # 1. Load fundamentals
        with engine.connect() as conn:
            if payload.universe == "all":
                universe_filter = ""
                params = {"min_cap": payload.min_market_cap}
            elif payload.universe in ("etf_broad", "etf_precious_metals"):
                universe_filter = "AND universe = :universe"
                params = {"min_cap": 0, "universe": payload.universe}
            else:
                universe_filter = "AND universe = :universe"
                params = {"min_cap": payload.min_market_cap, "universe": payload.universe}

            rows = conn.execute(
                sa.text(f"""
                    SELECT ticker, name, sector, industry, market_cap,
                           total_debt, total_revenue, beta, dividend_yield,
                           earning_yield_sec, roic_sec, pe_ratio, ev_ebitda,
                           net_margin, fcf_yield, debt_equity, current_ratio
                    FROM ticker_fundamentals
                    WHERE market_cap >= :min_cap
                    {universe_filter}
                    ORDER BY market_cap DESC
                """),
                params,
            ).fetchall()

        if not rows:
            return []

        import pandas as pd

        df = pd.DataFrame(
            rows,
            columns=[
                "ticker",
                "name",
                "sector",
                "industry",
                "market_cap",
                "total_debt",
                "total_revenue",
                "beta",
                "dividend_yield",
                "earning_yield_sec",
                "roic_sec",
                "pe_ratio",
                "ev_ebitda",
                "net_margin",
                "fcf_yield",
                "debt_equity",
                "current_ratio",
            ],
        )

        # 2. Ethical / Sharia filter
        if payload.require_ethical:
            ethical_blacklist = ["weapons", "tobacco", "gambling", "fossil", "coal", "oil"]
            mask = ~df["sector"].str.lower().apply(lambda s: any(b in s for b in ethical_blacklist))
            df = df[mask]

        if payload.require_sharia:
            sharia_blacklist = ["bank", "insurance", "financial", "alcohol", "casino", "tobacco"]
            mask = ~df["sector"].str.lower().apply(lambda s: any(b in s for b in sharia_blacklist))
            df = df[mask]
            df["debt_ratio"] = df["total_debt"] / (df["market_cap"] + 1)
            df = df[df["debt_ratio"] <= 0.33]

        if df.empty:
            return []

        tickers = df["ticker"].tolist()

        # 3. Load recent prices
        with engine.connect() as conn:
            price_rows = conn.execute(
                sa.text("""
                    SELECT ticker, date, adj_close
                    FROM ohlcv
                    WHERE ticker = ANY(:tickers)
                      AND date >= CURRENT_DATE - INTERVAL '300 days'
                    ORDER BY ticker, date
                """),
                {"tickers": tickers},
            ).fetchall()

        price_df = pd.DataFrame(price_rows, columns=["ticker", "date", "price"])
        price_pivot = price_df.pivot(index="date", columns="ticker", values="price")

        # 4. Compute scores — colonnes SEC depuis DB en priorité, fallback proxy
        scores = {}
        for ticker in tickers:
            row = df[df["ticker"] == ticker].iloc[0]
            market_cap = float(row["market_cap"] or 1)
            total_debt = float(row["total_debt"] or 0)
            total_revenue = float(row["total_revenue"] or 0)
            beta = float(row["beta"] or 1.0)

            # SEC depuis DB (pré-calculé par le scheduler 22h)
            earning_yield = float(row["earning_yield_sec"] or 0.0)
            roic = float(row["roic_sec"] or 0.0)

            # Fallback proxy si colonnes SEC vides
            if earning_yield == 0.0 and roic == 0.0:
                ev = market_cap + total_debt
                ebit = total_revenue * 0.15
                net_assets = max(market_cap * 0.5, 1)
                earning_yield = (ebit / ev) if ev > 0 else 0.0
                roic = (ebit / net_assets) if net_assets > 0 else 0.0

            ser = (
                price_pivot[ticker].dropna()
                if ticker in price_pivot.columns
                else pd.Series(dtype=float)
            )

            ret_1m = float(ser.pct_change(21).iloc[-1]) if len(ser) >= 22 else 0.0
            ret_6m = float(ser.pct_change(126).iloc[-1]) if len(ser) >= 127 else 0.0
            ret_12m = float(ser.pct_change(252).iloc[-1]) if len(ser) >= 253 else 0.0
            vol_20 = float(ser.pct_change().iloc[-20:].std()) if len(ser) >= 21 else 1.0

            scores[ticker] = {
                "ticker": ticker,
                "name": str(row["name"]),
                "sector": str(row["sector"]),
                "market_cap": market_cap,
                "earning_yield": round(earning_yield, 4),
                "roic": round(roic, 4),
                "beta": round(beta, 2),
                "ret_1m": round(ret_1m * 100, 2),
                "ret_6m": round(ret_6m * 100, 2),
                "ret_12m": round(ret_12m * 100, 2),
                "vol_20": round(vol_20 * 100, 2),
                "dividend_yield": round(float(row["dividend_yield"] or 0), 2),
            }

        scores_df = pd.DataFrame(list(scores.values()))
        if scores_df.empty:
            return []

        # 5. Ranking
        if payload.method == "magic_formula":
            scores_df["rank_ey"] = scores_df["earning_yield"].rank(ascending=False)
            scores_df["rank_roic"] = scores_df["roic"].rank(ascending=False)
            scores_df["score"] = scores_df["rank_ey"] + scores_df["rank_roic"]
            scores_df = scores_df.sort_values("score")

        elif payload.method == "momentum":
            scores_df["score"] = (
                scores_df["ret_12m"] * 0.5 + scores_df["ret_6m"] * 0.3 + scores_df["ret_1m"] * 0.2
            )
            scores_df = scores_df.sort_values("score", ascending=False)

        elif payload.method == "low_vol":
            scores_df["score"] = scores_df["vol_20"]
            scores_df = scores_df.sort_values("score")

        elif payload.method == "ml":
            try:
                from sklearn.preprocessing import StandardScaler

                features = [
                    "earning_yield",
                    "roic",
                    "ret_1m",
                    "ret_6m",
                    "ret_12m",
                    "vol_20",
                    "beta",
                ]
                X = scores_df[features].fillna(0).values
                scaler = StandardScaler()
                x_scaled = scaler.fit_transform(X)
                ideal = np.array([1, 1, 1, 1, 1, -1, -1], dtype=float)
                ml_scores = x_scaled @ ideal
                scores_df["score"] = ml_scores
                scores_df = scores_df.sort_values("score", ascending=False)
            except Exception:
                scores_df["score"] = scores_df["earning_yield"]
                scores_df = scores_df.sort_values("score", ascending=False)

        elif payload.method == "combined":
            scores_df["rank_ey"] = scores_df["earning_yield"].rank(ascending=False)
            scores_df["rank_roic"] = scores_df["roic"].rank(ascending=False)
            scores_df["rank_mom"] = (scores_df["ret_6m"] + scores_df["ret_12m"]).rank(
                ascending=False
            )
            scores_df["rank_vol"] = scores_df["vol_20"].rank(ascending=True)
            scores_df["score"] = (
                scores_df["rank_ey"]
                + scores_df["rank_roic"]
                + scores_df["rank_mom"] * 0.5
                + scores_df["rank_vol"] * 0.3
            )
            scores_df = scores_df.sort_values("score")

        scores_df = scores_df.head(payload.top_n).reset_index(drop=True)
        scores_df["rank"] = scores_df.index + 1
        scores_df["score"] = scores_df["score"].round(2)

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
    result = engine.run()

    bench_returns = (
        bench_series.pct_change(fill_method=None).dropna() if bench_series is not None else None
    )
    return build_tearsheet(result, benchmark_returns=bench_returns, prices=prices_full)


@app.post("/api/backtest/pdf")
async def backtest_pdf(payload: BacktestIn):
    tearsheet = await run_backtest(payload)
    pdf_bytes = generate_pdf(tearsheet)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport_{payload.strategy}_{date.today()}.pdf"'
        },
    )


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
        signal = "BUY" if composite >= 0.60 else ("SELL" if composite <= 0.40 else "HOLD")
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
