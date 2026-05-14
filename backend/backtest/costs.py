"""
:file: api/backtest/costs.py
:brief: Real cost model: broker commissions, bid-ask spread/slippage, FX,
        and French taxes (PFU, TTF).

        All functions are pure — they take trade details and return cost in EUR.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

from typing import Literal

from api.config import (
    BROKER_FEES,
    SLIPPAGE_BPS,
    TAX_RATES,
)


def _broker_schedule(broker: str) -> dict:
    return BROKER_FEES.get(broker.lower(), BROKER_FEES["default"])


# ─────────────────────────────────────────────────────────────────────────────
# Commission
# ─────────────────────────────────────────────────────────────────────────────


def broker_commission(
    notional_eur: float,
    broker: str = "default",
    asset_type: Literal["stock_eu", "stock_us", "etf"] = "stock_eu",
) -> float:
    """Compute broker commission in EUR.

    :param notional_eur: trade size in EUR (already converted from USD if needed)
    :param broker: broker name key (see config.BROKER_FEES)
    :param asset_type: ``'stock_eu'`` | ``'stock_us'`` | ``'etf'``
    :returns: commission in EUR (always positive)
    """
    sch = _broker_schedule(broker)

    if broker.lower() == "fortuneo" and asset_type == "stock_us":
        # Fortuneo special schedule for US equities
        threshold = sch.get("stock_us_flat_threshold", 7_500.0)
        if notional_eur <= threshold:
            return float(sch.get("stock_us_flat_fee", 50.0))
        else:
            return float(
                notional_eur * sch.get("stock_us_pct_above", 0.002)
                + sch.get("stock_us_fixed_above", 9.0)
            )

    fixed = float(sch.get(f"{asset_type}_fixed", sch.get("stock_eu_fixed", 1.0)))
    pct = float(sch.get(f"{asset_type}_pct", sch.get("stock_eu_pct", 0.001)))
    fee = fixed + notional_eur * pct
    fee = max(fee, float(sch.get("min_fee", 0.0)))
    max_f = sch.get("max_fee")
    if max_f is not None:
        fee = min(fee, float(max_f))
    return fee


# ─────────────────────────────────────────────────────────────────────────────
# Slippage
# ─────────────────────────────────────────────────────────────────────────────


def slippage_cost(
    notional_eur: float,
    cap_size: Literal["large_cap", "mid_cap", "small_cap", "etf"] = "mid_cap",
) -> float:
    """Estimate bid-ask / slippage cost in EUR.

    :param cap_size: category determining BPS
    """
    bps = SLIPPAGE_BPS.get(cap_size, SLIPPAGE_BPS["mid_cap"])
    return notional_eur * bps / 10_000.0


# ─────────────────────────────────────────────────────────────────────────────
# FX cost (EUR/USD spread)
# ─────────────────────────────────────────────────────────────────────────────


def fx_spread_cost(
    notional_eur: float,
    currency: str = "USD",
    spread_bps: float = 3.0,  # retail FX spread ~3 bps
) -> float:
    """Estimate FX conversion cost for non-EUR assets."""
    if currency.upper() == "EUR":
        return 0.0
    return notional_eur * spread_bps / 10_000.0


# ─────────────────────────────────────────────────────────────────────────────
# TTF (Taxe sur les transactions financières)
# ─────────────────────────────────────────────────────────────────────────────


def ttf_tax(
    notional_eur: float,
    market_cap_eur: float = 2e9,  # default: large-cap (TTF applies)
) -> float:
    """French TTF — 0.1 % on buy-side for companies with market cap > 1 Bn EUR."""
    if market_cap_eur < TAX_RATES["ttf_threshold_market_cap"]:
        return 0.0
    return notional_eur * TAX_RATES["ttf_rate"]


# ─────────────────────────────────────────────────────────────────────────────
# Capital gains tax
# ─────────────────────────────────────────────────────────────────────────────


def capital_gains_tax(
    gain_eur: float,
    account_type: str = "CTO",
    pea_years: int = 0,
) -> float:
    """Compute French capital gains tax on realised profits.

    :param account_type: ``'CTO'`` | ``'PEA'``
    :param pea_years: years since PEA opening (exempt from IR after 5 y)
    """
    if gain_eur <= 0:
        return 0.0

    if account_type.upper() == "PEA":
        if pea_years >= TAX_RATES["pea_capital_exempt_years"]:
            return gain_eur * TAX_RATES["pea_social_rate"]
        else:
            return gain_eur * TAX_RATES["pfu_rate"]

    return gain_eur * TAX_RATES["pfu_rate"]


# ─────────────────────────────────────────────────────────────────────────────
# Total round-trip cost
# ─────────────────────────────────────────────────────────────────────────────


def total_trade_cost(
    notional_eur: float,
    broker: str = "default",
    asset_type: Literal["stock_eu", "stock_us", "etf"] = "stock_eu",
    cap_size: Literal["large_cap", "mid_cap", "small_cap", "etf"] = "mid_cap",
    currency: str = "EUR",
    market_cap_eur: float = 2e9,
    side: Literal["buy", "sell"] = "buy",
) -> dict[str, float]:
    """Compute all costs for a single trade.

    :returns: dict with keys commission, slippage, fx_spread, ttf, total
    """
    comm = broker_commission(notional_eur, broker, asset_type)
    slip = slippage_cost(notional_eur, cap_size)
    fx = fx_spread_cost(notional_eur, currency)
    tax = ttf_tax(notional_eur, market_cap_eur) if side == "buy" else 0.0
    total = comm + slip + fx + tax
    return {
        "commission": comm,
        "slippage": slip,
        "fx_spread": fx,
        "ttf": tax,
        "total": total,
        "notional": notional_eur,
        "cost_pct": total / notional_eur if notional_eur > 0 else 0.0,
    }
