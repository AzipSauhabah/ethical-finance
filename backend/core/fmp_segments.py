"""
:file: backend/core/fmp_segments.py
:brief: Fetch des revenus par segment géographique et par produit via FMP.

        FMP endpoints utilisés :
        - /revenue-product-segmentation   → segments produit  (ex: LVMH: Wines & Spirits 18%)
        - /revenue-geographic-segmentation → segments géo      (ex: Europe 45%, Asie 30%)

        Le segment produit est prioritaire pour la classification Sharia.
        Le segment géo sert uniquement pour la future feature "exposition devise NAV".

        Usage :
            from backend.core.fmp_segments import fetch_product_segments
            segs = await fetch_product_segments("MC.PA", api_key)
            # → {"Wines & Spirits": 0.18, "Fashion & Leather Goods": 0.44, ...}

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/api/v4"
_TIMEOUT = 15.0


async def fetch_product_segments(
    ticker:  str,
    api_key: str,
    *,
    most_recent_year: bool = True,
) -> dict[str, float]:
    """
    Retourne {segment_name: fraction_du_CA} pour le ticker donné.

    Args:
        ticker:           Ticker FMP (ex: "AAPL", "MC.PA")
        api_key:          Clé FMP
        most_recent_year: Si True, ne garde que l'année la plus récente

    Returns:
        Dict segment → fraction ∈ [0,1].  Dict vide si non disponible.
    """
    url = f"{FMP_BASE}/revenue-product-segmentation"
    params = {"symbol": ticker, "apikey": api_key, "period": "annual"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("FMP product-segments fetch failed for %s: %s", ticker, exc)
        return {}

    # FMP retourne une liste d'années : [{"date": "2023-12-31", "Wines & Spirits": 0.18, ...}]
    if not isinstance(data, list) or not data:
        return {}

    # Trie par date décroissante, prend la plus récente
    try:
        sorted_data = sorted(
            [item for item in data if isinstance(item, dict) and "date" in item],
            key=lambda x: x["date"],
            reverse=True,
        )
    except (KeyError, TypeError):
        sorted_data = data

    if not sorted_data:
        return {}

    latest = sorted_data[0]

    # Extrait les segments (toutes les clés sauf "date" et "symbol")
    raw_segments: dict[str, float] = {}
    for key, val in latest.items():
        if key.lower() in ("date", "symbol", "period", "reportedcurrency"):
            continue
        try:
            raw_segments[key] = float(val)
        except (ValueError, TypeError):
            continue

    if not raw_segments:
        return {}

    # Normalise en fractions (FMP peut donner des valeurs absolues ou des %)
    total = sum(raw_segments.values())
    if total <= 0:
        return {}

    # Si les valeurs sont des montants absolus (> 1), on normalise
    if total > 2.0:
        return {k: v / total for k, v in raw_segments.items()}

    return raw_segments


async def fetch_geographic_segments(
    ticker:  str,
    api_key: str,
) -> dict[str, float]:
    """
    Retourne {region_name: fraction_du_CA} pour exposition géographique.
    Utilisé pour la feature "exposition devise NAV" (roadmap future).
    """
    url = f"{FMP_BASE}/revenue-geographic-segmentation"
    params = {"symbol": ticker, "apikey": api_key, "period": "annual"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("FMP geo-segments fetch failed for %s: %s", ticker, exc)
        return {}

    if not isinstance(data, list) or not data:
        return {}

    try:
        sorted_data = sorted(
            [item for item in data if isinstance(item, dict) and "date" in item],
            key=lambda x: x["date"],
            reverse=True,
        )
    except (KeyError, TypeError):
        sorted_data = data

    if not sorted_data:
        return {}

    latest = sorted_data[0]
    raw: dict[str, float] = {}
    for key, val in latest.items():
        if key.lower() in ("date", "symbol", "period"):
            continue
        try:
            raw[key] = float(val)
        except (ValueError, TypeError):
            continue

    if not raw:
        return {}

    total = sum(raw.values())
    if total <= 0:
        return {}
    if total > 2.0:
        return {k: v / total for k, v in raw.items()}
    return raw


async def fetch_all_segments(
    ticker:  str,
    api_key: str,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Fetch produit + géo en parallèle.
    Retourne (product_segments, geo_segments).
    """
    product_task = fetch_product_segments(ticker, api_key)
    geo_task     = fetch_geographic_segments(ticker, api_key)
    return await asyncio.gather(product_task, geo_task)
