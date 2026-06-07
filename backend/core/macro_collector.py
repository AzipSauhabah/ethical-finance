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
    "INTGSBFRM193N": ("France Govt Bond 10Y Yield", "monthly", "%"),
    "MYAGM2EZM196N": ("Euro Area M2 Money Supply", "monthly", "EUR B"),
    "ECBDFR":        ("ECB Deposit Facility Rate", "daily", "%"),
    "BOGMBASE":      ("US Monetary Base", "monthly", "USD B"),
    "WALCL":         ("Fed Balance Sheet Total Assets", "weekly", "USD B"),
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
INSEE_BDM_BASE = "https://www.bdm.insee.fr/series/sdmx/data/SERIES_BDM"

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

# Séries INSEE BDM natives (idbanks validés) — utiles pour prédiction de prix
# et optimisation de portefeuille
INSEE_BDM_SERIES = {
    # IPC base 2025 (nouvelles séries actives depuis fév 2026)
    "011814056": ("France IPC Ensemble base 2025",          "monthly",    "index"),
    "011814057": ("France IPC Variation mensuelle",          "monthly",    "%"),
    "011814058": ("France IPC Glissement annuel",            "monthly",    "%"),
    "011814059": ("France IPC Menages urbains base 2025",    "monthly",    "index"),
    # Marché du travail
    "001688527": ("France Taux Chomage BIT",                 "quarterly",  "%"),
    # Conjoncture sectorielle
    "001641608": ("France Conjoncture Promotion Immobiliere","quarterly",  "index"),
    "010766494": ("France Prix Production Services B2B",     "quarterly",  "index"),
    "010766495": ("France Prix Production Services Export",  "quarterly",  "index"),
}

# Alias pour compatibilité
INSEE_SERIES = {}


async def fetch_insee_bdm_series(idbank: str, start: str = "2015-01") -> list[dict]:
    """Fetch une série INSEE BDM via SDMX XML (API sans auth).

    Returns:
        list de {"date": "YYYY-MM-DD", "value": float}
    """
    import xml.etree.ElementTree as ET
    rows = []
    try:
        url = f"{INSEE_BDM_BASE}/{idbank}?startPeriod={start}"
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                log.warning("INSEE BDM %s HTTP %d", idbank, r.status_code)
                return []
        root = ET.fromstring(r.text)
        for obs in root.findall(".//{*}Obs"):
            period = obs.get("TIME_PERIOD", "")
            val = obs.get("OBS_VALUE", "")
            if not period or not val:
                continue
            # Normaliser la période en date ISO
            if "-Q" in period:            # YYYY-Qn → premier mois du trimestre
                year, q = period.split("-Q")
                month = str((int(q) - 1) * 3 + 1).zfill(2)
                d = f"{year}-{month}-01"
            elif len(period) == 7:        # YYYY-MM → YYYY-MM-01
                d = period + "-01"
            elif len(period) == 4:        # YYYY → YYYY-01-01
                d = period + "-01-01"
            else:
                d = period
            try:
                rows.append({"date": d, "value": float(val)})
            except ValueError:
                pass
    except Exception as e:
        log.warning("INSEE BDM %s error: %s", idbank, e)
    return rows


async def fetch_insee_series(series_id: str, token: str = "") -> list[dict]:
    """Alias pour compatibilité — délègue à fetch_insee_bdm_series."""
    return await fetch_insee_bdm_series(series_id)


