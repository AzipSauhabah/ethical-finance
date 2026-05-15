from __future__ import annotations

import logging
import os

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

# Scheduler optionnel — uniquement sur Docker/Fly.io, pas sur Vercel serverless
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    HAS_SCHEDULER = True
except ImportError:
    scheduler = None
    HAS_SCHEDULER = False


@app.on_event("startup")
async def _startup() -> None:
    import asyncio
    from backend.core.queue import start_worker

    start_worker()
    log.info("API ready — strategies loaded")

    if HAS_SCHEDULER and scheduler:
        from backend.core.loader import daily_update
        scheduler.add_job(daily_update, "cron", hour=21, minute=0, timezone="UTC")
        scheduler.start()
        log.info("Scheduler started — daily update at 21:00 UTC")
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
