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


def _sentiment_signal(score: float) -> int:
    """Convert sentiment score to -1/0/+1 signal."""
    if score >= 0.15:
        return 1
    if score <= -0.15:
        return -1
    return 0


def _sent_label(sent_sig: int) -> str:
    """Convert sentiment signal to label."""
    if sent_sig == 1:
        return "bullish"
    if sent_sig == -1:
        return "bearish"
    return "neutral"


def _compute_ticker_signal(
    ticker: str,
    prices,
    sentiment_scores: dict,
    include_sentiment: bool,
    end,
) -> dict | None:
    """Compute signal for a single ticker. Returns None if insufficient data."""
    if ticker not in prices.columns:
        return None
    p = prices[ticker].dropna()
    if len(p) < 20:
        return None

    sma_sig = int(sma_crossover_signal(p).iloc[-1])
    rsi_sig = int(rsi_signal(p).iloc[-1])
    macd_sig = int(macd_signal(p).iloc[-1])
    mom_sig = int(momentum_signal(p).iloc[-1])

    sent_score = sentiment_scores.get(ticker, 0.0)
    sent_sig = _sentiment_signal(sent_score)

    vote = sma_sig + rsi_sig + macd_sig + mom_sig
    if include_sentiment:
        vote += sent_sig

    max_vote = 5 if include_sentiment else 4
    if vote >= 2:
        signal = 1
    elif vote <= -2:
        signal = -1
    else:
        signal = 0
    if signal == 1:
        label = "BUY"
    elif signal == -1:
        label = "SELL"
    else:
        label = "HOLD"

    return {
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
            "signal": _sent_label(sent_sig),
        },
        "date": str(end),
    }


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
            sentiment_scores = {t: d.get("score", 0.0) for t, d in sentiment_data.items()}
        except Exception as e:
            log.warning("Sentiment fetch error: %s", e)

    results = []
    for ticker in tickers:
        result = _compute_ticker_signal(ticker, prices, sentiment_scores, include_sentiment, end)
        if result is not None:
            results.append(result)
    return results
