from __future__ import annotations

import logging
from datetime import date, timedelta
from functools import partial

import pandas as pd
import yfinance as yf

from backend.core.db import get_last_date, get_tickers_in_db, upsert_ohlcv

log = logging.getLogger(__name__)

# ── Univers de tickers ────────────────────────────────────────────────────────

SP500_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "BRK-B",
    "JPM",
    "UNH",
    "V",
    "XOM",
    "JNJ",
    "WMT",
    "MA",
    "PG",
    "LLY",
    "CVX",
    "HD",
    "MRK",
    "ABBV",
    "PEP",
    "KO",
    "COST",
    "AVGO",
    "MCD",
    "TMO",
    "ACN",
    "BAC",
    "CRM",
    "ABT",
    "NKE",
    "DIS",
    "TXN",
    "NEE",
    "PM",
    "ORCL",
    "DHR",
    "LIN",
    "AMGN",
    "IBM",
    "QCOM",
    "RTX",
    "HON",
    "UPS",
    "SBUX",
    "GS",
    "CAT",
    "INTU",
    "SPGI",
    "AMD",
    "ELV",
    "AXP",
    "ISRG",
    "BLK",
    "DE",
    "SYK",
    "T",
    "GILD",
    "ADI",
    "MDLZ",
    "REGN",
    "PLD",
    "CI",
    "VRTX",
    "ADP",
    "MO",
    "ZTS",
    "MMC",
    "TJX",
    "C",
    "ETN",
    "BSX",
    "NOC",
    "SO",
    "DUK",
    "AON",
    "CME",
    "ITW",
    "PNC",
    "USB",
    "EMR",
    "WM",
    "MCO",
    "F",
    "GM",
    "FDX",
    "NSC",
    "ECL",
    "APD",
    "HCA",
    "ICE",
    "SHW",
    "GD",
    "EW",
    "MSI",
    "CL",
    "OXY",
    "PSA",
    "D",
]

CAC40_TICKERS = [
    "MC.PA",
    "TTE.PA",
    "SAN.PA",
    "OR.PA",
    "AIR.PA",
    "BNP.PA",
    "AXA.PA",
    "SU.PA",
    "DG.PA",
    "RI.PA",
    "KER.PA",
    "CAP.PA",
    "BN.PA",
    "VIE.PA",
    "SGO.PA",
    "ORA.PA",
    "GLE.PA",
    "DSY.PA",
    "HO.PA",
    "STM.PA",
    "EL.PA",
    "RMS.PA",
    "URW.PA",
    "ML.PA",
    "ACA.PA",
    "LR.PA",
    "PUB.PA",
    "TEP.PA",
    "WLN.PA",
    "EN.PA",
    "ATO.PA",
    "CS.PA",
    "SAF.PA",
    "FP.PA",
    "VK.PA",
    "BOL.PA",
    "AI.PA",
    "SW.PA",
    "RNO.PA",
    "MT.AS",
]

ETF_TICKERS = [
    # ETF Broad Market
    "IWDA.AS",
    "VWRL.AS",
    "CSPX.AS",
    "EUNL.DE",
    "VUSA.AS",
    "SWRD.AS",
    # ETF Precious Metals
    "GLD",
    "IAU",
    "SLV",
    "SGOL",
    "PPLT",
    "PALL",
]

MSCI_WORLD_EXTRA = [
    "NESN.SW",
    "ROG.SW",
    "NOVN.SW",
    "ASML.AS",
    "SAP.DE",
    "LVMH.PA",
    "SIE.DE",
    "ALV.DE",
    "MUV2.DE",
    "BAYN.DE",
    "ADS.DE",
    "BMW.DE",
    "VOW3.DE",
    "DBK.DE",
    "BAS.DE",
    "RWE.DE",
    "DTE.DE",
    "ENR.DE",
    "7203.T",
    "6758.T",
    "9984.T",
    "6861.T",
    "8306.T",
    "HSBA.L",
    "BP.L",
    "GSK.L",
    "AZN.L",
    "ULVR.L",
    "RIO.L",
    "BHP.L",
    "^GSPC",
    "^FCHI",
    "^STOXX50E",
    "^VIX",
    "^GDAXI",
    "^N225",
]

