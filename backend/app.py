from __future__ import annotations

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

    scheduler = AsyncIOScheduler()
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
            import glob
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
                backups = sorted(glob.glob(f"{backup_dir}/ethical_finance_*.sql.gz"))
                for old_backup in backups[:-7]:
                    os.remove(old_backup)
                    log.info("Deleted old backup: %s", old_backup)
                log.info("PG backup complete: %s", backup_file)
            except Exception as e:
                log.warning("PG backup error: %s", e)

        # Drive sync — import OHLCV depuis Google Drive à 23h30 UTC
        async def drive_sync_job():
            try:
                from backend.core.drive_sync import trigger_drive_sync

                log.info("Drive sync job started")
                result = await trigger_drive_sync()
                log.info("Drive sync job complete: %s", result)
            except Exception as e:
                log.warning("Drive sync job error: %s", e)

        scheduler.add_job(drive_sync_job, "cron", hour=23, minute=30, timezone="UTC")
        scheduler.add_job(pg_backup_job, "cron", hour=23, minute=0, timezone="UTC")

        # FMP — mise à jour fondamentaux non-US à 22h30 UTC
        async def fmp_fundamentals_job():
            try:
                from backend.core.fmp import upsert_fmp_fundamentals
                from backend.core.loader import CAC40_TICKERS
                from backend.core.twelve_data import ALL_EXTENDED_TICKERS

                all_non_us = list(set(CAC40_TICKERS + ALL_EXTENDED_TICKERS[:50]))
                log.info("FMP job started — %d tickers", len(all_non_us))
                n = await upsert_fmp_fundamentals(all_non_us)
                log.info("FMP job complete — %d tickers updated", n)
            except Exception as e:
                log.warning("FMP job error: %s", e)

        scheduler.add_job(fmp_fundamentals_job, "cron", hour=22, minute=30, timezone="UTC")

        # Signaux journaliers — calcul + persistance pour tous les tickers à 20h30 UTC
        async def daily_signals_job():
            try:
                import os

                import sqlalchemy as sa

                from backend.signals.daily import compute_daily_signals

                database_url = os.environ.get("DATABASE_URL", "")
                sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
                engine = sa.create_engine(sync_url, pool_pre_ping=True)

                # Récupérer tous les tickers en base
                with engine.connect() as conn:
                    rows = conn.execute(
                        sa.text("SELECT DISTINCT ticker FROM ticker_fundamentals ORDER BY ticker")
                    ).fetchall()
                tickers = [r[0] for r in rows]
                log.info("Daily signals job — %d tickers", len(tickers))

                STRATEGIES = [
                    "epr5",
                    "momentum",
                    "mean_reversion",
                    "sma_crossover",
                    "dual_momentum",
                    "buy_hold",
                ]
                WEIGHTS = {
                    "epr5": {
                        "sma": 0.20,
                        "rsi": 0.20,
                        "macd": 0.20,
                        "momentum": 0.20,
                        "sentiment": 0.20,
                    },
                    "momentum": {
                        "sma": 0.10,
                        "rsi": 0.15,
                        "macd": 0.20,
                        "momentum": 0.35,
                        "sentiment": 0.20,
                    },
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
                    "buy_hold": {
                        "sma": 0.20,
                        "rsi": 0.20,
                        "macd": 0.20,
                        "momentum": 0.15,
                        "sentiment": 0.25,
                    },
                }

                # Traiter par batch de 50
                for strategy in STRATEGIES:
                    weights = WEIGHTS[strategy]

                    def norm(v):
                        return (v + 1) / 2.0

                    for i in range(0, len(tickers), 50):
                        batch = tickers[i : i + 50]
                        try:
                            raw = await compute_daily_signals(batch)
                            pool = app.state.pool
                            if not pool:
                                continue
                            async with pool.acquire() as conn:
                                for s in raw:
                                    ind = s.get("indicators", {})
                                    composite = round(
                                        norm(ind.get("sma_crossover", 0)) * weights["sma"]
                                        + norm(ind.get("rsi", 0)) * weights["rsi"]
                                        + norm(ind.get("macd", 0)) * weights["macd"]
                                        + norm(ind.get("momentum", 0)) * weights["momentum"]
                                        + norm(ind.get("sentiment", 0)) * weights["sentiment"],
                                        4,
                                    )
                                    await conn.execute(
                                        """
                                        INSERT INTO signals_history
                                            (ticker, date, strategy_id, signal_buy, signal_sell,
                                             rf_score, lstm_score, sentiment_score, fundamental_score,
                                             technical_score, composite_score)
                                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                                        ON CONFLICT (ticker, date, strategy_id) DO UPDATE SET
                                            composite_score=EXCLUDED.composite_score,
                                            signal_buy=EXCLUDED.signal_buy,
                                            signal_sell=EXCLUDED.signal_sell
                                    """,
                                        s["ticker"],
                                        s["date"],
                                        strategy,
                                        composite >= 0.60,
                                        composite <= 0.40,
                                        norm(ind.get("sma_crossover", 0)),
                                        norm(ind.get("macd", 0)),
                                        norm(ind.get("sentiment", 0)),
                                        norm(ind.get("rsi", 0)),
                                        norm(ind.get("momentum", 0)),
                                        composite,
                                    )
                        except Exception as e:
                            log.warning("signals batch error %s: %s", strategy, e)
                log.info("Daily signals job complete")
            except Exception as e:
                log.warning("Daily signals job error: %s", e)

        scheduler.add_job(daily_signals_job, "cron", hour=20, minute=30, timezone="UTC")

        # Intraday 1h — fetch Twelve Data toutes les heures (marché ouvert)
        async def intraday_job():
            try:
                import os

                import httpx
                import sqlalchemy as sa

                api_key = os.environ.get("TWELVE_DATA_API_KEY", "")
                if not api_key:
                    return

                database_url = os.environ.get("DATABASE_URL", "")
                sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
                engine = sa.create_engine(sync_url, pool_pre_ping=True)

                # Récupérer les tickers actifs (top 50 par market cap)
                with engine.connect() as conn:
                    rows = conn.execute(sa.text("""
                        SELECT ticker FROM ticker_fundamentals
                        WHERE universe IN ('sp500', 'cac40', 'etf_broad', 'etf_precious_metals')
                        ORDER BY market_cap DESC NULLS LAST
                        LIMIT 50
                    """)).fetchall()
                tickers = [r[0] for r in rows]

                # Normalise ticker pour Twelve Data
                def norm(t):
                    for suffix, exchange in [
                        (".PA", "XPAR"),
                        (".L", "XLON"),
                        (".DE", "XETR"),
                        (".AS", "XAMS"),
                    ]:
                        if t.endswith(suffix):
                            return t.replace(suffix, ""), exchange
                    return t, ""

                inserted = 0
                async with httpx.AsyncClient(timeout=10) as client:
                    for ticker in tickers:
                        sym, exchange = norm(ticker)
                        params = {
                            "symbol": sym,
                            "interval": "1h",
                            "outputsize": 2,
                            "apikey": api_key,
                        }
                        if exchange:
                            params["exchange"] = exchange
                        try:
                            r = await client.get(
                                "https://api.twelvedata.com/time_series", params=params
                            )
                            data = r.json()
                            if "values" not in data:
                                continue
                            with engine.connect() as conn:
                                for v in data["values"]:
                                    conn.execute(
                                        sa.text("""
                                        INSERT INTO ohlcv_intraday (ticker, datetime, open, high, low, close, volume, interval)
                                        VALUES (:ticker, :dt, :open, :high, :low, :close, :volume, '1h')
                                        ON CONFLICT (ticker, datetime, interval) DO UPDATE SET
                                            close=EXCLUDED.close, volume=EXCLUDED.volume
                                    """),
                                        {
                                            "ticker": ticker,
                                            "dt": v["datetime"],
                                            "open": float(v["open"]),
                                            "high": float(v["high"]),
                                            "low": float(v["low"]),
                                            "close": float(v["close"]),
                                            "volume": int(v.get("volume") or 0),
                                        },
                                    )
                                    conn.commit()
                                    inserted += 1
                            import asyncio

                            await asyncio.sleep(0.5)  # 800 req/jour = 1 req/2s
                        except Exception as e:
                            log.debug("intraday_job error %s: %s", ticker, e)

                log.info("Intraday job complete — %d rows inserted", inserted)
            except Exception as e:
                log.warning("Intraday job error: %s", e)

        scheduler.add_job(intraday_job, "interval", hours=1, timezone="UTC")
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
