"""
:file: backend/core/segment_enricher.py
:brief: Orchestrateur pour l'enrichissement des revenus par segment.

        Pipeline par priorité de source :
        1. FMP /revenue-product-segmentation     (meilleure couverture, labels lisibles)
        2. info-financiere.gouv.fr ESEF/iXBRL    (tickers .PA — gratuit, officiel)
        3. SEC EDGAR 10-K                        (tickers US)
        4. Fallback proxy interest_expense        (si toutes sources vides)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.core.fmp_segments    import fetch_product_segments
from backend.core.esef_segments   import fetch_segments_from_esef
from backend.core.sec_segments    import fetch_segments_from_edgar
from backend.quant.halal_classifier import classify_segments

log = logging.getLogger(__name__)

_CACHE_DAYS = 90


def _is_french_ticker(ticker: str) -> bool:
    return ticker.upper().endswith((".PA", ".FP"))


def _is_us_ticker(ticker: str) -> bool:
    return "." not in ticker


async def enrich_ticker_segments(
    ticker:   str,
    fmp_key:  str,
    db_conn,
    *,
    force_refresh: bool = False,
) -> dict[str, float]:
    """
    Enrichit un ticker avec ses revenus par segment.
    Pipeline : FMP → ESEF (tickers FR) → EDGAR (tickers US) → {}

    Returns:
        Dict {segment_name: fraction} (peut être vide).
    """
    # ── Cache ────────────────────────────────────────────────────────────────
    if not force_refresh:
        row = await db_conn.fetchrow(
            "SELECT revenue_segments, segments_fetched_at FROM ticker_fundamentals WHERE ticker = $1",
            ticker,
        )
        if row and row["revenue_segments"] and row["segments_fetched_at"]:
            age_days = (
                datetime.now(timezone.utc)
                - row["segments_fetched_at"].replace(tzinfo=timezone.utc)
            ).days
            if age_days < _CACHE_DAYS:
                try:
                    cached = json.loads(row["revenue_segments"])
                    log.debug("Segments cache hit for %s (%d days old)", ticker, age_days)
                    return cached
                except (json.JSONDecodeError, TypeError):
                    pass

    segments: dict[str, float] = {}
    source_used = "none"

    # ── Source 1 : FMP ───────────────────────────────────────────────────────
    segments = await fetch_product_segments(ticker, fmp_key)
    if segments:
        source_used = "fmp"

    # ── Source 2 : ESEF / info-financiere.gouv.fr (tickers FR) ───────────────
    if not segments and _is_french_ticker(ticker):
        log.info("FMP empty for %s — trying ESEF (info-financiere.gouv.fr)", ticker)
        segments = await fetch_segments_from_esef(ticker)
        if segments:
            source_used = "esef"

    # ── Source 3 : SEC EDGAR (tickers US) ────────────────────────────────────
    if not segments and _is_us_ticker(ticker):
        log.info("FMP empty for %s — trying SEC EDGAR", ticker)
        segments = await fetch_segments_from_edgar(ticker)
        if segments:
            source_used = "edgar"

    # ── Calcul ratio haram ───────────────────────────────────────────────────
    halal_result = classify_segments(segments) if segments else None
    haram_ratio  = halal_result.haram_ratio if halal_result else None

    # ── Persistance ──────────────────────────────────────────────────────────
    await db_conn.execute(
        """
        UPDATE ticker_fundamentals
        SET revenue_segments    = $1::jsonb,
            haram_revenue_ratio = $2,
            segments_fetched_at = $3
        WHERE ticker = $4
        """,
        json.dumps(segments) if segments else None,
        haram_ratio,
        datetime.now(timezone.utc),
        ticker,
    )

    if segments:
        log.info(
            "Segments persisted for %s (source: %s): %d segments, haram=%.1f%%",
            ticker, source_used, len(segments), (haram_ratio or 0) * 100,
        )
    else:
        log.info("No segments found for %s — proxy will be used for Sharia criterion 4", ticker)

    return segments


async def enrich_universe_segments(
    fmp_key:  str,
    db_conn,
    *,
    universe:      Optional[str] = None,
    force_refresh: bool = False,
    concurrency:   int = 5,
) -> dict[str, dict[str, float]]:
    """Enrichit tous les tickers d'un univers."""
    if universe:
        rows = await db_conn.fetch(
            "SELECT ticker FROM ticker_fundamentals WHERE universe = $1", universe
        )
    else:
        rows = await db_conn.fetch("SELECT ticker FROM ticker_fundamentals")

    tickers = [r["ticker"] for r in rows]
    log.info("Enriching segments for %d tickers (universe=%s)", len(tickers), universe or "all")

    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, dict[str, float]] = {}

    async def _enrich_one(ticker: str) -> None:
        async with semaphore:
            try:
                segs = await enrich_ticker_segments(
                    ticker, fmp_key, db_conn, force_refresh=force_refresh
                )
                results[ticker] = segs
                await asyncio.sleep(0.2)
            except Exception as exc:
                log.error("Segment enrichment failed for %s: %s", ticker, exc)
                results[ticker] = {}

    await asyncio.gather(*[_enrich_one(t) for t in tickers])

    covered = sum(1 for s in results.values() if s)
    log.info("Segment enrichment complete: %d/%d covered", covered, len(tickers))
    return results
