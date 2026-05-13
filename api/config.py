"""
:file: api/config.py
:brief: Central configuration — ALL magic numbers live here.
        Import only this file for constants; never hard-code values elsewhere.

:copyright: 2024 Sauhabah — Ethical Finance Platform
:license: GPL-3.0
"""

from __future__ import annotations
import os
from typing import Final

# ─────────────────────────────────────────────────────────────────────────────
# Broker fee schedules (French / European retail brokers)
# Structure: fixed_eur + pct_notional, with min/max caps
# ─────────────────────────────────────────────────────────────────────────────
BROKER_FEES: Final[dict] = {
    "degiro": {
        "stock_eu_fixed": 0.50,
        "stock_eu_pct": 0.0004,
        "stock_us_fixed": 0.50,
        "stock_us_pct": 0.0004,
        "etf_fixed": 0.00,
        "etf_pct": 0.0000,
        "min_fee": 0.50,
        "max_fee": None,
    },
    "fortuneo": {
        # Fortuneo: 50 USD flat for US stocks up to ~7 500 USD notional
        # above that threshold: 0.20 % + 9 USD
        "stock_eu_fixed": 6.95,
        "stock_eu_pct": 0.0000,
        "stock_us_flat_threshold": 7_500.0,   # USD notional
        "stock_us_flat_fee": 50.0,            # USD
        "stock_us_pct_above": 0.002,          # 0.20 %
        "stock_us_fixed_above": 9.0,          # USD
        "min_fee": 6.95,
        "max_fee": None,
    },
    "bourse_direct": {
        "stock_eu_fixed": 0.99,
        "stock_eu_pct": 0.0000,
        "stock_us_fixed": 0.99,
        "stock_us_pct": 0.0000,
        "etf_fixed": 0.99,
        "etf_pct": 0.0000,
        "min_fee": 0.99,
        "max_fee": None,
    },
    "interactive_brokers": {
        "stock_eu_fixed": 0.00,
        "stock_eu_pct": 0.0005,
        "stock_us_fixed": 0.00,
        "stock_us_pct": 0.0005,
        "min_fee": 1.00,
        "max_fee": 1.0,
    },
    "default": {
        "stock_eu_fixed": 1.00,
        "stock_eu_pct": 0.001,
        "stock_us_fixed": 1.00,
        "stock_us_pct": 0.001,
        "min_fee": 1.00,
        "max_fee": None,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# French tax rates (PFU flat tax 2024)
# ─────────────────────────────────────────────────────────────────────────────
TAX_RATES: Final[dict] = {
    "pfu_rate": 0.30,                  # Prélèvement Forfaitaire Unique 30 %
    "income_tax_rate": 0.11,           # Marginal IR (bracket — user-overridable)
    "social_contributions": 0.172,     # CSG + CRDS
    "pea_social_rate": 0.172,          # PEA after 5 y: social charges only
    "pea_capital_exempt_years": 5,
    "ttf_rate": 0.001,                 # Taxe sur transactions financières 0.1 %
    "ttf_threshold_market_cap": 1e9,   # EUR — applies to cos with cap > 1 Bn
}

# ─────────────────────────────────────────────────────────────────────────────
# Slippage model (basis points)
# ─────────────────────────────────────────────────────────────────────────────
SLIPPAGE_BPS: Final[dict[str, float]] = {
    "large_cap": 2.0,
    "mid_cap": 5.0,
    "small_cap": 15.0,
    "etf": 1.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# FX
# ─────────────────────────────────────────────────────────────────────────────
BASE_CURRENCY: Final[str] = "EUR"
FX_CACHE_TTL: Final[int] = 300          # seconds

# ─────────────────────────────────────────────────────────────────────────────
# Data sources (priority order)
# ─────────────────────────────────────────────────────────────────────────────
DATA_SOURCES: Final[list[str]] = ["yfinance", "stooq", "gbm_synthetic"]
DEFAULT_PERIOD: Final[str] = "5y"
MAX_PERIOD_YEARS: Final[int] = 20
PRICE_CACHE_TTL: Final[int] = 3_600     # 1 hour
LIVE_PRICE_CACHE_TTL: Final[int] = 60   # 1 minute
LIVE_PRICE_INTERVAL_SEC: Final[int] = 60

# ─────────────────────────────────────────────────────────────────────────────
# Risk / portfolio defaults
# ─────────────────────────────────────────────────────────────────────────────
RISK_FREE_RATE: Final[float] = 0.035    # OAT 10 ans ~3.5 %
DEFAULT_INITIAL_CAPITAL: Final[float] = 30_000.0   # EUR
DEFAULT_MONTHLY_CONTRIBUTION: Final[float] = 0.0

# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo
# ─────────────────────────────────────────────────────────────────────────────
MC_SIMULATIONS: Final[int] = 10_000
MC_HORIZON_DAYS: Final[int] = 252

# ─────────────────────────────────────────────────────────────────────────────
# Stress test windows
# ─────────────────────────────────────────────────────────────────────────────
STRESS_SCENARIOS: Final[dict] = {
    "gfc_2008":   {"start": "2008-09-01", "end": "2009-03-31", "label": "GFC 2008–09"},
    "covid_2020": {"start": "2020-02-19", "end": "2020-03-23", "label": "COVID Crash 2020"},
    "bear_2022":  {"start": "2022-01-03", "end": "2022-12-30", "label": "Bear Market 2022"},
    "dot_com":    {"start": "2000-03-10", "end": "2002-10-09", "label": "Dot-com Bust"},
    "eur_debt":   {"start": "2011-07-01", "end": "2012-07-01", "label": "EU Debt Crisis"},
}

# ─────────────────────────────────────────────────────────────────────────────
# Ethical / ESG screening
# ─────────────────────────────────────────────────────────────────────────────
ETHICAL_EXCLUSION_SECTORS: Final[list[str]] = [
    "weapons", "tobacco", "gambling", "pornography",
    "conventional_weapons", "controversial_weapons",
    "thermal_coal", "tar_sands",
]

ETHICAL_EXCLUSION_TICKERS: Final[list[str]] = [
    "LMT", "RTX", "NOC", "GD", "BA",       # Defense
    "XOM", "CVX", "BP", "SHEL", "TTE",     # Fossil fuels
    "MO", "PM", "BTI", "IMBBY",            # Tobacco
    "MGM", "WYNN", "LVS",                  # Gambling
]

# Interest-based exclusions (for Islamic finance screening)
INTEREST_DEBT_RATIO_THRESHOLD: Final[float] = 0.33   # total debt / market cap
INTEREST_INCOME_RATIO_THRESHOLD: Final[float] = 0.05  # interest income / total revenue

ETHICAL_SCREEN_ENABLED: Final[bool] = True

# ─────────────────────────────────────────────────────────────────────────────
# Benchmarks
# ─────────────────────────────────────────────────────────────────────────────
BENCHMARKS: Final[dict[str, str]] = {
    "US":  "^GSPC",    # S&P 500
    "FR":  "^FCHI",    # CAC 40
    "EU":  "^STOXX50E",
    "VOL": "^VIX",
}

# ─────────────────────────────────────────────────────────────────────────────
# Vercel KV
# ─────────────────────────────────────────────────────────────────────────────
KV_REST_API_URL: str  = os.getenv("KV_REST_API_URL", "")
KV_REST_API_TOKEN: str = os.getenv("KV_REST_API_TOKEN", "")

# ─────────────────────────────────────────────────────────────────────────────
# App meta
# ─────────────────────────────────────────────────────────────────────────────
APP_ENV: str          = os.getenv("APP_ENV", "development")
DEBUG: bool           = APP_ENV == "development"
API_VERSION: Final[str] = "2.0.0"
COPYRIGHT: Final[str]   = "© 2024 Sauhabah — Ethical Finance Platform"
DISCLAIMER: Final[str]  = (
    "Ce document est fourni à titre informatif uniquement et ne constitue pas "
    "un conseil en investissement. Les performances passées ne préjugent pas des "
    "performances futures. Tout investissement comporte un risque de perte en capital. "
    "Sauhabah Ethical Finance Platform n'est pas agréée par l'AMF."
)
