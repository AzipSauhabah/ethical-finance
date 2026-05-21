"""
:file: backend/jobs.py
:brief: APScheduler jobs extracted from _startup() to reduce cognitive complexity.
        Each job is a standalone async function registered in app.py.
"""

from __future__ import annotations

import glob
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)

_PG_SCHEME = "postgresql://"
_PG_PSYCOPG2_SCHEME = "postgresql+psycopg2://"


# ─── SEC EDGAR ───────────────────────────────────────────────────────────────

async def job_sec_fundamentals() -> None:
    """Update SP500 fundamentals from SEC EDGAR at 22h00 UTC."""
    try:
        from backend.core.loader import SP500_TICKERS
        from backend.core.sec_edgar import upsert_sec_fundamentals

        log.info("SEC EDGAR job started — %d tickers", len(SP500_TICKERS))
        n = await upsert_sec_fundamentals(SP500_TICKERS[:100])
        log.info("SEC EDGAR job complete — %d tickers updated", n)
    except Exception as e:
        log.warning("SEC EDGAR job error: %s", e)


# ─── PostgreSQL backup ───────────────────────────────────────────────────────

async def job_pg_backup() -> None:
    """Daily PostgreSQL backup at 23h00 UTC, 7-day retention."""
    import asyncio

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
        backups = sorted(glob.glob(f"{backup_dir}/ethical_finance_*.sql.gz"))
        for old_backup in backups[:-7]:
            os.remove(old_backup)
            log.info("Deleted old backup: %s", old_backup)
        log.info("PG backup complete: %s", backup_file)
    except Exception as e:
        log.warning("PG backup error: %s", e)


# ─── Google Drive sync ───────────────────────────────────────────────────────

async def job_drive_sync() -> None:
    """Sync OHLCV from Google Drive at 23h30 UTC."""
    try:
        from backend.core.drive_sync import trigger_drive_sync

        log.info("Drive sync job started")
        result = await trigger_drive_sync()
        log.info("Drive sync job complete: %s", result)
    except Exception as e:
        log.warning("Drive sync job error: %s", e)


# ─── FMP fundamentals ────────────────────────────────────────────────────────

async def job_fmp_fundamentals() -> None:
    """Update non-US fundamentals from FMP at 22h30 UTC."""
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


# ─── Daily signals ───────────────────────────────────────────────────────────

def _norm(v: float) -> float:
    return (v + 1) / 2.0


async def job_daily_signals(app_state) -> None:  # noqa: ANN001
    """Compute and persist daily signals for all tickers at 20h30 UTC."""
    try:
        import sqlalchemy as sa

        from backend.signals.daily import compute_daily_signals

        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)

        STRATEGIES = ["epr5", "momentum", "mean_reversion", "sma_crossover", "dual_momentum", "buy_hold"]
        WEIGHTS = {
            "epr5":          {"sma": 0.20, "rsi": 0.20, "macd": 0.20, "momentum": 0.20, "sentiment": 0.20},
            "momentum":      {"sma": 0.10, "rsi": 0.15, "macd": 0.20, "momentum": 0.35, "sentiment": 0.20},
            "mean_reversion":{"sma": 0.15, "rsi": 0.35, "macd": 0.15, "momentum": 0.10, "sentiment": 0.25},
            "sma_crossover": {"sma": 0.55, "rsi": 0.10, "macd": 0.15, "momentum": 0.10, "sentiment": 0.10},
            "dual_momentum": {"sma": 0.10, "rsi": 0.15, "macd": 0.15, "momentum": 0.30, "sentiment": 0.30},
            "buy_hold":      {"sma": 0.20, "rsi": 0.20, "macd": 0.20, "momentum": 0.15, "sentiment": 0.25},
        }

        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(sa.text("SELECT DISTINCT ticker FROM ticker_fundamentals ORDER BY ticker"))
            tickers = [r[0] for r in rows]

        log.info("Daily signals job — %d tickers", len(tickers))

        for strategy in STRATEGIES:
            weights = WEIGHTS[strategy]
            for i in range(0, len(tickers), 50):
                batch = tickers[i: i + 50]
                await _persist_signals_batch(app_state, batch, strategy, weights)

        log.info("Daily signals job complete")
    except Exception as e:
        log.warning("Daily signals job error: %s", e)


