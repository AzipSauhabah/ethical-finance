"""
:file: backend/core/drive_sync.py
:brief: Synchronisation Google Drive → NAS.

Télécharge le fichier ohlcv_latest.csv.gz depuis Google Drive
et importe les nouvelles données en base PostgreSQL.

Authentification : Service Account (pas d'interaction utilisateur).
Schedule : déclenché par APScheduler après le notebook Colab (23h30 UTC).

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import io
import logging
import os

log = logging.getLogger(__name__)

SERVICE_ACCOUNT_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT",
    "/app/ethical-finance-nas-885bda7b656d.json",
)
DRIVE_FOLDER_NAME = "ethical-finance-data"
OHLCV_FILENAME = "ohlcv_latest.csv.gz"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ─── Auth ────────────────────────────────────────────────────────────────────


def _get_drive_service():
    """Crée un client Google Drive authentifié via Service Account."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("drive", "v3", credentials=creds)
        return service
    except Exception as e:
        log.error("Google Drive auth error: %s", e)
        raise


# ─── Find file ───────────────────────────────────────────────────────────────


def _find_file_id(service, filename: str, folder_name: str) -> str | None:
    """Trouve l'ID d'un fichier dans Google Drive par nom."""
    try:
        # Chercher le dossier
        folder_result = (
            service.files()
            .list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)",
            )
            .execute()
        )

        folders = folder_result.get("files", [])
        if not folders:
            log.warning("Drive folder '%s' not found", folder_name)
            return None

        folder_id = folders[0]["id"]

        # Chercher le fichier dans le dossier
        file_result = (
            service.files()
            .list(
                q=f"name='{filename}' and '{folder_id}' in parents",
                fields="files(id, name, modifiedTime, size)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        files = file_result.get("files", [])
        if not files:
            log.warning("File '%s' not found in Drive folder", filename)
            return None

        file_info = files[0]
        log.info(
            "Found Drive file: %s (id=%s, modified=%s, size=%s)",
            file_info["name"],
            file_info["id"],
            file_info.get("modifiedTime"),
            file_info.get("size"),
        )
        return file_info["id"]

    except Exception as e:
        log.error("Drive file search error: %s", e)
        return None


# ─── Download ─────────────────────────────────────────────────────────────────


def _download_file(service, file_id: str) -> bytes | None:
    """Télécharge un fichier depuis Google Drive en mémoire."""
    try:
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                log.debug("Download progress: %d%%", int(status.progress() * 100))

        buf.seek(0)
        return buf.read()

    except Exception as e:
        log.error("Drive download error: %s", e)
        return None


# ─── Import en DB ─────────────────────────────────────────────────────────────


async def import_ohlcv_from_drive() -> dict:
    """
    Télécharge ohlcv_latest.csv.gz depuis Google Drive
    et importe les nouvelles données en base PostgreSQL.

    Returns:
        dict avec stats : rows_downloaded, rows_inserted, rows_skipped
    """
    import asyncio

    import pandas as pd

    from backend.core.db import upsert_ohlcv

    log.info("Starting Drive → DB sync")

    # 1. Auth et téléchargement
    loop = asyncio.get_event_loop()

    def _download():
        service = _get_drive_service()
        file_id = _find_file_id(service, OHLCV_FILENAME, DRIVE_FOLDER_NAME)
        if not file_id:
            return None
        return _download_file(service, file_id)

    raw_bytes = await loop.run_in_executor(None, _download)
    if not raw_bytes:
        log.warning("Drive sync: no data downloaded")
        return {"rows_downloaded": 0, "rows_inserted": 0, "error": "No file found"}

    # 2. Parser le CSV
    try:
        buf = io.BytesIO(raw_bytes)
        df = pd.read_csv(buf, compression="gzip", parse_dates=["date"])
        log.info("Drive sync: %d rows downloaded, %d tickers", len(df), df["ticker"].nunique())
    except Exception as e:
        log.error("Drive sync: CSV parse error: %s", e)
        return {"rows_downloaded": 0, "rows_inserted": 0, "error": str(e)}

    # 3. Importer par ticker
    total_inserted = 0
    tickers = df["ticker"].unique().tolist()

    for ticker in tickers:
        ticker_df = df[df["ticker"] == ticker].copy()
        ticker_df = ticker_df.set_index("date")
        ticker_df = ticker_df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "adj_close": "Adj Close",
                "volume": "Volume",
            }
        )
        try:
            n = await upsert_ohlcv(ticker_df, ticker)
            total_inserted += n
        except Exception as e:
            log.warning("Drive sync upsert error for %s: %s", ticker, e)

    log.info(
        "Drive sync complete: %d rows downloaded, %d rows inserted, %d tickers",
        len(df),
        total_inserted,
        len(tickers),
    )

    return {
        "rows_downloaded": len(df),
        "rows_inserted": total_inserted,
        "tickers": len(tickers),
    }


