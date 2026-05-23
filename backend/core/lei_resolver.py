"""
:file: backend/core/lei_resolver.py
:brief: Résolution et maintenance automatique du mapping ticker → LEI.

        Sources par ordre de priorité :
        1. GLEIF API (api.gleif.org) — base mondiale officielle des LEI
        2. info-financiere.gouv.fr (codes-lei dataset) — tickers FR
        3. Manuel (fallback pour cas spéciaux)

        Validation :
        - Vérifie que le LEI a des filings ESEF sur filings.xbrl.org
        - Stocke le résultat dans ticker_lei_mapping (DB)

        Refresh automatique :
        - Job trimestriel via APScheduler (tous les 90 jours)
        - Triggered aussi lors du daily_update si ticker sans LEI

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_TIMEOUT    = 15.0
_USER_AGENT = "ethical-finance-platform contact@sauhabah-advisory.eu"
_XBRL_BASE  = "https://filings.xbrl.org"


# ─────────────────────────────────────────────────────────────────────────────
# Lookup GLEIF
# ─────────────────────────────────────────────────────────────────────────────

async def _search_gleif(company_name: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Cherche un LEI sur GLEIF par nom légal.
    Retourne une liste de candidats [{lei, legal_name}].
    """
    try:
        r = await client.get(
            "https://api.gleif.org/api/v1/lei-records",
            params={
                "filter[entity.legalName]": company_name,
                "page[size]": 5,
            },
            headers={"User-Agent": _USER_AGENT},
        )
        r.raise_for_status()
        results = []
        for item in r.json().get("data", []):
            lei  = item["id"]
            name = item["attributes"]["entity"]["legalName"]["name"]
            results.append({"lei": lei, "legal_name": name, "source": "gleif"})
        return results
    except Exception as exc:
        log.warning("GLEIF search failed for '%s': %s", company_name, exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Lookup info-financiere.gouv.fr
# ─────────────────────────────────────────────────────────────────────────────

async def _search_info_financiere(fragment: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Cherche un LEI sur info-financiere.gouv.fr par fragment de nom.
    Bon pour les sociétés françaises.
    """
    try:
        r = await client.get(
            "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/codes-lei/records",
            params={
                "where": f'identificationsociete_iso_nom_soc like "%{fragment}%"',
                "limit": 5,
                "select": "identificationsociete_iso_nom_soc,identificationsociete_iso_cd_lei",
            },
            headers={"User-Agent": _USER_AGENT},
        )
        r.raise_for_status()
        results = []
        for item in r.json().get("results", []):
            lei  = item.get("identificationsociete_iso_cd_lei")
            name = item.get("identificationsociete_iso_nom_soc")
            if lei and name:
                results.append({"lei": lei, "legal_name": name, "source": "info-financiere"})
        return results
    except Exception as exc:
        log.warning("info-financiere search failed for '%s': %s", fragment, exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Validation ESEF filing sur xbrl.org
# ─────────────────────────────────────────────────────────────────────────────

async def _validate_esef_filing(lei: str, client: httpx.AsyncClient) -> dict:
    """
    Vérifie si un LEI a des filings ESEF sur filings.xbrl.org.
    Retourne {has_filing, count, last_period_end}.
    """
    try:
        r = await client.get(
            f"{_XBRL_BASE}/api/filings",
            params={
                "filter[entity.identifier]": lei,
                "sort": "-period_end",
                "limit": 1,
            },
        )
        r.raise_for_status()
        data = r.json()
        count = data["meta"]["count"]
        last_period = None
        if data["data"]:
            last_period = data["data"][0]["attributes"].get("period_end", "")[:10]
        return {
            "has_esef_filing": count > 0,
            "esef_filing_count": count,
            "last_period_end": last_period,
        }
    except Exception as exc:
        log.warning("xbrl.org validation failed for LEI %s: %s", lei, exc)
        return {"has_esef_filing": False, "esef_filing_count": 0, "last_period_end": None}


# ─────────────────────────────────────────────────────────────────────────────
# Résolution principale
# ─────────────────────────────────────────────────────────────────────────────

def _ticker_to_search_terms(ticker: str) -> tuple[str, str]:
    """
    Dérive les termes de recherche depuis un ticker.
    Retourne (gleif_query, info_financiere_fragment).
    """
    base = ticker.upper()

    # Mapping ticker → termes de recherche connus
    _KNOWN_NAMES: dict[str, tuple[str, str]] = {
        "MC.PA":   ("LVMH Moet Hennessy",      "LVMH"),
        "TTE.PA":  ("TotalEnergies SE",         "TOTALENERGIES"),
        "OR.PA":   ("L'Oreal",                  "OREAL"),
        "AIR.PA":  ("Airbus SE",                "AIRBUS"),
        "RMS.PA":  ("Hermes International",     "HERMES"),
        "BNP.PA":  ("BNP Paribas",              "BNP PARIBAS"),
        "SAN.PA":  ("Sanofi",                   "SANOFI"),
        "SU.PA":   ("Schneider Electric SE",    "SCHNEIDER"),
        "AI.PA":   ("L'Air Liquide",            "AIR LIQUIDE"),
        "KER.PA":  ("Kering",                   "KERING"),
        "SAF.PA":  ("Safran",                   "SAFRAN"),
        "HO.PA":   ("Thales",                   "THALES"),
        "DSY.PA":  ("Dassault Systemes",        "DASSAULT SYSTEMES"),
        "EL.PA":   ("EssilorLuxottica",         "ESSILORLUXOTTICA"),
        "DG.PA":   ("Vinci",                    "VINCI"),
        "CS.PA":   ("AXA SA",                   "AXA"),
        "GLE.PA":  ("Societe Generale",         "SOCIETE GENERALE"),
        "ACA.PA":  ("Credit Agricole",          "CREDIT AGRICOLE"),
        "ORA.PA":  ("Orange SA",                "ORANGE"),
        "ENGI.PA": ("Engie SA",                 "ENGIE"),
        "VIE.PA":  ("Veolia Environnement",     "VEOLIA"),
        "BN.PA":   ("Danone",                   "DANONE"),
        "CA.PA":   ("Carrefour",                "CARREFOUR"),
        "SGO.PA":  ("Compagnie de Saint-Gobain","SAINT-GOBAIN"),
        "ML.PA":   ("Michelin",                 "MICHELIN"),
        "RNO.PA":  ("Renault",                  "RENAULT"),
        "RI.PA":   ("Pernod Ricard",            "PERNOD RICARD"),
        "PUB.PA":  ("Publicis Groupe",          "PUBLICIS"),
        "VIV.PA":  ("Vivendi",                  "VIVENDI"),
        "EN.PA":   ("Bouygues",                 "BOUYGUES"),
        "CAP.PA":  ("Capgemini SE",             "CAPGEMINI"),
        "LR.PA":   ("Legrand SA",               "LEGRAND"),
        "TEP.PA":  ("Teleperformance SE",       "TELEPERFORMANCE"),
        "WLN.PA":  ("Worldline",                "WORLDLINE"),
        "URW.PA":  ("Unibail-Rodamco-Westfield","UNIBAIL"),
        "MT.PA":   ("ArcelorMittal",            "ARCELORMITTAL"),
        "STM.PA":  ("STMicroelectronics NV",    "STMICRO"),
        "ALO.PA":  ("Alstom",                   "ALSTOM"),
    }

    if base in _KNOWN_NAMES:
        return _KNOWN_NAMES[base]

    # Fallback : dérive depuis le ticker
    fragment = base.replace(".PA", "").replace(".FP", "").replace(".L", "")
    return (fragment, fragment)


async def resolve_lei(
    ticker: str,
    db_conn,
    *,
    force_refresh: bool = False,
) -> Optional[str]:
    """
    Résout le LEI pour un ticker depuis la DB ou via lookup externe.

    Args:
        ticker:        Ticker (ex: "MC.PA", "AAPL")
        db_conn:       Connection asyncpg
        force_refresh: Ignore le cache DB et re-résout

    Returns:
        LEI string ou None si introuvable.
    """
    # ── Cache DB ──────────────────────────────────────────────────────────────
    if not force_refresh:
        row = await db_conn.fetchrow(
            "SELECT lei, has_esef_filing, verified_at FROM ticker_lei_mapping WHERE ticker = $1",
            ticker,
        )
        if row and row["lei"] and row["verified_at"]:
            age_days = (
                datetime.now(timezone.utc)
                - row["verified_at"].replace(tzinfo=timezone.utc)
            ).days
            if age_days < 90:
                log.debug("LEI cache hit for %s: %s", ticker, row["lei"])
                return row["lei"] if row["has_esef_filing"] else None

    # ── Lookup externe ────────────────────────────────────────────────────────
    gleif_query, info_fin_fragment = _ticker_to_search_terms(ticker)

    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT}) as client:

        # Source 1 : GLEIF
        candidates = await _search_gleif(gleif_query, client)

        # Source 2 : info-financiere (si .PA et pas trouvé sur GLEIF)
        if not candidates and ".PA" in ticker.upper():
            candidates = await _search_info_financiere(info_fin_fragment, client)

        if not candidates:
            log.info("No LEI found for %s", ticker)
            await _upsert_lei(db_conn, ticker, None, None, None, False, 0, None)
            return None

        # Validation ESEF : cherche le premier candidat avec des filings
        best_lei    = None
        best_name   = None
        best_source = None
        best_filing = {"has_esef_filing": False, "esef_filing_count": 0, "last_period_end": None}

        for candidate in candidates:
            lei    = candidate["lei"]
            filing = await _validate_esef_filing(lei, client)
            if filing["has_esef_filing"]:
                best_lei    = lei
                best_name   = candidate["legal_name"]
                best_source = candidate["source"]
                best_filing = filing
                log.info(
                    "LEI resolved for %s: %s (%s) — %d ESEF filings, last: %s",
                    ticker, lei, best_name,
                    filing["esef_filing_count"],
                    filing["last_period_end"],
                )
                break

        # Si aucun candidat n'a de filing ESEF, prend le premier quand même
        if not best_lei and candidates:
            best_lei    = candidates[0]["lei"]
            best_name   = candidates[0]["legal_name"]
            best_source = candidates[0]["source"]
            log.info("LEI resolved for %s (no ESEF filing): %s (%s)", ticker, best_lei, best_name)

        # Persiste en DB
        await _upsert_lei(
            db_conn, ticker,
            best_lei, best_name, best_source,
            best_filing["has_esef_filing"],
            best_filing["esef_filing_count"],
            best_filing["last_period_end"],
        )

        return best_lei if best_filing["has_esef_filing"] else None


async def _upsert_lei(
    db_conn,
    ticker:             str,
    lei:                Optional[str],
    legal_name:         Optional[str],
    source:             Optional[str],
    has_esef_filing:    bool,
    esef_filing_count:  int,
    last_period_end:    Optional[str],
) -> None:
    """Insère ou met à jour le mapping LEI en DB."""
    await db_conn.execute(
        """
        INSERT INTO ticker_lei_mapping
            (ticker, lei, legal_name, source, has_esef_filing, esef_filing_count, last_period_end, verified_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7::date, $8)
        ON CONFLICT (ticker) DO UPDATE SET
            lei               = EXCLUDED.lei,
            legal_name        = EXCLUDED.legal_name,
            source            = EXCLUDED.source,
            has_esef_filing   = EXCLUDED.has_esef_filing,
            esef_filing_count = EXCLUDED.esef_filing_count,
            last_period_end   = EXCLUDED.last_period_end,
            verified_at       = EXCLUDED.verified_at
        """,
        ticker, lei, legal_name, source,
        has_esef_filing, esef_filing_count,
        last_period_end,
        datetime.now(timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Job trimestriel — refresh tous les tickers
# ─────────────────────────────────────────────────────────────────────────────

async def refresh_all_lei_mappings(db_conn, *, concurrency: int = 3) -> dict:
    """
    Refresh trimestriel de tous les LEI mappings.
    Appelé par APScheduler tous les 90 jours.

    Returns:
        Stats {total, resolved, with_esef, failed}
    """
    import asyncio

    # Récupère tous les tickers en DB
    rows = await db_conn.fetch("SELECT ticker FROM ticker_fundamentals")
    tickers = [r["ticker"] for r in rows]

    log.info("LEI refresh started for %d tickers", len(tickers))

    semaphore = asyncio.Semaphore(concurrency)
    stats = {"total": len(tickers), "resolved": 0, "with_esef": 0, "failed": 0}

    async def _refresh_one(ticker: str) -> None:
        async with semaphore:
            try:
                lei = await resolve_lei(ticker, db_conn, force_refresh=True)
                if lei:
                    stats["resolved"] += 1
                    stats["with_esef"] += 1
                else:
                    # Vérifie si LEI trouvé sans ESEF
                    row = await db_conn.fetchrow(
                        "SELECT lei FROM ticker_lei_mapping WHERE ticker = $1", ticker
                    )
                    if row and row["lei"]:
                        stats["resolved"] += 1
                    else:
                        stats["failed"] += 1
                await asyncio.sleep(0.3)  # Rate limit GLEIF
            except Exception as exc:
                log.error("LEI refresh failed for %s: %s", ticker, exc)
                stats["failed"] += 1

    await asyncio.gather(*[_refresh_one(t) for t in tickers])

    log.info(
        "LEI refresh complete: %d/%d resolved, %d with ESEF, %d failed",
        stats["resolved"], stats["total"], stats["with_esef"], stats["failed"],
    )
    return stats
