"""
:file: api/signals/daily.py
:brief: Daily buy/sell signals for each ticker in the portfolio.
        Updated by a background thread; consumed by the frontend "Next Moves" tab.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from backend.core.data import get_prices
from backend.quant.signals import (
    macd_signal,
    momentum_signal,
    rsi_signal,
    sma_crossover_signal,
)

log = logging.getLogger(__name__)


async def compute_daily_signals(
    tickers: list[str],
    lookback_days: int = 60,
    include_sentiment: bool = True,
) -> list[dict]:
    """Compute today's signal for each ticker using a multi-indicator vote.

    Vote system (max ±5) :
        - SMA Crossover  : ±1
        - RSI            : ±1
        - MACD           : ±1
        - Momentum       : ±1
        - Sentiment VADER: ±1 (si include_sentiment=True)

    BUY  si vote >= 2
    SELL si vote <= -2
    HOLD sinon

    :param tickers: list of ticker symbols
    :param lookback_days: price history needed to compute signals
    :param include_sentiment: inclure le score de sentiment VADER dans le vote
    :returns: list of dicts with keys: ticker, signal, strength, indicators
    """
    end = date.today()
    start = end - timedelta(days=lookback_days + 30)
    prices = await get_prices(tickers, start=start, end=end)

    # Sentiment en batch (un seul appel pour tous les tickers)
    sentiment_scores: dict[str, float] = {}
    if include_sentiment:
        try:
            import asyncio
            from backend.quant.sentiment import analyze_portfolio_sentiment
            loop = asyncio.get_event_loop()
            sentiment_data = await loop.run_in_executor(
                None,
                lambda: analyze_portfolio_sentiment(tickers[:20], delay=0.2),
            )
            sentiment_scores = {
                t: d.get("score", 0.0)
                for t, d in sentiment_data.items()
            }
        except Exception as e:
            log.warning("Sentiment fetch error: %s", e)

    results = []
    max_vote = 5 if include_sentiment else 4

    for ticker in tickers:
        if ticker not in prices.columns:
            continue
        p = prices[ticker].dropna()
        if len(p) < 20:
            continue

        sma_sig = int(sma_crossover_signal(p).iloc[-1])
        rsi_sig = int(rsi_signal(p).iloc[-1])
        macd_sig = int(macd_signal(p).iloc[-1])
        mom_sig = int(momentum_signal(p).iloc[-1])

        # Signal sentiment : bullish > 0.15 → +1, bearish < -0.15 → -1
        sent_score = sentiment_scores.get(ticker, 0.0)
        if sent_score >= 0.15:
            sent_sig = 1
        elif sent_score <= -0.15:
            sent_sig = -1
        else:
            sent_sig = 0

        vote = sma_sig + rsi_sig + macd_sig + mom_sig
        if include_sentiment:
            vote += sent_sig

        # Seuil adapté au nombre de signaux
        threshold = 2
        signal = 1 if vote >= threshold else (-1 if vote <= -threshold else 0)
        label = "BUY" if signal == 1 else ("SELL" if signal == -1 else "HOLD")

        results.append(
            {
                "ticker": ticker,
                "signal": signal,
                "label": label,
                "strength": round(abs(vote) / max_vote, 2),
                "indicators": {
                    "sma_crossover": sma_sig,
                    "rsi": rsi_sig,
                    "macd": macd_sig,
                    "momentum": mom_sig,
                    "sentiment": sent_sig,
                },
                "sentiment": {
                    "score": round(sent_score, 3),
                    "signal": "bullish" if sent_sig == 1 else ("bearish" if sent_sig == -1 else "neutral"),
                },
                "date": str(end),
            }
        )

    return results