# ─── Endpoint API ─────────────────────────────────────────────────────────────


async def trigger_drive_sync() -> dict:
    """
    Déclenche manuellement la synchronisation Drive → DB.
    Appelé par l'endpoint /api/admin/drive-sync et par le scheduler.
    """
    try:
        result = await import_ohlcv_from_drive()
        return {"status": "ok", **result}
    except Exception as e:
        log.error("Drive sync trigger error: %s", e)
        return {"status": "error", "error": str(e)}

async def import_ohlcv_backfill_from_drive(db_engine) -> int:
    """
    Importe les CSVs ohlcv_backfill_*.csv depuis Google Drive/ethical-finance/ohlcv_backfill/
    et les insère dans la table ohlcv.
    """
    import sqlalchemy as sa
    import pandas as pd
    import io

    service = _get_drive_service()
    if not service:
        log.warning("Drive service non disponible")
        return 0

    try:
        # ID direct du dossier ohlcv_backfill
        folder_id = "13IrATf_ft0ppLRrTE5uxl_PRfcIdmb73"

        # Liste les CSVs dans le dossier
        files_result = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'ohlcv_backfill' and name contains '.csv'",
            fields="files(id, name)",
            orderBy="createdTime desc"
        ).execute()
        files = files_result.get("files", [])
        if not files:
            log.warning("Aucun CSV backfill trouvé")
            return 0

        # Prend le plus récent
        file = files[0]
        log.info("Import backfill: %s", file["name"])

        # Download
        content = service.files().get_media(fileId=file["id"]).execute()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        df["date"] = pd.to_datetime(df["date"]).dt.date
        # Nettoyage
        df = df.dropna(subset=["ticker","date","close"])
        df["open"]   = pd.to_numeric(df["open"],   errors="coerce").fillna(0)
        df["high"]   = pd.to_numeric(df["high"],   errors="coerce").fillna(0)
        df["low"]    = pd.to_numeric(df["low"],    errors="coerce").fillna(0)
        df["close"]  = pd.to_numeric(df["close"],  errors="coerce").fillna(0)
        df["adj_close"] = pd.to_numeric(df["adj_close"], errors="coerce").fillna(0)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        df = df[df["close"] > 0]
        log.info("Backfill CSV: %d rows, %d tickers", len(df), df["ticker"].nunique())

        inserted = 0
        with db_engine.begin() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute(sa.text("""
                        INSERT INTO ohlcv (ticker, date, open, high, low, close, adj_close, volume)
                        VALUES (:ticker, :dt, :open, :high, :low, :close, :adj, :volume)
                        ON CONFLICT (ticker, date) DO UPDATE SET
                            open=EXCLUDED.open, high=EXCLUDED.high,
                            low=EXCLUDED.low, close=EXCLUDED.close,
                            adj_close=EXCLUDED.adj_close, volume=EXCLUDED.volume
                    """), {
                        "ticker": str(row["ticker"]),
                        "dt": str(row["date"]),
                        "open": float(row.get("open") or 0),
                        "high": float(row.get("high") or 0),
                        "low": float(row.get("low") or 0),
                        "close": float(row.get("close") or 0),
                        "adj": float(row.get("adj_close") or 0),
                        "volume": int(row.get("volume") or 0),
                    })
                    inserted += 1
                except Exception as e:
                    log.debug("Insert error %s: %s", row.get("ticker"), e)

        log.info("Backfill import complete — %d rows", inserted)
        return inserted

    except Exception as e:
        log.warning("Drive backfill error: %s", e)
        return 0

