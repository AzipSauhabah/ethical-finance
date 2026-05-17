"""
:file: api/core/registry.py
:brief: Ticker registry with two independent screens:
        * Ethical    — sector exclusions (weapons, tobacco, fossil, gambling)
        * Sharia     — AAOIFI-style financial purification ratios

        Each screen has its own pass/fail flag and detailed breakdown.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field

from backend.config import (
    ETHICAL_EXCLUSION_SECTORS,
    ETHICAL_EXCLUSION_TICKERS,
    INTEREST_DEBT_RATIO_THRESHOLD,
    INTEREST_INCOME_RATIO_THRESHOLD,
)
from backend.core.data import get_ticker_fundamentals

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Sharia screening criteria (AAOIFI / Dow Jones Islamic Market style)
# ─────────────────────────────────────────────────────────────────────────────

SHARIA_SECTOR_BLACKLIST = [
    # Riba (interest-based)
    "banks",
    "bank",
    "diversified financial",
    "consumer financial",
    "insurance",
    "capital markets",
    "asset management",
    # Haram products
    "alcohol",
    "brewers",
    "distillers",
    "wineries",
    "beverages alcoholic",
    "tobacco",
    "casino",
    "gambling",
    "resort",
    "hotel",
    "weapons",
    "defense",
    "aerospace defense",
    "adult entertainment",
    "pornography",
    # Pork
    "meat",
    "pork",
]

# AAOIFI thresholds
SHARIA_DEBT_RATIO_MAX = 0.33  # debt / market cap (or 24mo avg cap)
SHARIA_LIQUIDITY_RATIO_MAX = 0.33  # cash + interest-bearing securities / market cap
SHARIA_NON_PERMISSIBLE_INCOME_MAX = 0.05  # non-halal income / total revenue


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScreenCheck:
    """Single screening criterion result."""

    name: str
    passed: bool
    value: float | None = None
    threshold: float | None = None
    description: str = ""


@dataclass
class EthicalScreen:
    passed: bool
    score: float  # 0–1
    checks: list[ScreenCheck] = field(default_factory=list)


@dataclass
class ShariaScreen:
    passed: bool
    score: float
    checks: list[ScreenCheck] = field(default_factory=list)


@dataclass
class TickerInfo:
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    currency: str = "USD"
    exchange: str = ""
    country: str = ""
    market_cap: float = 0.0
    beta: float = 1.0
    dividend_yield: float = 0.0
    # Two independent screens
    ethical: EthicalScreen | None = None
    sharia: ShariaScreen | None = None

    # convenience flags
    @property
    def is_ethical(self) -> bool:
        return bool(self.ethical and self.ethical.passed)

    @property
    def is_sharia(self) -> bool:
        return bool(self.sharia and self.sharia.passed)


# ─────────────────────────────────────────────────────────────────────────────
# Ethical screen (sector + light interest filter)
# ─────────────────────────────────────────────────────────────────────────────


def run_ethical_screen(info: dict) -> EthicalScreen:
    checks: list[ScreenCheck] = []
    ticker = info.get("ticker", "").upper()
    sector = (info.get("sector", "") or "").lower()
    industry = (info.get("industry", "") or "").lower()

    # Hard ticker exclusion
    in_blacklist = ticker in ETHICAL_EXCLUSION_TICKERS
    checks.append(
        ScreenCheck(
            "Liste d'exclusion (ticker)",
            not in_blacklist,
            description=f"Ticker {'présent' if in_blacklist else 'absent'} de la liste éthique d'exclusion",
        )
    )

    # Sector exclusion
    combined = f"{sector} {industry}"
    matched_sectors = [s for s in ETHICAL_EXCLUSION_SECTORS if s in combined]
    checks.append(
        ScreenCheck(
            "Secteur autorisé (éthique)",
            len(matched_sectors) == 0,
            description=(
                "Aucun secteur exclu détecté"
                if not matched_sectors
                else f"Secteurs exclus détectés : {', '.join(matched_sectors)}"
            ),
        )
    )

    # Light interest filter (informational, not blocking)
    cap = info.get("market_cap", 0) or 0
    debt = info.get("total_debt", 0) or 0
    revenue = info.get("total_revenue", 0) or 0
    interest = info.get("interest_expense", 0) or 0

    debt_ratio = (debt / cap) if cap > 0 else 0.0
    interest_ratio = (interest / revenue) if revenue > 0 else 0.0

    checks.append(
        ScreenCheck(
            "Ratio dette / capitalisation",
            debt_ratio <= INTEREST_DEBT_RATIO_THRESHOLD,
            value=debt_ratio,
            threshold=INTEREST_DEBT_RATIO_THRESHOLD,
            description=f"Dette totale / market cap = {debt_ratio:.1%} (seuil informatif : {INTEREST_DEBT_RATIO_THRESHOLD:.0%})",
        )
    )
    checks.append(
        ScreenCheck(
            "Revenus d'intérêts / CA",
            interest_ratio <= INTEREST_INCOME_RATIO_THRESHOLD,
            value=interest_ratio,
            threshold=INTEREST_INCOME_RATIO_THRESHOLD,
            description=f"Intérêts / CA = {interest_ratio:.1%} (seuil : {INTEREST_INCOME_RATIO_THRESHOLD:.0%})",
        )
    )

    # Ethical passes if no HARD exclusion (ticker or sector)
    passed = all(c.passed for c in checks[:2])
    soft_failed = sum(1 for c in checks[2:] if not c.passed)
    score = 1.0 if passed else 0.0
    if passed:
        score = max(0.0, 1.0 - soft_failed * 0.15)
    return EthicalScreen(passed=passed, score=score, checks=checks)


# ─────────────────────────────────────────────────────────────────────────────
# Sharia screen (AAOIFI-style with full breakdown)
# ─────────────────────────────────────────────────────────────────────────────


def run_sharia_screen(info: dict) -> ShariaScreen:
    """AAOIFI / Dow Jones Islamic Market style screen.

    Four pillars:
      1. Sector — business activity must be halal
      2. Debt ratio — interest-bearing debt / market cap ≤ 33 %
      3. Liquidity — (cash + interest-bearing securities) / market cap ≤ 33 %
      4. Non-permissible income ≤ 5 % of total revenue

    A stock passes only if all four pass.
    """
    checks: list[ScreenCheck] = []
    sector = (info.get("sector", "") or "").lower()
    industry = (info.get("industry", "") or "").lower()
    combined = f"{sector} {industry}"

    # 1. Sector
    matched = [s for s in SHARIA_SECTOR_BLACKLIST if s in combined]
    checks.append(
        ScreenCheck(
            "1. Activité autorisée (Sharia)",
            len(matched) == 0,
            description=(
                "Aucune activité non-conforme détectée"
                if not matched
                else f"Activités non-conformes : {', '.join(matched)}"
            ),
        )
    )

    # 2. Debt ratio
    cap = info.get("market_cap", 0) or 0
    debt = info.get("total_debt", 0) or 0
    debt_ratio = (debt / cap) if cap > 0 else 0.0
    checks.append(
        ScreenCheck(
            "2. Ratio dette à intérêts (≤ 33 %)",
            debt_ratio <= SHARIA_DEBT_RATIO_MAX,
            value=debt_ratio,
            threshold=SHARIA_DEBT_RATIO_MAX,
            description=f"Dette portant intérêts / capitalisation = {debt_ratio:.1%}",
        )
    )

    # 3. Liquidity ratio (proxy: cash / market cap)
    cash = info.get("total_cash", 0) or 0
    liq_ratio = (cash / cap) if cap > 0 else 0.0
    checks.append(
        ScreenCheck(
            "3. Liquidités productives d'intérêts (≤ 33 %)",
            liq_ratio <= SHARIA_LIQUIDITY_RATIO_MAX,
            value=liq_ratio,
            threshold=SHARIA_LIQUIDITY_RATIO_MAX,
            description=f"Cash + titres rémunérés / capitalisation = {liq_ratio:.1%}",
        )
    )

    # 4. Non-permissible income
    revenue = info.get("total_revenue", 0) or 0
    interest = info.get("interest_expense", 0) or 0
    npi_ratio = (interest / revenue) if revenue > 0 else 0.0
    checks.append(
        ScreenCheck(
            "4. Revenus non-permis (≤ 5 %)",
            npi_ratio <= SHARIA_NON_PERMISSIBLE_INCOME_MAX,
            value=npi_ratio,
            threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX,
            description=f"Intérêts perçus / CA = {npi_ratio:.1%}",
        )
    )

    passed = all(c.passed for c in checks)
    score = sum(1 for c in checks if c.passed) / len(checks)
    return ShariaScreen(passed=passed, score=score, checks=checks)


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────


class TickerRegistry:
    def __init__(self) -> None:
        self._records: dict[str, TickerInfo] = {}

    async def load(self, ticker: str) -> TickerInfo:
        if ticker in self._records:
            return self._records[ticker]

        info = await get_ticker_fundamentals(ticker)

        record = TickerInfo(
            ticker=ticker,
            name=info.get("name", ticker),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            currency=info.get("currency", "USD"),
            exchange=info.get("exchange", ""),
            country=info.get("country", ""),
            market_cap=float(info.get("market_cap", 0) or 0),
            beta=float(info.get("beta", 1.0) or 1.0),
            dividend_yield=float(info.get("dividend_yield", 0.0) or 0.0),
            ethical=run_ethical_screen(info),
            sharia=run_sharia_screen(info),
        )
        self._records[ticker] = record
        log.info("Loaded %s — ethical=%s sharia=%s", ticker, record.is_ethical, record.is_sharia)
        return record

    async def load_many(self, tickers: list[str]) -> list[TickerInfo]:
        import asyncio

        return await asyncio.gather(*[self.load(t) for t in tickers])

    def get(self, ticker: str) -> TickerInfo | None:
        return self._records.get(ticker)

    def __iter__(self) -> Iterator[TickerInfo]:
        return iter(self._records.values())


registry: TickerRegistry = TickerRegistry()


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation helper for API
# ─────────────────────────────────────────────────────────────────────────────


def ticker_to_dict(t: TickerInfo) -> dict:
    return {
        "ticker": t.ticker,
        "name": t.name,
        "sector": t.sector,
        "industry": t.industry,
        "currency": t.currency,
        "exchange": t.exchange,
        "country": t.country,
        "market_cap": t.market_cap,
        "beta": t.beta,
        "dividend_yield": t.dividend_yield,
        "is_ethical": t.is_ethical,
        "is_sharia": t.is_sharia,
        "ethical": {
            "passed": t.ethical.passed if t.ethical else False,
            "score": t.ethical.score if t.ethical else 0,
            "checks": [asdict(c) for c in t.ethical.checks] if t.ethical else [],
        },
        "sharia": {
            "passed": t.sharia.passed if t.sharia else False,
            "score": t.sharia.score if t.sharia else 0,
            "checks": [asdict(c) for c in t.sharia.checks] if t.sharia else [],
        },
    }
