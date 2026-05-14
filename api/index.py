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

from fastapi import FastAPI, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.backtest.engine import BacktestEngine
from api.config import (
    API_VERSION, COPYRIGHT, DISCLAIMER,
    DEFAULT_INITIAL_CAPITAL, DEFAULT_PERIOD, BENCHMARKS,
)
from api.core.cache import cache
from api.core.data import get_prices, get_live_quote, get_fx_rate
from api.core.queue import start_worker, subscribe, unsubscribe, watch
from api.core.registry import registry, ticker_to_dict
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

strategy_registry.auto_discover()

app = FastAPI(
    title=f"Ethical Finance Platform API",
    version=API_VERSION,
    description="Sauhabah — Backtest, signals & reporting engine",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def _startup():
    start_worker()
    log.info("API ready — %d strategies", len(strategy_registry))


# ─── Schemas ──────────────────────────────────────────────────────────────────

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
    require_ethical:      bool  = False
    require_sharia:       bool  = False


class CustomStrategyIn(BaseModel):
    name:        str
    description: str = ""
    rules:       list[dict]
    combination: str = "majority"
    benchmark:   str = "^GSPC"


class RebalanceIn(BaseModel):
    positions:      dict[str, dict]
    target_weights: dict[str, float]
    cash_eur:       float
    broker:         str = "default"


class MonteCarloIn(BaseModel):
    ticker:          str
    period:          str   = DEFAULT_PERIOD
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    n_paths:         int   = 5_000
    n_days:          int   = 252
    method:          str   = "gbm"


# ─── Health & meta ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": API_VERSION, "strategies": len(strategy_registry)}


@app.get("/api/meta")
async def meta():
    return {"version": API_VERSION, "copyright": COPYRIGHT,
            "disclaimer": DISCLAIMER, "benchmarks": BENCHMARKS}


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
        "tickers": ts, "period": period,
        "data": [
            {"date": str(idx.date()),
             **{c: (None if (isinstance(row[c], float) and math.isnan(row[c])) else float(row[c])) for c in df.columns}}
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

    records  = await registry.load_many(payload.tickers)
    records  = _filter_tickers_by_screen(records, payload.require_ethical, payload.require_sharia)
    if not records:
        raise HTTPException(400, "Aucun ticker ne passe les filtres sélectionnés")

    tickers   = [r.ticker for r in records]
    currencies = {r.ticker: r.currency for r in records}

    # Always also fetch benchmark + VIX (EPR5 needs them; harmless otherwise)
    all_tickers = list(set(tickers + [payload.benchmark, "^VIX", "^GSPC"]))
    prices_full = await get_prices(all_tickers, period=payload.period)
    if prices_full.empty:
        raise HTTPException(400, "No price data")

    # Split benchmark from strategy universe
    bench_series = prices_full[payload.benchmark] if payload.benchmark in prices_full.columns else None
    strat_cols   = [c for c in prices_full.columns if c not in (payload.benchmark,)]
    # keep ^VIX + ^GSPC IN the strategy frame so EPR5 can use them
    strat_prices = prices_full[strat_cols]

    eurusd   = await get_fx_rate("USD", "EUR")
    fx_rates = {"USDEUR": eurusd, "EURUSD": 1.0 / eurusd}

    params = StrategyParams(
        initial_capital      = payload.initial_capital,
        monthly_contribution = payload.monthly_contribution,
        broker               = payload.broker,
        account_type         = payload.account_type,
        rebalance_frequency  = payload.rebalance_frequency,
        max_position_pct     = payload.max_position_pct,
        stop_loss_pct        = payload.stop_loss_pct,
        custom               = payload.custom_params,
    )

    engine = BacktestEngine(strategy, strat_prices, currencies, fx_rates, params, bench_series)
    result = engine.run()

    bench_returns = bench_series.pct_change().dropna() if bench_series is not None else None
    return build_tearsheet(result, benchmark_returns=bench_returns)


@app.post("/api/backtest/pdf")
async def backtest_pdf(payload: BacktestIn):
    tearsheet = await run_backtest(payload)
    pdf_bytes = generate_pdf(tearsheet)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="rapport_{payload.strategy}_{date.today()}.pdf"'},
    )


# ─── Monte Carlo ─────────────────────────────────────────────────────────────

@app.post("/api/montecarlo")
async def monte_carlo(payload: MonteCarloIn):
    df = await get_prices([payload.ticker], period=payload.period)
    if df.empty:
        raise HTTPException(400, "No data")
    series = df[payload.ticker].dropna()
    res = run_simulation(series, payload.initial_capital, payload.n_paths,
                         payload.n_days, payload.method)
    return {
        "final_values_summary": {
            "p5": res.percentile_5, "p25": res.percentile_25,
            "median": res.median, "p75": res.percentile_75, "p95": res.percentile_95,
        },
        "prob_loss": res.prob_loss, "var_95": res.var_95,
        "cvar_95":   res.cvar_95,   "expected_return": res.expected_return,
        "paths_sample": res.paths_sample.tolist(),
    }


# ─── Signals & rebalance ─────────────────────────────────────────────────────

@app.post("/api/signals/daily")
async def daily_signals(payload: TickerListIn):
    return {"signals": await compute_daily_signals(payload.tickers)}


@app.post("/api/signals/rebalance")
async def rebalance(payload: RebalanceIn):
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
        payload.positions, prices_eur, payload.target_weights,
        payload.cash_eur, payload.broker,
    )
    return {"orders": orders, "date": str(date.today())}


handler = app
