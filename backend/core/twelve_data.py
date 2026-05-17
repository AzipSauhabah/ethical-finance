"""
:file: backend/core/twelve_data.py
:brief: Client Twelve Data API — alternative à yfinance sans rate-limit.

Plan gratuit : 800 requêtes/jour
Couvre : 70+ bourses mondiales (US, UK, EU, JP, AU, CN, ZA, NO, SE, etc.)

Univers supportés :
  - SP500 (NYSE, NASDAQ)
  - CAC40 (Euronext Paris)
  - MSCI World (toutes bourses)
  - UK (LSE)
  - Australie (ASX)
  - Japon (TSE)
  - Chine (SSE, SZSE)
  - Afrique du Sud (JSE)
  - Nordiques (OMX Stockholm, Oslo, Helsinki, Copenhagen)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.twelvedata.com"
RATE_LIMIT_SLEEP = 0.5  # 800 req/jour = ~0.5s entre requêtes pour rester safe


def _get_api_key() -> str:
    key = os.environ.get("TWELVE_DATA_API_KEY", "")
    if not key:
        raise ValueError("TWELVE_DATA_API_KEY non défini dans .env")
    return key


# ─── Mapping ticker yfinance → Twelve Data ───────────────────────────────────

def _normalize_ticker(ticker: str) -> tuple[str, str]:
    """
    Convertit un ticker yfinance en ticker Twelve Data + exchange.
    
    Returns:
        (symbol, exchange) pour l'API Twelve Data
    """
    # Indices — Twelve Data utilise des symboles différents
    index_map = {
        "^GSPC": ("SPX", "NYSE"),
        "^FCHI": ("CAC40", "XPAR"),
        "^GDAXI": ("DAX", "XETR"),
        "^STOXX50E": ("SX5E", "XEUR"),
        "^VIX": ("VIX", "CBOE"),
        "^N225": ("N225", "XTKS"),
        "^FTSE": ("FTSE", "XLON"),
        "EURUSD=X": ("EUR/USD", ""),
        "USDEUR=X": ("USD/EUR", ""),
    }
    if ticker in index_map:
        return index_map[ticker]

    # Tickers avec suffixe de bourse
    suffix_exchange = {
        ".PA": ("", "XPAR"),    # Euronext Paris
        ".AS": ("", "XAMS"),    # Euronext Amsterdam
        ".DE": ("", "XETR"),    # XETRA (Deutsche Börse)
        ".L": ("", "XLON"),     # London Stock Exchange
        ".SW": ("", "XSWX"),    # SIX Swiss Exchange
        ".MI": ("", "XMIL"),    # Borsa Italiana
        ".MC": ("", "XMAD"),    # Bolsa de Madrid
        ".AX": ("", "XASX"),    # ASX (Australie)
        ".T": ("", "XTKS"),     # Tokyo Stock Exchange
        ".HK": ("", "XHKG"),    # Hong Kong Stock Exchange
        ".SS": ("", "XSHG"),    # Shanghai Stock Exchange
        ".SZ": ("", "XSHE"),    # Shenzhen Stock Exchange
        ".KS": ("", "XKRX"),    # Korea Stock Exchange
        ".NS": ("", "XNSE"),    # National Stock Exchange India
        ".SA": ("", "BVMF"),    # B3 (Brésil)
        ".JO": ("", "XJSE"),    # JSE (Afrique du Sud)
        ".ST": ("", "XSTO"),    # Nasdaq Stockholm
        ".OL": ("", "XOSL"),    # Oslo Børs
        ".HE": ("", "XHEL"),    # Nasdaq Helsinki
        ".CO": ("", "XCSE"),    # Nasdaq Copenhagen
        ".TO": ("", "XTSE"),    # Toronto Stock Exchange
        ".BR": ("", "XBRU"),    # Euronext Brussels
        ".LS": ("", "XLIS"),    # Euronext Lisbon
        ".WA": ("", "XWAR"),    # Warsaw Stock Exchange
    }

    for suffix, (_, exchange) in suffix_exchange.items():
        if ticker.endswith(suffix):
            symbol = ticker[: -len(suffix)]
            return symbol, exchange

    # US par défaut
    return ticker, "NASDAQ"


# ─── Fetch OHLCV ─────────────────────────────────────────────────────────────


def fetch_ohlcv(
    ticker: str,
    start: date,
    end: date,
    interval: str = "1day",
) -> pd.DataFrame:
    """
    Télécharge les données OHLCV depuis Twelve Data.

    Args:
        ticker: symbole yfinance (ex: AAPL, MC.PA, HSBA.L)
        start: date de début
        end: date de fin
        interval: "1day", "1week", "1month"

    Returns:
        DataFrame avec colonnes Open, High, Low, Close, Adj Close, Volume
        ou DataFrame vide si erreur
    """
    api_key = _get_api_key()
    symbol, exchange = _normalize_ticker(ticker)

    params = {
        "symbol": symbol,
        "interval": interval,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "apikey": api_key,
        "format": "JSON",
        "order": "ASC",
    }
    if exchange:
        params["exchange"] = exchange

    try:
        r = requests.get(f"{BASE_URL}/time_series", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        if data.get("status") == "error":
            log.warning("Twelve Data error for %s: %s", ticker, data.get("message"))
            return pd.DataFrame()

        values = data.get("values", [])
        if not values:
            log.debug("No data from Twelve Data for %s", ticker)
            return pd.DataFrame()

        df = pd.DataFrame(values)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        df = df.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        })

        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "Volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

        df["Adj Close"] = df["Close"]  # Twelve Data n'a pas l'adj close gratuit

        log.info("Twelve Data: %d rows for %s", len(df), ticker)
        return df

    except Exception as e:
        log.warning("Twelve Data fetch error for %s: %s", ticker, e)
        return pd.DataFrame()


# ─── Fetch fundamentals ───────────────────────────────────────────────────────


def fetch_fundamentals_twelve(ticker: str) -> dict | None:
    """
    Récupère les statistiques de base depuis Twelve Data.
    Disponible sur le plan gratuit : price, market_cap, beta, dividend_yield.

    Args:
        ticker: symbole yfinance

    Returns:
        dict avec les fondamentaux ou None
    """
    api_key = _get_api_key()
    symbol, exchange = _normalize_ticker(ticker)

    params = {
        "symbol": symbol,
        "apikey": api_key,
    }
    if exchange:
        params["exchange"] = exchange

    try:
        r = requests.get(f"{BASE_URL}/statistics", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        if data.get("status") == "error":
            return None

        stats = data.get("statistics", {})
        valuations = stats.get("valuations_metrics", {})
        financials = stats.get("financials", {})
        stock_stats = stats.get("stock_statistics", {})

        return {
            "ticker": ticker,
            "market_cap": valuations.get("market_capitalization"),
            "pe_ratio": valuations.get("trailing_pe"),
            "forward_pe": valuations.get("forward_pe"),
            "pb_ratio": valuations.get("price_to_book_mrq"),
            "ev_ebitda": valuations.get("enterprise_to_ebitda"),
            "beta": stock_stats.get("beta"),
            "dividend_yield": stock_stats.get("five_year_average_dividend_yield"),
            "profit_margin": financials.get("profit_margin"),
            "roe": financials.get("return_on_equity_ttm"),
            "roa": financials.get("return_on_assets_ttm"),
            "revenue": financials.get("revenue_ttm"),
            "source": "TWELVE_DATA",
        }
    except Exception as e:
        log.warning("Twelve Data fundamentals error for %s: %s", ticker, e)
        return None


# ─── Nouveaux univers ─────────────────────────────────────────────────────────

# Tickers MSCI World supplémentaires par région
MSCI_WORLD_EXTENDED = {
    "UK": [
        "HSBA.L", "BP.L", "GSK.L", "AZN.L", "ULVR.L", "RIO.L", "BHP.L",
        "SHEL.L", "LSEG.L", "REL.L", "NG.L", "BARC.L", "LLOY.L", "STAN.L",
        "VOD.L", "BT-A.L", "RKT.L", "CPG.L", "IMB.L", "PRU.L",
    ],
    "AU": [
        "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX", "ANZ.AX",
        "WES.AX", "WOW.AX", "MQG.AX", "RIO.AX", "FMG.AX", "TLS.AX",
    ],
    "JP": [
        "7203.T", "6758.T", "9984.T", "6861.T", "8306.T", "9432.T",
        "8316.T", "4063.T", "6367.T", "9433.T", "7267.T", "6902.T",
    ],
    "CH": [
        "NESN.SW", "ROG.SW", "NOVN.SW", "ABBN.SW", "ZURN.SW",
        "CSGN.SW", "UBSG.SW", "SIKA.SW", "LONN.SW", "CFR.SW",
    ],
    "SE": [
        "VOLV-B.ST", "ERIC-B.ST", "SEB-A.ST", "INVE-B.ST", "SAND.ST",
        "ALFA.ST", "ATCO-A.ST", "HM-B.ST", "SWED-A.ST", "TELE2-B.ST",
    ],
    "NO": [
        "EQNR.OL", "DNB.OL", "TEL.OL", "MOWI.OL", "ORKLA.OL",
        "SALM.OL", "YAR.OL", "AKERBP.OL", "NHY.OL", "SGSN.OL",
    ],
    "DK": [
        "NOVO-B.CO", "MAERSK-B.CO", "DSV.CO", "ORSTED.CO", "CARL-B.CO",
        "NFLX.CO", "CHR.CO", "DEMANT.CO", "PNDORA.CO", "COLO-B.CO",
    ],
    "ZA": [
        "NPN.JO", "PRX.JO", "BHP.JO", "AGL.JO", "FSR.JO",
        "SBK.JO", "SOL.JO", "MTN.JO", "NED.JO", "REM.JO",
    ],
}

ALL_EXTENDED_TICKERS = [t for tickers in MSCI_WORLD_EXTENDED.values() for t in tickers]


# ─── Loader intégré dans le scheduler ────────────────────────────────────────


async def load_ticker_twelve(ticker: str, years: int = 20) -> int:
    """
    Charge l'historique d'un ticker depuis Twelve Data et l'insère en DB.
    Utiliser en fallback si yfinance échoue.

    Returns:
        nombre de lignes insérées
    """
    import asyncio
    from backend.core.db import get_last_date, upsert_ohlcv

    loop = asyncio.get_event_loop()

    last = await get_last_date(ticker)
    if last:
        start = last + timedelta(days=1)
        if start >= date.today():
            log.info("%s already up to date (Twelve Data)", ticker)
            return 0
    else:
        start = date(date.today().year - years, 1, 1)

    end = date.today()

    df = await loop.run_in_executor(
        None, lambda: fetch_ohlcv(ticker, start, end)
    )

    if df.empty:
        log.warning("No data from Twelve Data for %s", ticker)
        return 0

    time.sleep(RATE_LIMIT_SLEEP)
    n = await upsert_ohlcv(df, ticker)
    log.info("Twelve Data upserted %d rows for %s", n, ticker)
    return n


async def load_extended_universe(years: int = 10) -> None:
    """
    Charge les tickers MSCI World étendu (UK, AU, JP, CH, SE, NO, DK, ZA)
    depuis Twelve Data.
    """
    import asyncio

    log.info("Loading extended MSCI World universe (%d tickers)", len(ALL_EXTENDED_TICKERS))
    for ticker in ALL_EXTENDED_TICKERS:
        try:
            await load_ticker_twelve(ticker, years=years)
            await asyncio.sleep(RATE_LIMIT_SLEEP)
        except Exception as e:
            log.warning("Extended universe load failed for %s: %s", ticker, e)
    log.info("Extended universe load complete")
