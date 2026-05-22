"""
:file: backend/core/segment_enricher.py
:brief: Orchestrateur pour l'enrichissement des revenus par segment.

        Pipeline :
        1. Tente FMP /revenue-product-segmentation (meilleure couverture, labels lisibles)
        2. Si vide → tente SEC EDGAR (bon pour tickers US 10-K)
        3. Si vide → retourne {} (critère 4 utilisera le proxy interest_expense)
        4. Persiste dans ticker_fundamentals.revenue_segments (JSONB)
        5. Calcule et persiste haram_revenue_ratio

        Appelé depuis :
        - daily_update() → enrichit les tickers mis à jour
        - POST /api/screener/enrich-segments → enrichissement manuel via UI
        - run_sharia_screen() → en temps réel si segments manquants

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.core.fmp_segments  import fetch_product_segments
from backend.core.sec_segments  import fetch_segments_from_edgar
from backend.quant.halal_classifier import classify_segments

log = logging.getLogger(__name__)


async def enrich_ticker_segments(
    ticker:   str,
    fmp_key:  str,
    db_conn,                        # asyncpg connection ou pool
    *,
    force_refresh: bool = False,
) -> dict[str, float]:
    """
    Enrichit un ticker avec ses revenus par segment.

    Args:
        ticker:        Ticker (ex: "MC.PA", "AAPL")
        fmp_key:       Clé API FMP
        db_conn:       Connection asyncpg (ou pool)
        force_refresh: Si True, ignore le cache et re-fetche

    Returns:
        Dict {segment_name: fraction} (peut être vide si aucune source).
    """
    # ── Cache : si déjà dans la DB et récent (< 90 jours), skip ──────────────
    if not force_refresh:
        row = await db_conn.fetchrow(
            """
            SELECT revenue_segments, segments_fetched_at
            FROM ticker_fundamentals
            WHERE ticker = $1
            """,
            ticker,
        )
        if row and row["revenue_segments"] and row["segments_fetched_at"]:
            age_days = (
                datetime.now(timezone.utc) - row["segments_fetched_at"].replace(tzinfo=timezone.utc)
            ).days
            if age_days < 90:
                try:
                    cached = json.loads(row["revenue_segments"])
                    log.debug("Segments cache hit for %s (%d days old)", ticker, age_days)
                    return cached
                except (json.JSONDecodeError, TypeError):
                    pass

    # ── Source 1 : FMP ────────────────────────────────────────────────────────
    segments = await fetch_product_segments(ticker, fmp_key)

    # ── Source 2 : EDGAR (fallback US tickers) ────────────────────────────────
    if not segments:
        log.info("FMP segments empty for %s — trying EDGAR", ticker)
        segments = await fetch_segments_from_edgar(ticker)

    # ── Calcul ratio haram ───────────────────────────────────────────────────
    halal_result = classify_segments(segments) if segments else None
    haram_ratio  = halal_result.haram_ratio if halal_result else None

    # ── Persistance ──────────────────────────────────────────────────────────
    await db_conn.execute(
        """
        UPDATE ticker_fundamentals
        SET
            revenue_segments    = $1::jsonb,
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
            "Segments persisted for %s: %d segments, haram_ratio=%.1f%%",
            ticker, len(segments), (haram_ratio or 0) * 100,
        )
    else:
        log.info("No segments found for %s — proxy will be used", ticker)

    return segments


async def enrich_universe_segments(
    fmp_key:  str,
    db_conn,
    *,
    universe:      Optional[str] = None,
    force_refresh: bool = False,
    concurrency:   int = 5,
) -> dict[str, dict[str, float]]:
    """
    Enrichit tous les tickers d'un univers (ou tous si universe=None).

    Args:
        fmp_key:       Clé API FMP
        db_conn:       Connection asyncpg
        universe:      Filtre univers (ex: "sp500", "cac40") ou None pour tous
        force_refresh: Re-fetch même si données récentes
        concurrency:   Nombre de requêtes parallèles (attention aux rate limits FMP)

    Returns:
        Dict {ticker: segments}
    """
    # Récupère la liste des tickers
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
                # Délai léger pour respecter les rate limits FMP (300 req/min)
                await asyncio.sleep(0.2)
            except Exception as exc:
                log.error("Segment enrichment failed for %s: %s", ticker, exc)
                results[ticker] = {}

    await asyncio.gather(*[_enrich_one(t) for t in tickers])

    covered = sum(1 for s in results.values() if s)
    log.info(
        "Segment enrichment complete: %d/%d tickers covered",
        covered, len(tickers),
    )
    return results
