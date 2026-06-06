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
from backend.quant.halal_classifier import (
    classify_segments,
    classify_from_proxy,
    SegmentClass,
)

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
SHARIA_LIQUIDITY_RATIO_MAX = 0.33
SHARIA_INCOME_RATIO_MAX    = 0.05  # cash + interest-bearing securities / market cap
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
    # Ratios bruts Finance Islamique
    haram_revenue_ratio: float | None = None
    sharia_debt_ratio:   float | None = None
    sharia_income_ratio: float | None = None
    revenue_segments:    dict  | None = None

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

    Quatre critères :
      1. Secteur     — activité halal (blacklist sectorielle)
      2. Ratio dette — interest-bearing debt / market cap ≤ 33 %
      3. Liquidité   — (cash + interest-bearing securities) / market cap ≤ 33 %
      4. Revenus     — revenus non-permissibles ≤ 5 % du CA total

    Critère 4 :
      - Source primaire : revenue_segments JSONB (FMP ou EDGAR)
      - Fallback proxy  : interest_expense / total_revenue
    """
    checks: list[ScreenCheck] = []
    sector   = (info.get("sector",   "") or "").lower()
    industry = (info.get("industry", "") or "").lower()
    combined = f"{sector} {industry}"

    # Critère 1 : Activité halal
    matched = [s for s in SHARIA_SECTOR_BLACKLIST if s in combined]
    checks.append(ScreenCheck(
        name="1. Activité autorisée (Sharia)",
        passed=len(matched) == 0,
        description=(
            "Aucune activité non-conforme détectée"
            if not matched
            else f"Activités non-conformes : {', '.join(matched)}"
        ),
    ))


    # ── Court-circuit banques / assurances (AAOIFI) ──────────────────────────
    # Les banques et assurances échouent structurellement :
    #   - Critère 2 : dette portant intérêts >>> 33% market cap (business model)
    #   - Critère 3 : revenus d'intérêts >>> 33% market cap
    #   - Critère 4 : intérêts = activité principale
    # Pas besoin de données — le secteur suffit.
    _BANK_SECTORS = {
        "bank", "banking", "financial services", "insurance",
        "diversified financials", "capital markets", "thrifts",
        "consumer finance", "mortgage",
    }
    _sector_lower = (info.get("sector", "") or "").lower()
    _industry_lower = (info.get("industry", "") or "").lower()
    _is_bank = any(s in _sector_lower or s in _industry_lower for s in _BANK_SECTORS)

    if _is_bank:
        checks.append(ScreenCheck(
            name="2. Ratio dette a interets (<=33%)",
            passed=False,
            value=1.0,
            threshold=SHARIA_DEBT_RATIO_MAX,
            description="Banque/assurance : dette portant interets structurellement > 33% market cap",
        ))
        checks.append(ScreenCheck(
            name="3. Ratio liquidites (<=33%)",
            passed=False,
            value=1.0,
            threshold=SHARIA_LIQUIDITY_RATIO_MAX,
            description="Banque/assurance : produits d'interets structurellement > 33% market cap",
        ))
        checks.append(ScreenCheck(
            name="4. Revenus non-permissibles (<=5%)",
            passed=False,
            value=1.0,
            threshold=SHARIA_INCOME_RATIO_MAX,
            description="Banque/assurance : revenus d'interets = activite principale (non-permissible)",
        ))
        return ShariaScreen(
            passed=False,
            score=0.0,
            checks=checks,
        )

    # Critère 2 : Ratio dette portant intérêts / capitalisation ≤ 33% (AAOIFI)
    cap = float(info.get("market_cap", 0) or 0)
    ibd = float(
        info.get("interest_bearing_debt")
        or ((info.get("short_term_debt") or 0) + (info.get("long_term_debt") or 0))
        or info.get("total_debt")
        or 0
    )
    debt_ratio = (ibd / cap) if cap > 0 else 0.0
    debt_src = "ibd" if info.get("interest_bearing_debt") else "total_debt (fallback)"
    checks.append(ScreenCheck(
        name="2. Ratio dette a interets (<=33%)",
        passed=debt_ratio <= SHARIA_DEBT_RATIO_MAX,
        value=debt_ratio,
        threshold=SHARIA_DEBT_RATIO_MAX,
        description=f"Dette portant interets / cap = {debt_ratio:.1%} [{debt_src}]",
    ))

    # Critère 3 : Ratio liquidités / capitalisation ≤ 33 %
    cash      = float(info.get("total_cash", 0) or 0)
    liq_ratio = (cash / cap) if cap > 0 else 0.0
    checks.append(ScreenCheck(
        name="3. Ratio liquidités productives (≤ 33 %)",
        passed=liq_ratio <= SHARIA_LIQUIDITY_RATIO_MAX,
        value=liq_ratio,
        threshold=SHARIA_LIQUIDITY_RATIO_MAX,
        description=f"Trésorerie portant intérêts / capitalisation = {liq_ratio:.1%}",
    ))

    # Critère 4 : Revenus non-permissibles ≤ 5 %
    revenue_segments = info.get("revenue_segments")  # dict ou None

    if revenue_segments and isinstance(revenue_segments, dict) and len(revenue_segments) > 0:
        halal_result = classify_segments(
            revenue_segments, threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX
        )
        haram_segs     = [s for s in halal_result.segments if s.cls == SegmentClass.HARAM]
        uncertain_segs = [s for s in halal_result.segments if s.cls == SegmentClass.UNCERTAIN]

        if haram_segs:
            detail = "Segments haram : " + ", ".join(
                f"{s.name} ({s.fraction:.0%})" for s in haram_segs
            )
        else:
            detail = "Aucun segment haram identifié"

        if uncertain_segs and halal_result.uncertain_ratio > 0.10:
            detail += (
                f" | Non-classifiés : {halal_result.uncertain_ratio:.0%}"
                " (vérification manuelle conseillée)"
            )

        checks.append(ScreenCheck(
            name="4. Revenus non-permissibles (≤ 5 %)",
            passed=halal_result.passed,
            value=halal_result.haram_ratio,
            threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX,
            description=f"{detail} → {halal_result.haram_ratio:.1%} du CA",
        ))
    else:
        interest_expense = float(info.get("interest_expense", 0) or 0)
        total_revenue    = float(info.get("total_revenue",    1) or 1)
        proxy_result = classify_from_proxy(
            interest_expense, total_revenue,
            threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX,
        )
        checks.append(ScreenCheck(
            name="4. Revenus non-permissibles (≤ 5 %) [proxy]",
            passed=proxy_result.passed,
            value=proxy_result.haram_ratio,
            threshold=SHARIA_NON_PERMISSIBLE_INCOME_MAX,
            description=(
                "⚠ Proxy utilisé (segments non disponibles) — "
                f"interest_expense / total_revenue = {proxy_result.haram_ratio:.1%}. "
                "Lancer l'enrichissement des segments pour plus de précision."
            ),
        ))

    passed     = all(c.passed for c in checks)
    score      = sum(1 for c in checks if c.passed) / len(checks) if checks else 0.0

    return ShariaScreen(passed=passed, score=score, checks=checks)



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
            haram_revenue_ratio=info.get("haram_revenue_ratio"),
            sharia_debt_ratio=info.get("sharia_debt_ratio"),
            sharia_income_ratio=info.get("sharia_income_ratio"),
            revenue_segments=info.get("revenue_segments"),
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
        "haram_revenue_ratio": t.haram_revenue_ratio,
        "sharia_debt_ratio":   t.sharia_debt_ratio,
        "sharia_income_ratio": t.sharia_income_ratio,
        "revenue_segments":    t.revenue_segments,
    }