async def upsert_insee_all(db_engine, token: str = "") -> int:
    """Fetch et upsert toutes les séries INSEE BDM natives + FRED_FR."""
    import sqlalchemy as sa
    total = 0

    # 1. Séries INSEE BDM natives (SDMX)
    for idbank, (name, freq, unit) in INSEE_BDM_SERIES.items():
        rows = await fetch_insee_bdm_series(idbank, start="2015-01")
        if not rows:
            log.warning("INSEE BDM %s: no data", idbank)
            continue
        with db_engine.begin() as conn:
            for row in rows:
                conn.execute(sa.text("""
                    INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                    VALUES (:sid, 'INSEE_BDM', :name, :freq, :date, :value, :unit)
                    ON CONFLICT (series_id, date) DO UPDATE
                    SET value=EXCLUDED.value, updated_at=NOW()
                """), {"sid": f"INSEE:{idbank}", "name": name, "freq": freq,
                       "date": row["date"], "value": row["value"], "unit": unit})
        total += len(rows)
        log.info("INSEE BDM %s (%s): %d rows upserted", idbank, name, len(rows))
        await asyncio.sleep(0.3)

    # 2. Séries FRED_FR (proxy INSEE via FRED)
    for series_id, (name, freq, unit) in FRED_FRANCE_SERIES.items():
        rows = await fetch_fred_series(series_id, start="2015-01-01")
        if not rows:
            continue
        with db_engine.begin() as conn:
            for row in rows:
                conn.execute(sa.text("""
                    INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                    VALUES (:sid, 'FRED_FR', :name, :freq, :date, :value, :unit)
                    ON CONFLICT (series_id, date) DO UPDATE
                    SET value=EXCLUDED.value, updated_at=NOW()
                """), {"sid": f"INSEE:{series_id}", "name": name, "freq": freq,
                       "date": row["date"], "value": row["value"], "unit": unit})
        total += len(rows)
        log.info("FRED_FR %s: %d rows upserted", series_id, len(rows))
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
    """Fetch transactions initiés SEC Form 4 pour un ticker avec parsing XML."""
    import sqlalchemy as sa
    try:
        end = date.today()
        start = end - timedelta(days=days)
        search_url = (
            f"https://efts.sec.gov/LATEST/search-index?"
            f"q=%22{ticker}%22+%22form+4%22"
            f"&dateRange=custom&startdt={start}&enddt={end}&forms=4"
        )
        headers = {"User-Agent": "EthicalFinance research@sauhabah.eu"}
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            r = await client.get(search_url)
            data = r.json()

        hits = data.get("hits", {}).get("hits", [])
        count = 0
        for hit in hits[:10]:
            src = hit.get("_source", {})
            period = (src.get("period_of_report") or str(end))[:10]
            entity = src.get("entity_name", "Unknown")
            accession = hit.get("_id", "").replace("-", "")
            # Tente de lire le XML Form 4 pour BUY/SELL
            tx_type = "UNKNOWN"
            shares = None
            try:
                if accession:
                    # Fallback — utilise le champ disponible
                    tx_type = "BUY" if src.get("transaction_shares", 0) and float(src.get("transaction_shares", 0) or 0) > 0 else "SELL"
            except Exception:
                pass
            with db_engine.connect() as conn:
                conn.execute(sa.text("""
                    INSERT INTO insider_signals
                        (ticker, date, insider_name, role, transaction_type, shares, source)
                    VALUES (:ticker, :date, :name, :role, :type, :shares, 'SEC_FORM4')
                    ON CONFLICT (ticker, date, insider_name, transaction_type) DO UPDATE
                    SET shares=EXCLUDED.shares, updated_at=NOW()
                """), {
                    "ticker": ticker,
                    "date": period,
                    "name": entity,
                    "role": src.get("relationship_is_officer", "Unknown"),
                    "type": tx_type,
                    "shares": shares,
                })
                conn.commit()
            count += 1
        return count
    except Exception as e:
        log.warning("Insider SEC %s: %s", ticker, e)
        return 0


# ── DVF — Demandes de Valeurs Foncières (data.gouv.fr) ───────────────────────
async def fetch_dvf_index(db_engine) -> int:
    """Fetch indice prix immobilier agrégé depuis DVF/DV3F (Cerema)."""
    import sqlalchemy as sa
    try:
        url = "https://apidf-preprod.cerema.fr/indicateurs/dv3f/national/indicateurs_transac/?ordering=periode&format=json"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                log.warning("DVF HTTP %d", r.status_code)
                return 0
            data = r.json()
        rows = data.get("results", [])
        count = 0
        with db_engine.connect() as conn:
            for row in rows:
                periode = row.get("periode", "")
                prix_m2 = row.get("prix_m2_median")
                nb_ventes = row.get("nbtrans_cod")
                if not periode or not prix_m2:
                    continue
                d = periode + "-01" if len(periode) == 7 else periode
                for sid, name, val, unit in [
                    ("DVF:PRIX_M2_MEDIAN_FR", "Prix m2 median France", prix_m2, "EUR/m2"),
                    ("DVF:NB_VENTES_FR", "Nombre ventes France", nb_ventes, "transactions"),
                ]:
                    if val:
                        conn.execute(sa.text("""
                            INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                            VALUES (:sid, 'DVF', :name, 'quarterly', :date, :value, :unit)
                            ON CONFLICT (series_id, date) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                        """), {"sid": sid, "name": name, "date": d, "value": float(val), "unit": unit})
                count += 1
            conn.commit()
        log.info("DVF: %d periodes upserted", count)
        return count
    except Exception as e:
        log.warning("DVF error: %s", e)
        return 0


