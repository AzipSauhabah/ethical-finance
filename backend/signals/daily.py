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


async def compute_daily_signals(tickers: list[str], lookback_days: int = 60) -> list[dict]:
    """Compute today's signal for each ticker using a multi-indicator vote.

    :param tickers: list of ticker symbols
    :param lookback_days: price history needed to compute signals
    :returns: list of dicts with keys: ticker, signal, strength, indicators
    """
    end = date.today()
    start = end - timedelta(days=lookback_days + 30)
    prices = await get_prices(tickers, start=start, end=end)

    results = []
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
        vote = sma_sig + rsi_sig + macd_sig + mom_sig
        signal = 1 if vote >= 2 else (-1 if vote <= -2 else 0)
        label = "BUY" if signal == 1 else ("SELL" if signal == -1 else "HOLD")

        results.append(
            {
                "ticker": ticker,
                "signal": signal,
                "label": label,
                "strength": abs(vote) / 4.0,
                "indicators": {
                    "sma_crossover": sma_sig,
                    "rsi": rsi_sig,
                    "macd": macd_sig,
                    "momentum": mom_sig,
                },
                "date": str(end),
            }
        )

    return results
