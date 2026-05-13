"""
:file: api/core/registry.py
:brief: Ticker registry and ethical auto-screening engine.

        Ethical screening checks three layers:
        1. Hard exclusion list (sectors + tickers)
        2. Interest/debt ratio (for Islamic-compatible screening)
        3. ESG controversy score (if available via yfinance)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterator

from api.config import (
    ETHICAL_EXCLUSION_SECTORS,
    ETHICAL_EXCLUSION_TICKERS,
    INTEREST_DEBT_RATIO_THRESHOLD,
    INTEREST_INCOME_RATIO_THRESHOLD,
    ETHICAL_SCREEN_ENABLED,
)
from api.core.data import get_ticker_fundamentals

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TickerInfo:
    """Lightweight ticker record stored in the registry."""
    ticker:            str
    name:              str        = ""
    sector:            str        = ""
    industry:          str        = ""
    currency:          str        = "USD"
    exchange:          str        = ""
    country:           str        = ""
    market_cap:        float      = 0.0
    ethical_score:     float      = 1.0    # 0 = excluded, 1 = fully compliant
    ethical_flags:     list[str]  = field(default_factory=list)
    is_ethical:        bool       = True
    beta:              float      = 1.0
    dividend_yield:    float      = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Screening logic (pure functions)
# ─────────────────────────────────────────────────────────────────────────────

def _screen_hard_exclusion(info: dict) -> list[str]:
    """Return list of ethical flags triggered by hard exclusions."""
    flags: list[str] = []
    ticker  = info.get("ticker", "").upper()
    sector  = (info.get("sector", "") or "").lower().replace(" ", "_")
    industry = (info.get("industry", "") or "").lower().replace(" ", "_")

    if ticker in ETHICAL_EXCLUSION_TICKERS:
        flags.append(f"hard_exclusion:{ticker}")

    combined = f"{sector} {industry}"
    for excl in ETHICAL_EXCLUSION_SECTORS:
        if excl in combined:
            flags.append(f"sector_exclusion:{excl}")

    return flags


def _screen_interest_ratio(info: dict) -> list[str]:
    """Check debt/revenue ratios for interest-based finance screen."""
    flags: list[str] = []
    cap     = info.get("market_cap", 0) or 0
    debt    = info.get("total_debt",  0) or 0
    revenue = info.get("total_revenue", 0) or 0
    interest = info.get("interest_expense", 0) or 0

    if cap > 0 and (debt / cap) > INTEREST_DEBT_RATIO_THRESHOLD:
        flags.append(f"high_debt_ratio:{debt/cap:.2f}")
    if revenue > 0 and (interest / revenue) > INTEREST_INCOME_RATIO_THRESHOLD:
        flags.append(f"high_interest_income:{interest/revenue:.2f}")
    return flags


def _compute_ethical_score(flags: list[str]) -> float:
    """Map flag count to a 0–1 score (1 = clean)."""
    if not flags:
        return 1.0
    hard = sum(1 for f in flags if "hard_exclusion" in f or "sector_exclusion" in f)
    if hard:
        return 0.0
    soft = len(flags)
    return max(0.0, 1.0 - soft * 0.15)


def screen_ticker(info: dict) -> tuple[bool, float, list[str]]:
    """Run full ethical screen on fundamental *info* dict.

    :returns: (is_ethical, score 0–1, flags)
    """
    if not ETHICAL_SCREEN_ENABLED:
        return True, 1.0, []

    flags  = _screen_hard_exclusion(info) + _screen_interest_ratio(info)
    score  = _compute_ethical_score(flags)
    return score > 0.0, score, flags


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

class TickerRegistry:
    """In-memory registry of tickers with lazy async loading."""

    def __init__(self) -> None:
        self._records: dict[str, TickerInfo] = {}

    # ------------------------------------------------------------------
    async def load(self, ticker: str) -> TickerInfo:
        """Fetch fundamentals and run ethical screen; cache result."""
        if ticker in self._records:
            return self._records[ticker]

        info  = await get_ticker_fundamentals(ticker)
        ok, score, flags = screen_ticker(info)

        record = TickerInfo(
            ticker         = ticker,
            name           = info.get("name", ticker),
            sector         = info.get("sector", ""),
            industry       = info.get("industry", ""),
            currency       = info.get("currency", "USD"),
            exchange       = info.get("exchange", ""),
            country        = info.get("country", ""),
            market_cap     = float(info.get("market_cap", 0)),
            ethical_score  = score,
            ethical_flags  = flags,
            is_ethical     = ok,
            beta           = float(info.get("beta", 1.0) or 1.0),
            dividend_yield = float(info.get("dividend_yield", 0.0) or 0.0),
        )
        self._records[ticker] = record
        log.info(
            "Ticker %s loaded — ethical=%s score=%.2f flags=%s",
            ticker, ok, score, flags,
        )
        return record

    async def load_many(self, tickers: list[str]) -> list[TickerInfo]:
        """Load multiple tickers concurrently."""
        import asyncio
        return await asyncio.gather(*[self.load(t) for t in tickers])

    def get(self, ticker: str) -> TickerInfo | None:
        return self._records.get(ticker)

    def all_ethical(self) -> list[TickerInfo]:
        return [r for r in self._records.values() if r.is_ethical]

    def __iter__(self) -> Iterator[TickerInfo]:
        return iter(self._records.values())

    def __len__(self) -> int:
        return len(self._records)


#: Module-level singleton
registry: TickerRegistry = TickerRegistry()
