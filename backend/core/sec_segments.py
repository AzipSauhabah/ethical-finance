"""
:file: backend/core/sec_segments.py
:brief: Extrait les revenus par segment depuis les filings SEC EDGAR (10-K).

        Stratégie :
        1. Lookup CIK via company_tickers.json (déjà dans sec_edgar.py)
        2. Fetch companyfacts pour les concepts GAAP de segment :
           - us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax
           - us-gaap/Revenues
           avec dimension "srt:ProductOrServiceAxis" ou "srt:StatementBusinessSegmentsAxis"
        3. Parse les valeurs par segment, normalise en fractions

        Note : La couverture EDGAR est excellente pour les entreprises US (S&P 500).
        Pour les tickers non-US (CAC40, etc.), FMP est la source principale.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_CIK_URL   = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
_HEADERS   = {"User-Agent": "ethical-finance-platform contact@sauhabah-advisory.eu"}
_TIMEOUT   = 20.0

# Concepts GAAP qui contiennent les revenus segmentés
_SEGMENT_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
]

# Axes de dimension indiquant une décomposition par segment produit
_PRODUCT_AXES = {
    "srt:ProductOrServiceAxis",
    "srt:StatementBusinessSegmentsAxis",
    "us-gaap:StatementBusinessSegmentsAxis",
}


async def _get_cik(ticker: str) -> Optional[int]:
    """Retourne le CIK pour un ticker US, None si introuvable."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(_CIK_URL)
            resp.raise_for_status()
            tickers_map: dict = resp.json()

        ticker_upper = ticker.upper().split(".")[0]  # MC.PA → MC
        for _idx, entry in tickers_map.items():
            if entry.get("ticker", "").upper() == ticker_upper:
                return int(entry["cik_str"])
    except Exception as exc:
        log.warning("SEC CIK lookup failed for %s: %s", ticker, exc)
    return None


async def fetch_segments_from_edgar(ticker: str) -> dict[str, float]:
    """
    Extrait les revenus par segment depuis SEC EDGAR.

    Returns:
        Dict {segment_name: fraction_du_CA} ou {} si non disponible.
    """
    cik = await _get_cik(ticker)
    if cik is None:
        log.debug("No CIK found for %s — skipping EDGAR segments", ticker)
        return {}

    url = _FACTS_URL.format(cik=cik)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            facts: dict = resp.json()
    except Exception as exc:
        log.warning("SEC EDGAR facts fetch failed for CIK %d (%s): %s", cik, ticker, exc)
        return {}

    gaap = facts.get("facts", {}).get("us-gaap", {})

    # Cherche le premier concept disponible avec données segmentées
    for concept in _SEGMENT_CONCEPTS:
        if concept not in gaap:
            continue

        units = gaap[concept].get("units", {})
        usd_entries = units.get("USD", [])

        if not usd_entries:
            continue

        # Filtre : form 10-K uniquement, avec une dimension segment
        segmented = [
            e for e in usd_entries
            if e.get("form") in ("10-K", "20-F")
            and e.get("segment") is not None
        ]

        if not segmented:
            continue

        # Prend l'année la plus récente (champ "end" = date de fin de période)
        try:
            latest_year = max(e["end"][:4] for e in segmented)
        except (KeyError, ValueError):
            continue

        year_entries = [e for e in segmented if e.get("end", "")[:4] == latest_year]

        # Regroupe par nom de membre (dimension value)
        segment_revenues: dict[str, float] = {}
        for entry in year_entries:
            seg_info = entry.get("segment", {})
            # EDGAR structure: {"dimension": "srt:ProductOrServiceAxis", "value": "us-gaap:XxxMember"}
            dim   = seg_info.get("dimension", "")
            value = seg_info.get("value", "")

            if dim not in _PRODUCT_AXES:
                continue

            # Nettoie le nom du membre (us-gaap:WinesAndSpiritsMember → Wines And Spirits)
            name = _clean_member_name(value)
            val  = float(entry.get("val", 0))

            if name and val > 0:
                # En cas de doublons (plusieurs dépôts), garde le max
                segment_revenues[name] = max(segment_revenues.get(name, 0), val)

        if not segment_revenues:
            continue

        # Normalise en fractions
        total = sum(segment_revenues.values())
        if total <= 0:
            continue

        log.info(
            "EDGAR segments found for %s (concept: %s, year: %s): %d segments",
            ticker, concept, latest_year, len(segment_revenues),
        )
        return {k: v / total for k, v in segment_revenues.items()}

    log.debug("No segmented revenue data found in EDGAR for %s", ticker)
    return {}


def _clean_member_name(member: str) -> str:
    """
    Convertit un nom de membre XBRL en label lisible.
    Ex: "us-gaap:WinesAndSpiritsMember" → "Wines And Spirits"
        "srt:NorthAmericaMember"        → "North America"
    """
    # Supprime le namespace
    if ":" in member:
        member = member.split(":")[-1]

    # Supprime "Member" en fin
    if member.endswith("Member"):
        member = member[:-6]

    # CamelCase → mots séparés
    import re
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", member)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)

    return spaced.strip()