async def _persist_signals_batch(app_state, batch: list[str], strategy: str, weights: dict) -> None:  # noqa: ANN001
    """Compute and persist signals for a batch of tickers."""
    try:
        from backend.signals.daily import compute_daily_signals

        raw = await compute_daily_signals(batch)
        pool = app_state.pool
        if not pool:
            return
        async with pool.acquire() as conn:
            for s in raw:
                ind = s.get("indicators", {})
                composite = round(
                    _norm(ind.get("sma_crossover", 0)) * weights["sma"]
                    + _norm(ind.get("rsi", 0)) * weights["rsi"]
                    + _norm(ind.get("macd", 0)) * weights["macd"]
                    + _norm(ind.get("momentum", 0)) * weights["momentum"]
                    + _norm(ind.get("sentiment", 0)) * weights["sentiment"],
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
                    s["ticker"], s["date"], strategy,
                    composite >= 0.60, composite <= 0.40,
                    _norm(ind.get("sma_crossover", 0)),
                    _norm(ind.get("macd", 0)),
                    _norm(ind.get("sentiment", 0)),
                    _norm(ind.get("rsi", 0)),
                    _norm(ind.get("momentum", 0)),
                    composite,
                )
    except Exception as e:
        log.warning("signals batch error %s: %s", strategy, e)


# ─── OHLCV update ────────────────────────────────────────────────────────────

async def job_ohlcv_update() -> None:
    """Download and persist OHLCV data Mon-Fri at 20h00 UTC."""
    try:
        import asyncio
        import time

        import pandas as pd
        import sqlalchemy as sa
        import yfinance as yf
        from datetime import date, timedelta

        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)

        from backend.core.loader import SP500_TICKERS, CAC40_TICKERS
        from backend.core.twelve_data import ALL_EXTENDED_TICKERS

        all_tickers = list(set(SP500_TICKERS + CAC40_TICKERS + ALL_EXTENDED_TICKERS))
        end = date.today()
        start = end - timedelta(days=7)
        inserted = 0

        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        loop = asyncio.get_event_loop()

        def _download_and_insert() -> None:
            nonlocal inserted
            for ticker in all_tickers:
                try:
                    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
                    if df.empty:
                        continue
                    with engine.begin() as conn:
                        for dt, row in df.iterrows():
                            conn.execute(sa.text("""
                                INSERT INTO ohlcv (ticker, date, open, high, low, close, volume)
                                VALUES (:ticker, :dt, :open, :high, :low, :close, :volume)
                                ON CONFLICT (ticker, date) DO UPDATE SET
                                    open=EXCLUDED.open, high=EXCLUDED.high,
                                    low=EXCLUDED.low, close=EXCLUDED.close,
                                    volume=EXCLUDED.volume
                            """), {
                                "ticker": ticker,
                                "dt": dt.date(),
                                "open": float(row["Open"]),
                                "high": float(row["High"]),
                                "low": float(row["Low"]),
                                "close": float(row["Close"]),
                                "volume": int(row["Volume"] or 0),
                            })
                            inserted += 1
                except Exception as e:
                    log.debug("OHLCV error %s: %s", ticker, e)
                time.sleep(0.05)

        await loop.run_in_executor(None, _download_and_insert)
        log.info("OHLCV job complete — %d rows inserted", inserted)
    except Exception as e:
        log.warning("OHLCV job error: %s", e)


# ─── Intraday ────────────────────────────────────────────────────────────────

async def job_intraday() -> None:
    """Fetch intraday data from Twelve Data every hour."""
    try:
        import asyncio

        import httpx
        import sqlalchemy as sa

        api_key = os.environ.get("TWELVE_DATA_API_KEY", "")
        if not api_key:
            return

        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace(_PG_SCHEME, _PG_PSYCOPG2_SCHEME)

        from backend.core.loader import SP500_TICKERS, CAC40_TICKERS

        tickers = list(set(SP500_TICKERS[:50] + CAC40_TICKERS[:20]))
        engine = sa.create_engine(sync_url, pool_pre_ping=True)
        inserted = 0

        for ticker in tickers:
            try:
                url = (
                    f"https://api.twelvedata.com/time_series"
                    f"?symbol={ticker}&interval=1h&outputsize=24&apikey={api_key}"
                )
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url)
                    data = resp.json()

                values = data.get("values", [])
                with engine.begin() as conn:
                    for v in values:
                        conn.execute(sa.text("""
                            INSERT INTO ohlcv_intraday
                                (ticker, dt, open, high, low, close, volume)
                            VALUES (:ticker, :dt, :open, :high, :low, :close, :volume)
                            ON CONFLICT (ticker, dt) DO UPDATE SET
                                open=EXCLUDED.open, high=EXCLUDED.high,
                                low=EXCLUDED.low, close=EXCLUDED.close,
                                volume=EXCLUDED.volume
                        """), {
                            "ticker": ticker,
                            "dt": v["datetime"],
                            "open": float(v["open"]),
                            "high": float(v["high"]),
                            "low": float(v["low"]),
                            "close": float(v["close"]),
                            "volume": int(v.get("volume") or 0),
                        })
                        inserted += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                log.debug("intraday_job error %s: %s", ticker, e)

        log.info("Intraday job complete — %d rows inserted", inserted)
    except Exception as e:
        log.warning("Intraday job error: %s", e)