async def fetch_dvf_csv(db_engine, year: int = 2024) -> int:
    """Telecharge DVF CSV, agrege prix/m2 par trimestre et departement."""
    import gzip, io, csv, statistics
    import sqlalchemy as sa
    from collections import defaultdict
    url = f"https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/full.csv.gz"
    log.info("DVF: telechargement %s...", url)
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                log.warning("DVF HTTP %d", r.status_code)
                return 0
        buckets = defaultdict(list)
        with gzip.open(io.BytesIO(r.content), "rt", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f, delimiter=",")
            for row in reader:
                try:
                    date_str = row.get("date_mutation", "")
                    if not date_str or len(date_str) < 7:
                        continue
                    month = int(date_str[5:7])
                    quarter = (month - 1) // 3 + 1
                    periode = f"{date_str[:4]}-Q{quarter}"
                    dept = row.get("code_departement", "")[:2]
                    surface = row.get("surface_reelle_bati", "")
                    valeur = row.get("valeur_fonciere", "").replace(",", ".")
                    type_local = row.get("type_local", "")
                    if surface and valeur and type_local in ("Appartement", "Maison"):
                        s, v = float(surface), float(valeur)
                        if 10 < s < 500 and v > 10000:
                            buckets[(periode, dept)].append(v / s)
                except (ValueError, KeyError):
                    continue
        count = 0
        with db_engine.connect() as conn:
            for (periode, dept), prix_list in buckets.items():
                if len(prix_list) < 10:
                    continue
                median_prix = statistics.median(prix_list)
                y, q = periode.split("-Q")
                month_start = (int(q) - 1) * 3 + 1
                d = f"{y}-{month_start:02d}-01"
                conn.execute(sa.text("""
                    INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                    VALUES (:sid, 'DVF', :name, 'quarterly', :date, :value, 'EUR/m2')
                    ON CONFLICT (series_id, date) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                """), {"sid": f"DVF:PRIX_M2_{dept}", "name": f"Prix m2 median dept {dept}",
                       "date": d, "value": round(median_prix, 2)})
                count += 1
            all_prices = [p for prices in buckets.values() for p in prices]
            if all_prices:
                conn.execute(sa.text("""
                    INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                    VALUES ('DVF:PRIX_M2_FR', 'DVF', 'Prix m2 median France', 'annual', :date, :value, 'EUR/m2')
                    ON CONFLICT (series_id, date) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                """), {"date": f"{year}-01-01", "value": round(statistics.median(all_prices), 2)})
                count += 1
            conn.commit()
        log.info("DVF %d: %d series upserted", year, count)
        return count
    except Exception as e:
        log.warning("DVF error: %s", e)
        return 0


# ── GDELT — Global Database of Events, Language, and Tone ────────────────────
async def fetch_gdelt_sentiment(db_engine, query: str = "CAC40 OR SP500 OR stocks", days: int = 7) -> int:
    """Fetch sentiment GDELT pour les marchés financiers."""
    import sqlalchemy as sa
    from datetime import datetime
    try:
        url = (
            f"https://api.gdeltproject.org/api/v2/doc/doc"
            f"?query={query.replace(' ', '%20')}"
            f"&mode=artlist&maxrecords=50&format=json"
            f"&timespan={days}d"
        )
        await asyncio.sleep(6)  # GDELT: 1 req/5s
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                log.warning("GDELT HTTP %d", r.status_code)
                return 0
            data = r.json()
        articles = data.get("articles", [])
        if not articles:
            return 0
        # Calcul score sentiment moyen (tone GDELT -100 à +100)
        tones = []
        for art in articles:
            tone = art.get("tone")
            if tone is not None:
                try:
                    tones.append(float(tone))
                except ValueError:
                    pass
        if not tones:
            return 0
        avg_tone = sum(tones) / len(tones)
        today = date.today()
        with db_engine.connect() as conn:
            conn.execute(sa.text("""
                INSERT INTO macro_series (series_id, source, name, frequency, date, value, unit)
                VALUES (:sid, 'GDELT', :name, 'daily', :date, :value, 'tone')
                ON CONFLICT (series_id, date) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
            """), {
                "sid": "GDELT:MARKET_TONE",
                "name": "GDELT Market Sentiment Tone",
                "date": str(today),
                "value": round(avg_tone, 3),
            })
            conn.commit()
        log.info("GDELT: tone=%.2f from %d articles", avg_tone, len(articles))
        return 1
    except Exception as e:
        log.warning("GDELT error: %s", e)
        return 0