async def import_msci_ohlcv_from_drive(db_engine) -> int:
    """Importe ohlcv_msci_*.csv depuis Drive."""
    import sqlalchemy as sa
    import pandas as pd
    import io

    service = _get_drive_service()
    if not service:
        return 0

    try:
        folder_id = "13IrATf_ft0ppLRrTE5uxl_PRfcIdmb73"
        files_result = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'ohlcv_msci' and name contains '.csv'",
            fields="files(id, name)", orderBy="createdTime desc"
        ).execute()
        files = files_result.get("files", [])
        if not files:
            log.warning("Aucun CSV MSCI trouvé")
            return 0

        file = files[0]
        log.info("Import MSCI: %s", file["name"])
        content = service.files().get_media(fileId=file["id"]).execute()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.dropna(subset=["ticker","date","close"])
        df = df[df["close"] > 0]

        inserted = 0
        with db_engine.begin() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute(sa.text("""
                        INSERT INTO ohlcv (ticker, date, open, high, low, close, adj_close, volume)
                        VALUES (:ticker, :dt, :open, :high, :low, :close, :adj, :volume)
                        ON CONFLICT (ticker, date) DO UPDATE SET
                            close=EXCLUDED.close, adj_close=EXCLUDED.adj_close
                    """), {
                        "ticker": str(row["ticker"]),
                        "dt": str(row["date"]),
                        "open": float(row.get("open") or 0),
                        "high": float(row.get("high") or 0),
                        "low": float(row.get("low") or 0),
                        "close": float(row.get("close") or 0),
                        "adj": float(row.get("adj_close") or 0),
                        "volume": int(row.get("volume") or 0),
                    })
                    inserted += 1
                except: pass

        log.info("MSCI import complete — %d rows", inserted)
        return inserted
    except Exception as e:
        log.warning("MSCI import error: %s", e)
        return 0


