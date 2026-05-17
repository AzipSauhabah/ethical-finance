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
from backend.core.queue import start_worker, subscribe, unsubscribe, watch
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


@app.on_event("startup")
async def _startup():
    start_worker()
    log.info("API ready — %d strategies", len(strategy_registry))


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
        sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
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
                           total_debt, total_revenue, beta, dividend_yield
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

        # 4. Compute scores
        scores = {}
        for ticker in tickers:
            row = df[df["ticker"] == ticker].iloc[0]
            market_cap = float(row["market_cap"] or 1)
            total_debt = float(row["total_debt"] or 0)
            total_revenue = float(row["total_revenue"] or 0)
            beta = float(row["beta"] or 1.0)

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
                X_scaled = scaler.fit_transform(X)
                ideal = np.array([1, 1, 1, 1, 1, -1, -1], dtype=float)
                ml_scores = X_scaled @ ideal
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

    all_tickers = list(set(tickers + [payload.benchmark, "^VIX", "^GSPC", "EURUSD=X"]))
    prices_full = await get_prices(all_tickers, period=payload.period)

    bench_series = (
        prices_full[payload.benchmark] if payload.benchmark in prices_full.columns else None
    )
    [c for c in prices_full.columns if c not in INDICATOR_TICKERS and c != payload.benchmark]
    strat_prices = prices_full[[c for c in prices_full.columns if c not in {payload.benchmark}]]

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
async def daily_signals(payload: TickerListIn):
    return {"signals": await compute_daily_signals(payload.tickers)}


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
