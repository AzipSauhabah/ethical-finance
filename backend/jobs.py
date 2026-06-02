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
        import sqlalchemy as sa
        from backend.core.db import engine
        from backend.core.sec_edgar import upsert_sec_fundamentals

        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT ticker FROM ticker_fundamentals WHERE universe='sp500' ORDER BY sec_updated_at ASC NULLS FIRST"
            )).fetchall()
        tickers = [r[0] for r in rows]
        log.info("SEC EDGAR job started — %d tickers (DB)", len(tickers))
        n = await upsert_sec_fundamentals(tickers)
        log.info("SEC EDGAR job complete — %d tickers updated", n)
    except Exception as e:
        log.warning("SEC EDGAR job error: %s", e)


async def job_macro_series() -> None:
    """Update macro series: FRED + INSEE BDM — daily/weekly."""
    try:
        import os
        from backend.core.db import engine
        from backend.core.macro_collector import upsert_fred_all, upsert_insee_all
        fred_key = os.environ.get("FRED_API_KEY", "")
        n_fred = await upsert_fred_all(engine, api_key=fred_key)
        n_insee = await upsert_insee_all(engine)
        from backend.core.macro_collector import fetch_dvf_csv, fetch_gdelt_sentiment
        n_dvf = await fetch_dvf_csv(engine)
        n_gdelt = await fetch_gdelt_sentiment(engine)
        log.info("Macro job complete — FRED: %d, FRED_FR: %d, DVF: %d, GDELT: %d", n_fred, n_insee, n_dvf, n_gdelt)
    except Exception as e:
        log.warning("Macro job error: %s", e)


async def job_implied_vol() -> None:
    """Update implied volatility for SP500 + CAC40 tickers — daily."""
    try:
        import sqlalchemy as sa
        from backend.core.db import engine
        from backend.core.macro_collector import upsert_implied_vol_all
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT ticker FROM ticker_fundamentals WHERE universe IN ('sp500','cac40') ORDER BY market_cap DESC NULLS LAST LIMIT 100"
            )).fetchall()
        tickers = [r[0] for r in rows]
        n = await upsert_implied_vol_all(tickers, engine)
        log.info("Implied vol job complete — %d rows for %d tickers", n, len(tickers))
    except Exception as e:
        log.warning("Implied vol job error: %s", e)


async def job_insider_signals() -> None:
    """Update insider signals from SEC Form 4 — daily."""
    try:
        import sqlalchemy as sa
        from backend.core.db import engine
        from backend.core.macro_collector import fetch_insider_sec
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT ticker FROM ticker_fundamentals WHERE universe='sp500' ORDER BY market_cap DESC NULLS LAST LIMIT 50"
            )).fetchall()
        tickers = [r[0] for r in rows]
        total = 0
        for t in tickers:
            total += await fetch_insider_sec(t, engine)
        log.info("Insider signals job complete — %d records for %d tickers", total, len(tickers))
    except Exception as e:
        log.warning("Insider signals job error: %s", e)


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


# ─── ESEF fundamentals (CAC40 + EU) ─────────────────────────────────────────