async def import_dividends_from_drive(db_engine) -> int:
    """Importe dividends_*.csv depuis Drive dans la table ohlcv_dividends."""
    import sqlalchemy as sa
    import pandas as pd
    import io

    service = _get_drive_service()
    if not service:
        return 0

    try:
        folder_id = "13IrATf_ft0ppLRrTE5uxl_PRfcIdmb73"
        files_result = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'dividends' and name contains '.csv'",
            fields="files(id, name)", orderBy="createdTime desc"
        ).execute()
        files = files_result.get("files", [])
        if not files:
            log.warning("Aucun CSV dividendes trouvé")
            return 0

        file = files[0]
        log.info("Import dividendes: %s", file["name"])
        content = service.files().get_media(fileId=file["id"]).execute()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.dropna(subset=["ticker","date","dividend"])

        # Insère dans transactions comme DIVIDEND
        inserted = 0
        with db_engine.begin() as conn:
            # Crée la table si elle n'existe pas
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS ohlcv_dividends (
                    ticker TEXT NOT NULL,
                    date DATE NOT NULL,
                    dividend DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (ticker, date)
                )
            """))
            for _, row in df.iterrows():
                try:
                    conn.execute(sa.text("""
                        INSERT INTO ohlcv_dividends (ticker, date, dividend)
                        VALUES (:ticker, :dt, :div)
                        ON CONFLICT (ticker, date) DO UPDATE SET dividend=EXCLUDED.dividend
                    """), {
                        "ticker": str(row["ticker"]),
                        "dt": str(row["date"]),
                        "div": float(row["dividend"]),
                    })
                    inserted += 1
                except: pass

        log.info("Dividendes import complete — %d rows", inserted)
        return inserted
    except Exception as e:
        log.warning("Dividendes import error: %s", e)
        return 0

async def import_splits_from_drive(db_engine) -> int:
    """Importe splits_*.csv depuis Drive."""
    import sqlalchemy as sa, pandas as pd, io
    service = _get_drive_service()
    if not service: return 0
    try:
        folder_id = "13IrATf_ft0ppLRrTE5uxl_PRfcIdmb73"
        files = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'splits' and name contains '.csv'",
            fields="files(id,name)", orderBy="createdTime desc"
        ).execute().get("files", [])
        if not files: return 0
        content = service.files().get_media(fileId=files[0]["id"]).execute()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        df["date"] = pd.to_datetime(df["date"]).dt.date
        inserted = 0
        with db_engine.begin() as conn:
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS stock_splits (
                    ticker TEXT NOT NULL, date DATE NOT NULL,
                    ratio DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (ticker, date)
                )
            """))
            for _, row in df.iterrows():
                try:
                    conn.execute(sa.text("""
                        INSERT INTO stock_splits (ticker, date, ratio)
                        VALUES (:t, :d, :r)
                        ON CONFLICT (ticker, date) DO UPDATE SET ratio=EXCLUDED.ratio
                    """), {"t": str(row["ticker"]), "d": str(row["date"]), "r": float(row["ratio"])})
                    inserted += 1
                except: pass
        log.info("Splits import: %d rows", inserted)
        return inserted
    except Exception as e:
        log.warning("Splits import error: %s", e)
        return 0


async def import_intraday_from_drive(db_engine) -> int:
    """Importe ohlcv_intraday_*.csv depuis Drive."""
    import sqlalchemy as sa, pandas as pd, io
    service = _get_drive_service()
    if not service: return 0
    try:
        folder_id = "13IrATf_ft0ppLRrTE5uxl_PRfcIdmb73"
        files = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'ohlcv_intraday' and name contains '.csv'",
            fields="files(id,name)", orderBy="createdTime desc"
        ).execute().get("files", [])
        if not files: return 0
        content = service.files().get_media(fileId=files[0]["id"]).execute()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.dropna(subset=["ticker","datetime","close"])
        df = df[df["close"] > 0]
        inserted = 0
        with db_engine.begin() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute(sa.text("""
                        INSERT INTO ohlcv_intraday (ticker, datetime, open, high, low, close, volume)
                        VALUES (:t, :dt, :o, :h, :l, :c, :v)
                        ON CONFLICT (ticker, datetime) DO UPDATE SET close=EXCLUDED.close
                    """), {
                        "t": str(row["ticker"]),
                        "dt": pd.to_datetime(str(row["datetime"])).isoformat(),
                        "o": float(row.get("open") or 0), "h": float(row.get("high") or 0),
                        "l": float(row.get("low") or 0), "c": float(row.get("close") or 0),
                        "v": int(row.get("volume") or 0),
                    })
                    inserted += 1
                except: pass
        log.info("Intraday import: %d rows", inserted)
        return inserted
    except Exception as e:
        log.warning("Intraday import error: %s", e)
        return 0


