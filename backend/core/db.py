from __future__ import annotations

import logging
import os
from datetime import date

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SYNC_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://").replace(
    "postgresql://", "postgresql+psycopg2://"
)

engine = create_engine(SYNC_URL, pool_size=5, max_overflow=10, echo=False)


class Base(DeclarativeBase):
    pass


class OHLCVRow(Base):
    __tablename__ = "ohlcv"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(sa.String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(sa.Float, nullable=True)
    high: Mapped[float] = mapped_column(sa.Float, nullable=True)
    low: Mapped[float] = mapped_column(sa.Float, nullable=True)
    close: Mapped[float] = mapped_column(sa.Float, nullable=False)
    adj_close: Mapped[float] = mapped_column(sa.Float, nullable=True)
    volume: Mapped[int] = mapped_column(sa.BigInteger, nullable=True)

    __table_args__ = (sa.UniqueConstraint("ticker", "date", name="uq_ticker_date"),)


async def init_db() -> None:
    """Crée les tables si elles n'existent pas."""
    import asyncio

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _init_db_sync)
    log.info("DB initialized")


def _init_db_sync() -> None:
    Base.metadata.create_all(engine)


async def upsert_ohlcv(df: pd.DataFrame, ticker: str) -> int:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _upsert_sync(df, ticker))


def _upsert_sync(df: pd.DataFrame, ticker: str) -> int:
    if df.empty:
        return 0

    rows = []
    for idx, row in df.iterrows():
        rows.append(
            {
                "ticker": ticker,
                "date": idx.date() if hasattr(idx, "date") else idx,
                "open": float(row.get("Open", 0) or 0),
                "high": float(row.get("High", 0) or 0),
                "low": float(row.get("Low", 0) or 0),
                "close": float(row.get("Close", 0) or 0),
                "adj_close": float(row.get("Adj Close", row.get("Close", 0)) or 0),
                "volume": int(row.get("Volume", 0) or 0),
            }
        )

    stmt = sa.dialects.postgresql.insert(OHLCVRow).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "date"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "adj_close": stmt.excluded.adj_close,
            "volume": stmt.excluded.volume,
        },
    )

    with Session(engine) as session:
        session.execute(stmt)
        session.commit()

    return len(rows)


async def get_ohlcv(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _get_ohlcv_sync(tickers, start, end))


def _get_ohlcv_sync(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    with Session(engine) as session:
        result = session.execute(
            sa.select(OHLCVRow)
            .where(
                OHLCVRow.ticker.in_(tickers),
                OHLCVRow.date >= start,
                OHLCVRow.date <= end,
            )
            .order_by(OHLCVRow.date)
        )
        rows = result.scalars().all()

    if not rows:
        return pd.DataFrame()

    data = [{"date": r.date, "ticker": r.ticker, "close": r.adj_close or r.close} for r in rows]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.pivot(index="date", columns="ticker", values="close")
    df.columns.name = None
    return df


async def get_last_date(ticker: str) -> date | None:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _get_last_date_sync(ticker))


def _get_last_date_sync(ticker: str) -> date | None:
    with Session(engine) as session:
        result = session.execute(
            sa.select(sa.func.max(OHLCVRow.date)).where(OHLCVRow.ticker == ticker)
        )
        return result.scalar()


async def get_tickers_in_db() -> list[str]:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_tickers_sync)


def _get_tickers_sync() -> list[str]:
    with Session(engine) as session:
        result = session.execute(sa.select(OHLCVRow.ticker).distinct())
        return [r[0] for r in result.all()]
