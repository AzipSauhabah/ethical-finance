"""
backend/core/macro_collector.py
Collecteurs alternative data : FRED, INSEE BDM, CBOE VIX, Google Trends
"""
from __future__ import annotations
import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

log = logging.getLogger(__name__)

# ── FRED (St Louis Fed) ───────────────────────────────────────────────────────
FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_API  = "https://api.stlouisfed.org/fred/series/observations"

FRED_SERIES = {
    # Macro US
    "UNRATE":    ("Unemployment Rate", "monthly", "%"),
    "CPIAUCSL":  ("CPI All Items", "monthly", "index"),
    "CPILFESL":  ("Core CPI ex Food/Energy", "monthly", "index"),
    "RSAFS":     ("Retail Sales", "monthly", "USD M"),
    "UMCSENT":   ("U. Michigan Consumer Sentiment", "monthly", "index"),
    "ICSA":      ("Initial Jobless Claims", "weekly", "persons"),
    "T10Y2Y":    ("Yield Curve 10y-2y Spread", "daily", "%"),
    "T10YFF":    ("10y Treasury - Fed Funds Spread", "daily", "%"),
    "VIXCLS":    ("CBOE VIX Close", "daily", "index"),
    "BAMLH0A0HYM2": ("HY Spread (OAS)", "daily", "%"),
    "DEXUSEU":   ("USD/EUR Exchange Rate", "daily", "rate"),
    # Housing
    "HOUST":     ("Housing Starts", "monthly", "k units"),
    "CSUSHPISA": ("Case-Shiller Home Price Index", "monthly", "index"),
    # Credit
    "TOTALSL":   ("Consumer Credit Outstanding", "monthly", "USD B"),
    "DRCCLACBS": ("Credit Card Delinquency Rate", "quarterly", "%"),
}

async def fetch_fred_series(series_id: str, api_key: str = "", start: str = "2020-01-01") -> list[dict]:
    """Fetch une série FRED sans API key (CSV public) ou avec API key (JSON)."""
    rows = []
    try:
        if api_key:
            url = f"{FRED_API}?series_id={series_id}&observation_start={start}&api_key={api_key}&file_type=json"
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url)
                data = r.json()
                for obs in data.get("observations", []):
                    if obs["value"] != ".":
                        rows.append({"date": obs["date"], "value": float(obs["value"])})
        else:
            # CSV public sans auth
            url = f"{FRED_BASE}?id={series_id}&vintage_date={date.today()}"
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url)
                for line in r.text.strip().split("\n")[1:]:
                    parts = line.split(",")
                    if len(parts) == 2 and parts[1] != ".":
                        try:
                            rows.append({"date": parts[0], "value": float(parts[1])})
                        except ValueError:
                            pass
    except Exception as e:
        log.warning("FRED %s error: %s", series_id, e)
    return rows


async def upsert_fred_all(db_engine, api_key: str = "", start: str = "2020-01-01") -> int:
    """Fetch et upsert toutes les séries FRED définies."""
    import sqlalchemy as sa
    total = 0
    for series_id, (name, freq, unit) in FRED_SERIES.items():
        rows = await fetch_fred_series(series_id, api_key, start)
        if not rows:
            continue
        with db_engine.connect() as conn:
            for row in rows:
                conn.execute(sa.text("""
                    INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                    VALUES (:sid, 'FRED', :name, :freq, :date, :value, :unit)
                    ON CONFLICT (series_id, date) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                """), {"sid": f"FRED:{series_id}", "name": name, "freq": freq,
                       "date": row["date"], "value": row["value"], "unit": unit})
            conn.commit()
        total += len(rows)
        log.info("FRED %s: %d rows upserted", series_id, len(rows))
        await asyncio.sleep(0.2)  # rate limit
    return total


# ── INSEE BDM ─────────────────────────────────────────────────────────────────
INSEE_BASE = "https://api.insee.fr/series/BDM/V1/data/SERIES_BDM"

INSEE_SERIES = {
    "001769682": ("IPC Ensemble", "monthly", "index"),
    "001769683": ("IPC Alimentation", "monthly", "index"),
    "001769684": ("IPC Energie", "monthly", "index"),
    "001762077": ("IPC Sous-jacent", "monthly", "index"),
    "001688527": ("Indice Confiance Consommateurs", "monthly", "index"),
    "001688526": ("Situation Financiere Menages", "monthly", "index"),
    "001672893": ("Taux Chomage France", "quarterly", "%"),
    "001620144": ("PIB Volume", "quarterly", "index"),
    "001654798": ("Production Industrielle", "monthly", "index"),
    "001617212": ("Ventes Commerce Detail", "monthly", "index"),
}

async def fetch_insee_series(series_id: str, token: str = "") -> list[dict]:
    """Fetch une série INSEE BDM (accès public sans token ou avec token)."""
    rows = []
    try:
        url = f"{INSEE_BASE}/{series_id}?startPeriod=2020-01&format=json"
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=headers)
            data = r.json()
            obs_list = (data.get("GenericData", {})
                           .get("DataSet", {})
                           .get("Series", {})
                           .get("Obs", []))
            if isinstance(obs_list, dict):
                obs_list = [obs_list]
            for obs in obs_list:
                period = obs.get("ObsDimension", {}).get("value", "")
                value  = obs.get("ObsValue", {}).get("value")
                if period and value:
                    # Convertit 2024-01 → 2024-01-01
                    d = period + "-01" if len(period) == 7 else period
                    try:
                        rows.append({"date": d, "value": float(value)})
                    except ValueError:
                        pass
    except Exception as e:
        log.warning("INSEE %s error: %s", series_id, e)
    return rows


