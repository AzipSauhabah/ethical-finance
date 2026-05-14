from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import API_VERSION

log = logging.getLogger(__name__)

app = FastAPI(
    title="Ethical Finance Platform API",
    version=API_VERSION,
    description=" Backtest, signals & reporting engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def _startup() -> None:
    import asyncio
    from backend.core.db import init_db
    from backend.core.loader import daily_update, load_all_tickers

    # Initialise les tables
    await init_db()

    # Cron job quotidien à 22h CET
    scheduler.add_job(daily_update, "cron", hour=21, minute=0, timezone="UTC")
    scheduler.start()
    log.info("Scheduler started — daily update at 21:00 UTC")

    # Charge l'univers complet en arrière-plan au premier démarrage
    asyncio.create_task(_initial_load())


async def _initial_load() -> None:
    from backend.core.db import get_tickers_in_db
    from backend.core.loader import load_all_tickers

    tickers_in_db = await get_tickers_in_db()
    if len(tickers_in_db) < 10:
        log.info("First boot — loading full universe (this takes ~10 min)")
        await load_all_tickers(years=20)
    else:
        log.info("DB already populated with %d tickers", len(tickers_in_db))


@app.on_event("shutdown")
async def _shutdown() -> None:
    scheduler.shutdown()