async def import_implied_vol_from_drive(db_engine) -> int:
    """Importe implied_vol_*.csv depuis Drive."""
    import sqlalchemy as sa, pandas as pd, io
    service = _get_drive_service()
    if not service: return 0
    try:
        folder_id = "13IrATf_ft0ppLRrTE5uxl_PRfcIdmb73"
        files = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'implied_vol' and name contains '.csv'",
            fields="files(id,name)", orderBy="createdTime desc"
        ).execute().get("files", [])
        if not files: return 0
        content = service.files().get_media(fileId=files[0]["id"]).execute()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        df["date"] = pd.to_datetime(df["date"]).dt.date
        inserted = 0
        with db_engine.begin() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute(sa.text("""
                        INSERT INTO implied_vol (ticker, date, expiry, strike, iv, vix_proxy)
                        VALUES (:t, :d, :exp, :strike, :iv, :vix)
                        ON CONFLICT (ticker, date, expiry, strike) DO UPDATE SET iv=EXCLUDED.iv
                    """), {
                        "t": str(row["ticker"]),
                        "d": str(row["date"]),
                        "exp": str(row.get("expiration", row["date"])),
                        "strike": 0.0,
                        "iv": float(row["iv_30d"]),
                        "vix": float(row["iv_30d"]),
                    })
                    inserted += 1
                except: pass
        log.info("IV import: %d rows", inserted)
        return inserted
    except Exception as e:
        log.warning("IV import error: %s", e)
        return 0

async def import_sp500_composition_from_drive(db_engine) -> int:
    """Importe sp500_current + sp500_changes depuis Drive."""
    import sqlalchemy as sa, pandas as pd, io
    service = _get_drive_service()
    if not service: return 0
    try:
        folder_id = "13IrATf_ft0ppLRrTE5uxl_PRfcIdmb73"
        inserted = 0

        # Table sp500_composition
        with db_engine.begin() as conn:
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS sp500_composition (
                    date DATE NOT NULL,
                    tickers TEXT NOT NULL,
                    PRIMARY KEY (date)
                )
            """))
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS sp500_current (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    sector TEXT,
                    sub_industry TEXT,
                    headquarters TEXT,
                    date_added DATE,
                    cik TEXT,
                    founded TEXT
                )
            """))

        # Import composition historique (sp500_changes)
        files = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'sp500_changes' and name contains '.csv'",
            fields="files(id,name)", orderBy="createdTime desc"
        ).execute().get("files", [])

        if files:
            content = service.files().get_media(fileId=files[0]["id"]).execute()
            df = pd.read_csv(io.StringIO(content.decode("utf-8")))
            df["date"] = pd.to_datetime(df["date"]).dt.date
            with db_engine.begin() as conn:
                for _, row in df.iterrows():
                    try:
                        conn.execute(sa.text("""
                            INSERT INTO sp500_composition (date, tickers)
                            VALUES (:d, :t)
                            ON CONFLICT (date) DO UPDATE SET tickers=EXCLUDED.tickers
                        """), {"d": str(row["date"]), "t": str(row["tickers"])})
                        inserted += 1
                    except: pass
            log.info("SP500 changes: %d rows", inserted)

        # Import composition actuelle (sp500_current)
        files2 = service.files().list(
            q=f"'{folder_id}' in parents and name contains 'sp500_current' and name contains '.csv'",
            fields="files(id,name)", orderBy="createdTime desc"
        ).execute().get("files", [])

        if files2:
            content2 = service.files().get_media(fileId=files2[0]["id"]).execute()
            df2 = pd.read_csv(io.StringIO(content2.decode("utf-8")))
            with db_engine.begin() as conn:
                for _, row in df2.iterrows():
                    try:
                        conn.execute(sa.text("""
                            INSERT INTO sp500_current (ticker, name, sector, sub_industry, headquarters, date_added, cik, founded)
                            VALUES (:t, :n, :s, :si, :hq, :da, :cik, :f)
                            ON CONFLICT (ticker) DO UPDATE SET name=EXCLUDED.name, sector=EXCLUDED.sector
                        """), {
                            "t": str(row.get("Symbol","")),
                            "n": str(row.get("Security","")),
                            "s": str(row.get("GICS Sector","")),
                            "si": str(row.get("GICS Sub-Industry","")),
                            "hq": str(row.get("Headquarters Location","")),
                            "da": str(row.get("Date added","")) or None,
                            "cik": str(row.get("CIK","")),
                            "f": str(row.get("Founded","")),
                        })
                    except: pass
            log.info("SP500 current: %d tickers", len(df2))

        return inserted
    except Exception as e:
        log.warning("SP500 import error: %s", e)
        return 0