async def upsert_insee_all(db_engine, token: str = "") -> int:
    """Fetch et upsert toutes les séries INSEE définies."""
    import sqlalchemy as sa
    total = 0
    for series_id, (name, freq, unit) in INSEE_SERIES.items():
        rows = await fetch_insee_series(series_id, token)
        if not rows:
            continue
        with db_engine.connect() as conn:
            for row in rows:
                conn.execute(sa.text("""
                    INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                    VALUES (:sid, 'INSEE', :name, :freq, :date, :value, :unit)
                    ON CONFLICT (series_id, date) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                """), {"sid": f"INSEE:{series_id}", "name": name, "freq": freq,
                       "date": row["date"], "value": row["value"], "unit": unit})
            conn.commit()
        total += len(rows)
        log.info("INSEE %s: %d rows upserted", series_id, len(rows))
        await asyncio.sleep(0.3)
    return total


# ── Volatilité implicite (yfinance options) ───────────────────────────────────
async def fetch_implied_vol(ticker: str, db_engine) -> int:
    """Fetch vol implicite ATM depuis yfinance options chain."""
    import sqlalchemy as sa
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        expirations = t.options[:4]  # 4 prochaines expirations
        spot = t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
        if not spot or not expirations:
            return 0

        today = date.today()
        count = 0
        for expiry in expirations:
            try:
                chain = t.option_chain(expiry)
                calls = chain.calls
                # Trouve l'option ATM (strike le plus proche du spot)
                calls["dist"] = abs(calls["strike"] - spot)
                atm = calls.nsmallest(3, "dist")
                with db_engine.connect() as conn:
                    for _, row in atm.iterrows():
                        iv = row.get("impliedVolatility")
                        if iv and iv > 0:
                            conn.execute(sa.text("""
                                INSERT INTO implied_vol (ticker, date, expiry, strike, iv, delta, vix_proxy)
                                VALUES (:ticker, :date, :expiry, :strike, :iv, :delta, :vix)
                                ON CONFLICT (ticker, date, expiry, strike) DO UPDATE
                                SET iv=EXCLUDED.iv, updated_at=NOW()
                            """), {
                                "ticker": ticker,
                                "date": str(today),
                                "expiry": expiry,
                                "strike": float(row["strike"]),
                                "iv": float(iv),
                                "delta": float(row.get("delta") or 0),
                                "vix": float(atm["impliedVolatility"].mean()),
                            })
                            count += 1
                    conn.commit()
            except Exception as e:
                log.warning("IV %s expiry %s: %s", ticker, expiry, e)
    except Exception as e:
        log.warning("IV fetch %s: %s", ticker, e)
        return 0
    return count


async def upsert_implied_vol_all(tickers: list[str], db_engine) -> int:
    """Fetch vol implicite pour une liste de tickers."""
    total = 0
    for ticker in tickers:
        n = await fetch_implied_vol(ticker, db_engine)
        total += n
        await asyncio.sleep(0.5)
    log.info("Implied vol complete: %d rows for %d tickers", total, len(tickers))
    return total


# ── Insider signals SEC Form 4 ────────────────────────────────────────────────
SEC_FORM4_BASE = "https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt={start}&enddt={end}&hits.hits._source=period_of_report,entity_name,file_date"

async def fetch_insider_sec(ticker: str, db_engine, days: int = 30) -> int:
    """Fetch transactions initiés SEC Form 4 pour un ticker."""
    import sqlalchemy as sa
    try:
        end = date.today()
        start = end - timedelta(days=days)
        # SEC EDGAR full-text search Form 4
        url = (f"https://efts.sec.gov/LATEST/search-index?"
               f"q=%22{ticker}%22+%22form+4%22"
               f"&dateRange=custom&startdt={start}&enddt={end}"
               f"&forms=4")
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "EthicalFinance research@sauhabah.eu"}) as client:
            r = await client.get(url)
            data = r.json()

        hits = data.get("hits", {}).get("hits", [])
        count = 0
        for hit in hits[:20]:
            src = hit.get("_source", {})
            period = src.get("period_of_report", str(end))
            entity = src.get("entity_name", "Unknown")
            # Valeur approximative depuis le filing (simplifiée)
            with db_engine.connect() as conn:
                conn.execute(sa.text("""
                    INSERT INTO insider_signals
                        (ticker, date, insider_name, role, transaction_type, source)
                    VALUES (:ticker, :date, :name, :role, :type, 'SEC_FORM4')
                    ON CONFLICT (ticker, date, insider_name, transaction_type) DO NOTHING
                """), {
                    "ticker": ticker,
                    "date": period[:10] if period else str(end),
                    "name": entity,
                    "role": src.get("relationship_is_officer", "Unknown"),
                    "type": "UNKNOWN",
                })
                conn.commit()
            count += 1
        return count
    except Exception as e:
        log.warning("Insider SEC %s: %s", ticker, e)
        return 0
