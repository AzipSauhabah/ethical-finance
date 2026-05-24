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

# INSEE via FRED (Eurostat/OECD reformaté) — accès libre sans auth
FRED_FRANCE_SERIES = {
    "FRCPIALLMINMEI":  ("France IPC Ensemble", "monthly", "index"),
    "FRACPIENGMINMEI": ("France IPC Energie", "monthly", "index"),
    "FRACPIFODAMINMEI":("France IPC Alimentation", "monthly", "index"),
    "LRUNTTTTFRM156S": ("France Taux Chomage", "monthly", "%"),
    "CLVMEURSCAB1GQFR":("France PIB Volume", "quarterly", "index"),
    "FRAPRINTO01IXPYM":("France Production Industrielle", "monthly", "index"),
    "FRARETAILSALMEI": ("France Ventes Retail", "monthly", "index"),
    "CSCICP03FRM665S": ("France Confiance Consommateurs", "monthly", "index"),
    "IRLTLT01FRM156N": ("France Taux 10 ans OAT", "monthly", "%"),
    "ECBDFR":          ("France Deficit/PIB", "annual", "%"),
}

# Alias pour compatibilité
INSEE_SERIES = {}

async def fetch_insee_series(series_id: str, token: str = "") -> list[dict]:
    """Fetch une série INSEE BDM via CSV public (sans auth)."""
    rows = []
    try:
        # URL CSV publique BDM — ne nécessite pas d'auth
        url = f"https://www.bdm.insee.fr/series/sdmx/data/SERIES_BDM/{series_id}?startPeriod=2020-01&format=csvnohead"
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers={"Accept": "text/csv"})
            if r.status_code != 200:
                log.warning("INSEE %s HTTP %d", series_id, r.status_code)
                return []
            for line in r.text.strip().split("\n")[1:]:
                parts = line.split(";")
                if len(parts) >= 2:
                    period = parts[0].strip().strip('"')
                    val = parts[-1].strip().strip('"')
                    if period and val and val not in ("", "NA", "."):
                        d = period + "-01" if len(period) == 7 else period
                        try:
                            rows.append({"date": d, "value": float(val.replace(",", "."))})
                        except ValueError:
                            pass
    except Exception as e:
        log.warning("INSEE %s error: %s", series_id, e)
    return rows


async def upsert_insee_all(db_engine, token: str = "") -> int:
    """Fetch et upsert toutes les séries INSEE définies."""
    import sqlalchemy as sa
    total = 0
    for series_id, (name, freq, unit) in FRED_FRANCE_SERIES.items():
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