ALL_TICKERS = list(set(SP500_TICKERS + CAC40_TICKERS + MSCI_WORLD_EXTRA + ETF_TICKERS))


# ── Chargement ────────────────────────────────────────────────────────────────


def _stooq_ticker(ticker: str) -> str:
    mapping = {
        "GLD": "gld.us",
        "IAU": "iau.us",
        "SLV": "slv.us",
        "SGOL": "sgol.us",
        "PPLT": "pplt.us",
        "PALL": "pall.us",
        "IWDA.AS": "iwda.as",
        "VWRL.AS": "vwrl.as",
        "CSPX.AS": "cspx.as",
        "EUNL.DE": "eunl.de",
        "VUSA.AS": "vusa.as",
        "^GSPC": "^spx",
        "^FCHI": "^cac",
        "^GDAXI": "^dax",
        "^VIX": "^vix",
        "^STOXX50E": "^sx5e",
        "^N225": "^nkx",
    }
    return mapping.get(ticker, ticker.lower().replace("-", ".") + ".us")


def _download_sync(ticker: str, start: date, end: date) -> pd.DataFrame:
    try:
        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
            progress=False,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        if not df.empty:
            return df
    except Exception as e:
        log.warning("yfinance failed for %s: %s — trying stooq", ticker, e)

    try:
        import pandas_datareader as pdr

        stooq_t = _stooq_ticker(ticker)
        df = pdr.get_data_stooq(stooq_t, start=start, end=end)
        if not df.empty:
            df = df.sort_index()
            df["Adj Close"] = df["Close"]
            log.info("stooq fallback OK for %s (%s)", ticker, stooq_t)
            return df
    except Exception as e:
        log.warning("stooq fallback failed for %s: %s", ticker, e)

    return pd.DataFrame()


async def load_ticker(ticker: str, years: int = 20) -> int:
    """Charge l'historique d'un ticker depuis yfinance et l'insère en DB.

    :param ticker: symbole
    :param years: nombre d'années d'historique
    :returns: nombre de lignes insérées
    """
    import asyncio

    loop = asyncio.get_event_loop()

    last = await get_last_date(ticker)
    if last:
        start = last + timedelta(days=1)
        if start >= date.today():
            log.info("%s already up to date", ticker)
            return 0
    else:
        start = date(date.today().year - years, 1, 1)

    end = date.today()
    log.info("Loading %s from %s to %s", ticker, start, end)

    df = await loop.run_in_executor(None, partial(_download_sync, ticker, start, end))
    if df.empty:
        log.warning("No data for %s", ticker)
        return 0

    n = await upsert_ohlcv(df, ticker)
    log.info("Upserted %d rows for %s", n, ticker)
    return n


async def load_all_tickers(years: int = 20) -> None:
    """Charge tous les tickers de l'univers SP500 + CAC40 + MSCI World."""
    import asyncio

    log.info("Starting full universe load (%d tickers)", len(ALL_TICKERS))
    for ticker in ALL_TICKERS:
        try:
            await load_ticker(ticker, years=years)
            await asyncio.sleep(0.5)  # rate limiting yfinance
        except Exception as e:
            log.warning("Failed %s: %s", ticker, e)
    log.info("Full universe load complete")


async def daily_update() -> None:
    """Met à jour tous les tickers présents en DB avec les données du jour."""
    import asyncio

    tickers = await get_tickers_in_db()
    log.info("Daily update for %d tickers", len(tickers))
    for ticker in tickers:
        try:
            await load_ticker(ticker, years=1)
            await asyncio.sleep(0.3)
        except Exception as e:
            log.warning("Daily update failed %s: %s", ticker, e)
    log.info("Daily update complete")
