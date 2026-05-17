from __future__ import annotations

import logging

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

        # SEC EDGAR — mise à jour fondamentaux SP500 à 22h00 UTC
        async def sec_fundamentals_job():
            try:
                from backend.core.loader import SP500_TICKERS
                from backend.core.sec_edgar import upsert_sec_fundamentals

                log.info("SEC EDGAR job started — %d tickers", len(SP500_TICKERS))
                n = await upsert_sec_fundamentals(SP500_TICKERS[:100])
                log.info("SEC EDGAR job complete — %d tickers updated", n)
            except Exception as e:
                log.warning("SEC EDGAR job error: %s", e)

        scheduler.add_job(sec_fundamentals_job, "cron", hour=22, minute=0, timezone="UTC")

        # Backup PostgreSQL quotidien à 23h00 UTC
        async def pg_backup_job():
            import asyncio
            import os
            from datetime import datetime

            try:
                backup_dir = "/data/backups"
                os.makedirs(backup_dir, exist_ok=True)
                date_str = datetime.now().strftime("%Y%m%d_%H%M")
                backup_file = f"{backup_dir}/ethical_finance_{date_str}.sql.gz"
                proc = await asyncio.create_subprocess_shell(
                    f"pg_dump -U sauhabah -d ethical_finance | gzip > {backup_file}",
                    env={
                        **os.environ,
                        "PGPASSWORD": os.environ.get("POSTGRES_PASSWORD", "sauhabah"),
                    },
                )
                await proc.wait()
                # Garder seulement les 7 derniers backups
                import glob

                backups = sorted(glob.glob(f"{backup_dir}/ethical_finance_*.sql.gz"))
                for old_backup in backups[:-7]:
                    os.remove(old_backup)
                    log.info("Deleted old backup: %s", old_backup)
                log.info("PG backup complete: %s", backup_file)
            except Exception as e:
                log.warning("PG backup error: %s", e)

        scheduler.add_job(pg_backup_job, "cron", hour=23, minute=0, timezone="UTC")
        scheduler.start()
        log.info("Scheduler started — OHLCV 21h, SEC 22h, Backup 23h UTC")
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