async def job_esef_fundamentals() -> None:
    """Update EU fundamentals from ESEF filings weekly (Monday 04h00 UTC).
    Peuple interest_bearing_debt, total_assets, total_equity depuis filings.xbrl.org.
    """
    try:
        import asyncpg, os
        from backend.core.esef_fundamentals import fetch_fundamentals_esef
        from backend.core.loader import CAC40_TICKERS
        import sqlalchemy as sa

        db = await asyncpg.connect(os.environ["DATABASE_URL"])
        engine = sa.create_engine(
            os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
        )
        updated = 0
        for ticker in CAC40_TICKERS:
            try:
                d = await fetch_fundamentals_esef(ticker, db_conn=db)
                if not d or not d.get("interest_bearing_debt"):
                    continue
                with engine.begin() as conn:
                    conn.execute(sa.text("""
                        UPDATE ticker_fundamentals SET
                            interest_bearing_debt = :ibd,
                            short_term_debt       = :std,
                            long_term_debt        = :ltd,
                            total_assets          = COALESCE(NULLIF(total_assets, 0), :ta),
                            total_equity          = COALESCE(NULLIF(total_equity, 0), :te),
                            interest_expense      = COALESCE(NULLIF(interest_expense, 0), :ie),
                            interest_income       = COALESCE(NULLIF(interest_income, 0), :ii),
                            total_revenue         = COALESCE(NULLIF(total_revenue, 0), :tr),
                            total_debt            = COALESCE(NULLIF(total_debt, 0), :td)
                        WHERE ticker = :ticker
                    """), {
                        "ticker": ticker,
                        "ibd": d.get("interest_bearing_debt", 0),
                        "std": d.get("short_term_debt", 0),
                        "ltd": d.get("long_term_debt", 0),
                        "ta":  d.get("total_assets", 0),
                        "te":  d.get("total_equity", 0),
                        "ie":  d.get("interest_expense", 0),
                        "ii":  d.get("interest_income", 0),
                        "tr":  d.get("total_revenue", 0),
                        "td":  d.get("total_debt", 0),
                    })
                updated += 1
            except Exception as e:
                log.warning("ESEF job error for %s: %s", ticker, e)
        await db.close()
        log.info("ESEF job complete — %d tickers updated", updated)
    except Exception as e:
        log.warning("ESEF job error: %s", e)


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
                    s["ticker"], __import__("datetime").date.fromisoformat(s["date"]) if isinstance(s["date"], str) else s["date"], strategy,
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
    """Download and persist OHLCV data Mon-Fri at 20h00 UTC via Twelve Data."""
    try:
        import sqlalchemy as sa
        from datetime import date, timedelta
        from backend.core.db import engine

        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT DISTINCT ticker FROM ticker_fundamentals "
                "WHERE universe IN ('sp500','cac40','etf_broad','etf_precious_metals') "
                "ORDER BY ticker"
            )).fetchall()
        all_tickers = [r[0] for r in rows]

        end = date.today()
        start = end - timedelta(days=20)  # rattrape jusqu'à 3 semaines de retard
        inserted = 0

        # Batch par 8 tickers — 1 crédit API pour 8 tickers
        from backend.core.twelve_data import fetch_ohlcv_batch
        BATCH = 8
        import time as _time
        for i in range(0, len(all_tickers), BATCH):
            batch = all_tickers[i:i+BATCH]
            try:
                results = fetch_ohlcv_batch(batch, start=start, end=end)
                for ticker, df in results.items():
                    if df is None or df.empty:
                        continue
                    with engine.begin() as conn:
                        for dt_idx, row in df.iterrows():
                            try:
                                conn.execute(sa.text("""
                                    INSERT INTO ohlcv (ticker, date, open, high, low, close, adj_close, volume)
                                    VALUES (:ticker, :dt, :open, :high, :low, :close, :adj, :volume)
                                    ON CONFLICT (ticker, date) DO UPDATE SET
                                        open=EXCLUDED.open, high=EXCLUDED.high,
                                        low=EXCLUDED.low, close=EXCLUDED.close,
                                        adj_close=EXCLUDED.adj_close, volume=EXCLUDED.volume
                                """), {
                                    "ticker": ticker,
                                    "dt": str(dt_idx)[:10],
                                    "open":   float(row.get("open") or 0),
                                    "high":   float(row.get("high") or 0),
                                    "low":    float(row.get("low") or 0),
                                    "close":  float(row.get("close") or 0),
                                    "adj":    float(row.get("close") or 0),
                                    "volume": int(row.get("volume") or 0),
                                })
                                inserted += 1
                            except Exception as e:
                                log.debug("OHLCV insert error %s: %s", ticker, e)
            except Exception as e:
                log.debug("OHLCV batch error %s: %s", batch, e)
            _time.sleep(8)  # Twelve Data: max 8 req/min

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

        import sqlalchemy as sa2
        from backend.core.db import engine as db_engine
        with db_engine.connect() as conn2:
            rows2 = conn2.execute(sa.text(
                "SELECT ticker FROM ticker_fundamentals WHERE universe='sp500' ORDER BY market_cap DESC NULLS LAST LIMIT 50"
            )).fetchall()
        tickers = [r[0] for r in rows2]
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
