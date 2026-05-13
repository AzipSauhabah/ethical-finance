"""
:file: api/index.py
:brief: FastAPI thin layer — routing only. All logic lives in submodules.
        Compatible with Vercel Python serverless deployment.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Response, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from api.backtest.engine import BacktestEngine
from api.backtest.stress import run_stress_tests
from api.config import (
    API_VERSION, COPYRIGHT, DISCLAIMER,
    DEFAULT_INITIAL_CAPITAL, DEFAULT_PERIOD,
    BENCHMARKS,
)
from api.core.cache import cache
from api.core.data import get_prices, get_live_quote, get_fx_rate
from api.core.queue import start_worker, subscribe, unsubscribe, watch
from api.core.registry import registry
from api.quant.montecarlo import run_simulation
from api.report.pdf import generate_pdf
from api.report.tearsheet import build_tearsheet
from api.signals.daily import compute_daily_signals
from api.signals.rebalance import compute_rebalance_orders
from api.strategies.base import StrategyParams
from api.strategies.custom import build_custom_strategy
from api.strategies.registry import strategy_registry

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

# Auto-discover built-in strategies on startup
strategy_registry.auto_discover()

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Ethical Finance Platform API",
    version     = API_VERSION,
    description = "Sauhabah — Backtest, signals & reporting engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    start_worker()
    log.info("API ready — %d strategies registered.", len(strategy_registry))


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class TickerListIn(BaseModel):
    tickers: list[str]


class BacktestIn(BaseModel):
    tickers:              list[str]
    strategy:             str
    period:               str   = DEFAULT_PERIOD
    initial_capital:      float = DEFAULT_INITIAL_CAPITAL
    monthly_contribution: float = 0.0
    broker:               str   = "default"
    account_type:         str   = "CTO"
    rebalance_frequency:  str   = "monthly"
    max_position_pct:     float = 0.25
    stop_loss_pct:        float | None = 0.10
    benchmark:            str   = "^GSPC"
    custom_params:        dict  = Field(default_factory=dict)


class MonteCarloIn(BaseModel):
    ticker:          str
    period:          str   = DEFAULT_PERIOD
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    n_paths:         int   = 5_000
    n_days:          int   = 252
    method:          str   = "gbm"   # 'gbm' | 'bootstrap'


class CustomStrategyIn(BaseModel):
    name:        str
    description: str = ""
    rules:       list[dict]
    combination: str = "majority"
    benchmark:   str = "^GSPC"


class RebalanceIn(BaseModel):
    positions:       dict[str, dict]
    target_weights:  dict[str, float]
    cash_eur:        float
    broker:          str = "default"


# ─────────────────────────────────────────────────────────────────────────────
# Health & meta
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict:
    return {
        "status":     "ok",
        "version":    API_VERSION,
        "copyright":  COPYRIGHT,
        "strategies": len(strategy_registry),
    }


@app.get("/api/meta")
async def meta() -> dict:
    return {
        "version":    API_VERSION,
        "copyright":  COPYRIGHT,
        "disclaimer": DISCLAIMER,
        "benchmarks": BENCHMARKS,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tickers
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/tickers/screen")
async def screen_tickers(payload: TickerListIn) -> dict:
    """Run ethical screen on a list of tickers."""
    records = await registry.load_many(payload.tickers)
    watch(payload.tickers)
    return {
        "tickers": [
            {
                "ticker":         r.ticker,
                "name":           r.name,
                "sector":         r.sector,
                "is_ethical":     r.is_ethical,
                "ethical_score":  r.ethical_score,
                "ethical_flags":  r.ethical_flags,
                "currency":       r.currency,
                "country":        r.country,
                "dividend_yield": r.dividend_yield,
                "beta":           r.beta,
                "market_cap":     r.market_cap,
            }
            for r in records
        ]
    }


@app.get("/api/quote/{ticker}")
async def quote(ticker: str) -> dict:
    return await get_live_quote(ticker.upper())


@app.get("/api/quote/stream/{ticker}")
async def quote_stream(ticker: str) -> StreamingResponse:
    """Server-Sent Events stream of live quotes for a ticker."""
    aq = subscribe(ticker.upper())

    async def _generator():
        try:
            # Send initial quote
            initial = await get_live_quote(ticker.upper())
            yield f"data: {json.dumps(initial)}\n\n"
            while True:
                try:
                    quote_data = await asyncio.wait_for(aq.get(), timeout=120)
                    yield f"data: {json.dumps(quote_data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unsubscribe(ticker.upper(), aq)

    return StreamingResponse(_generator(), media_type="text/event-stream")


@app.get("/api/prices")
async def prices(
    tickers: str = Query(..., description="Comma-separated tickers"),
    period:  str = Query(DEFAULT_PERIOD),
) -> dict:
    ts = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    df = await get_prices(ts, period=period)
    return {
        "tickers": ts,
        "period":  period,
        "data":    [
            {"date": str(idx.date()), **{c: (None if pd_isna(row[c]) else float(row[c])) for c in df.columns}}
            for idx, row in df.iterrows()
        ],
    }


def pd_isna(v) -> bool:
    import math
    try:
        return math.isnan(v)
    except Exception:
        return v is None


# ─────────────────────────────────────────────────────────────────────────────
# Strategies
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/strategies")
async def list_strategies() -> dict:
    return {"strategies": strategy_registry.list_all()}


@app.post("/api/strategies/custom")
async def create_custom_strategy(payload: CustomStrategyIn) -> dict:
    inst = build_custom_strategy(payload.dict())
    return {
        "name":        inst.name,
        "description": inst.description,
        "registered":  True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Backtest
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/backtest")
async def run_backtest(payload: BacktestIn) -> dict:
    strategy = strategy_registry.get_instance(payload.strategy)
    if strategy is None:
        raise HTTPException(404, detail=f"Strategy '{payload.strategy}' not found")

    # Load price data + fundamentals
    records  = await registry.load_many(payload.tickers)
    prices   = await get_prices(payload.tickers, period=payload.period)
    if prices.empty:
        raise HTTPException(400, detail="No price data found for given tickers")

    currencies = {r.ticker: r.currency for r in records}
    eurusd     = await get_fx_rate("USD", "EUR")
    fx_rates   = {"USDEUR": eurusd, "EURUSD": 1.0 / eurusd}

    # Benchmark
    bench_df = await get_prices([payload.benchmark], period=payload.period)
    bench_r  = bench_df[payload.benchmark].pct_change().dropna() if not bench_df.empty else None

    params = StrategyParams(
        initial_capital     = payload.initial_capital,
        monthly_contribution = payload.monthly_contribution,
        broker              = payload.broker,
        account_type        = payload.account_type,
        rebalance_frequency = payload.rebalance_frequency,
        max_position_pct    = payload.max_position_pct,
        stop_loss_pct       = payload.stop_loss_pct,
        custom              = payload.custom_params,
    )

    engine = BacktestEngine(strategy, prices, currencies, fx_rates, params)
    result = engine.run()

    tearsheet = build_tearsheet(result, benchmark_returns=bench_r)
    return tearsheet


@app.post("/api/backtest/pdf")
async def backtest_pdf(payload: BacktestIn):
    strategy = strategy_registry.get_instance(payload.strategy)
    if strategy is None:
        raise HTTPException(404, detail=f"Strategy '{payload.strategy}' not found")

    records   = await registry.load_many(payload.tickers)
    prices    = await get_prices(payload.tickers, period=payload.period)
    if prices.empty:
        raise HTTPException(400, detail="No price data found")

    currencies = {r.ticker: r.currency for r in records}
    eurusd     = await get_fx_rate("USD", "EUR")
    fx_rates   = {"USDEUR": eurusd, "EURUSD": 1.0 / eurusd}
    bench_df = await get_prices([payload.benchmark], period=payload.period)
    bench_r  = bench_df[payload.benchmark].pct_change().dropna() if not bench_df.empty else None

    params = StrategyParams(
        initial_capital=payload.initial_capital,
        monthly_contribution=payload.monthly_contribution,
        broker=payload.broker,
        account_type=payload.account_type,
        rebalance_frequency=payload.rebalance_frequency,
        max_position_pct=payload.max_position_pct,
        stop_loss_pct=payload.stop_loss_pct,
        custom=payload.custom_params,
    )
    result    = BacktestEngine(strategy, prices, currencies, fx_rates, params).run()
    tearsheet = build_tearsheet(result, benchmark_returns=bench_r)
    pdf_bytes = generate_pdf(tearsheet)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report_{payload.strategy}_{date.today()}.pdf"',
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/montecarlo")
async def monte_carlo(payload: MonteCarloIn) -> dict:
    df = await get_prices([payload.ticker], period=payload.period)
    if df.empty:
        raise HTTPException(400, detail="No data")
    series = df[payload.ticker].dropna()
    res = run_simulation(
        series,
        initial_capital=payload.initial_capital,
        n_paths=payload.n_paths,
        n_days=payload.n_days,
        method=payload.method,
    )
    return {
        "final_values_summary": {
            "p5":      res.percentile_5,
            "p25":     res.percentile_25,
            "median":  res.median,
            "p75":     res.percentile_75,
            "p95":     res.percentile_95,
        },
        "prob_loss":       res.prob_loss,
        "var_95":          res.var_95,
        "cvar_95":         res.cvar_95,
        "expected_return": res.expected_return,
        "paths_sample":    res.paths_sample.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Daily signals & rebalance
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/signals/daily")
async def daily_signals(payload: TickerListIn) -> dict:
    return {"signals": await compute_daily_signals(payload.tickers)}


@app.post("/api/signals/rebalance")
async def rebalance(payload: RebalanceIn) -> dict:
    # Fetch current prices for held + target tickers
    all_tickers = sorted(set(payload.positions) | set(payload.target_weights))
    prices_df   = await get_prices(all_tickers, period="3mo")
    eurusd      = await get_fx_rate("USD", "EUR")
    prices_eur  = {}
    for t in all_tickers:
        if t not in prices_df.columns or prices_df[t].dropna().empty:
            continue
        last_native = float(prices_df[t].dropna().iloc[-1])
        ccy = payload.positions.get(t, {}).get("currency", "USD")
        prices_eur[t] = last_native * (eurusd if ccy != "EUR" else 1.0)

    orders = compute_rebalance_orders(
        positions       = payload.positions,
        prices_eur      = prices_eur,
        target_weights  = payload.target_weights,
        cash_eur        = payload.cash_eur,
        broker          = payload.broker,
    )
    return {"orders": orders, "date": str(date.today())}


# ─────────────────────────────────────────────────────────────────────────────
# Vercel handler
# ─────────────────────────────────────────────────────────────────────────────
handler = app
