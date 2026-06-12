from __future__ import annotations

# ─── DB URL constants ────────────────────────────────────────────────────────
_PG_SCHEME = "postgresql://"
_PG_PSYCOPG2_SCHEME = "postgresql+psycopg2://"

import logging
import os

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import API_VERSION

log = logging.getLogger(__name__)

app = FastAPI(
    title="Ethical Finance Platform API",
    version=API_VERSION,
    description="Sauhabah — Backtest, signals & reporting engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers v2 ────────────────────────────────────────────────────────────────
from backend.auth.jwt import router as auth_router
from backend.auth.portfolio_routes import router as portfolio_router

app.include_router(auth_router)
app.include_router(portfolio_router)

# Scheduler optionnel — uniquement sur Docker/Fly.io, pas sur Vercel serverless
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(job_defaults={"misfire_grace_time": 3600, "coalesce": True})
    HAS_SCHEDULER = True
except ImportError:
    scheduler = None
    HAS_SCHEDULER = False


_STARTED = False


@app.on_event("startup")
async def _startup() -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    import asyncio

    from backend.core.queue import start_worker
    from backend.strategies.registry import strategy_registry

    strategy_registry.auto_discover()

    # ── Pool asyncpg (auth + portfolio) ──────────────────────────────────────
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        app.state.pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        log.info("asyncpg pool created")
    else:
        app.state.pool = None
        log.warning("DATABASE_URL non définie — routes auth désactivées")

    start_worker()
    log.info("API ready — strategies loaded")

    if HAS_SCHEDULER and scheduler:
        from backend.core.loader import daily_update

        scheduler.add_job(daily_update, "cron", hour=21, minute=0, timezone="UTC")

        from backend.jobs import (
            job_sec_fundamentals, job_pg_backup, job_drive_sync,
            job_fmp_fundamentals, job_daily_signals, job_ohlcv_update, job_intraday,
    job_esef_fundamentals,
    job_macro_series,
    job_implied_vol,
    job_insider_signals,
    job_seed_macro_events,
)

        scheduler.add_job(job_sec_fundamentals, "cron", hour=22, minute=0, timezone="UTC")

        scheduler.add_job(job_drive_sync, "cron", hour=23, minute=30, timezone="UTC")
        scheduler.add_job(job_pg_backup, "cron", hour=23, minute=0, timezone="UTC")

        scheduler.add_job(job_fmp_fundamentals, "cron", hour=22, minute=30, timezone="UTC")
        scheduler.add_job(job_esef_fundamentals, "cron", day_of_week="mon", hour=4, minute=0, timezone="UTC")
        scheduler.add_job(job_macro_series, "cron", hour=6, minute=0, timezone="UTC")
        scheduler.add_job(job_seed_macro_events, "cron", month=1, day=1, hour=0, minute=0, timezone="UTC")  # seed annuel
        scheduler.add_job(job_implied_vol, "cron", hour=21, minute=30, day_of_week="mon-fri", timezone="UTC")
        scheduler.add_job(job_insider_signals, "cron", hour=23, minute=45, timezone="UTC")

        scheduler.add_job(lambda: job_daily_signals(app.state), "cron", hour=20, minute=30, timezone="UTC")

        scheduler.add_job(job_ohlcv_update, "cron", hour=20, minute=0, day_of_week="mon-fri", timezone="UTC")

        # scheduler.add_job(job_intraday, "interval", hours=1, timezone="UTC")  # disabled — économie crédits Basic
        scheduler.start()
        log.info("Scheduler started — OHLCV 21h, SEC 22h, FMP 22h30, Backup 23h, Signals 20h30 UTC")
        asyncio.create_task(_init_and_load())


async def _init_and_load() -> None:
    import asyncio

    from backend.core.db import get_tickers_in_db, init_db
    from backend.core.loader import load_all_tickers

    await asyncio.sleep(5)
    try:
        await init_db()
        tickers_in_db = await get_tickers_in_db()
        if len(tickers_in_db) < 10:
            log.info("First boot — loading full universe")
            await load_all_tickers(years=20)
        else:
            log.info("DB already populated with %d tickers", len(tickers_in_db))
    except Exception as e:
        log.error("DB init failed: %s", e)


@app.on_event("shutdown")
async def _shutdown() -> None:
    if HAS_SCHEDULER and scheduler:
        scheduler.shutdown()
    if hasattr(app.state, "pool") and app.state.pool:
        await app.state.pool.close()
        log.info("asyncpg pool closed")
