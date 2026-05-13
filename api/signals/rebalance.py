"""
:file: api/signals/rebalance.py
:brief: Rebalancing recommendations — given current portfolio weights vs
        target weights, produce a list of buy/sell orders that minimise
        turnover and respect integer share constraints + transaction costs.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Iterable

from api.backtest.costs import total_trade_cost

log = logging.getLogger(__name__)


@dataclass
class RebalanceOrder:
    ticker:        str
    side:          str         # 'buy' | 'sell' | 'hold'
    shares:        int
    price_eur:     float
    notional_eur:  float
    current_pct:   float
    target_pct:    float
    drift_pct:     float       # current_pct - target_pct
    cost_eur:      float
    rationale:     str


def compute_rebalance_orders(
    positions:     dict[str, dict],
    prices_eur:    dict[str, float],
    target_weights: dict[str, float],
    cash_eur:      float,
    broker:        str   = "default",
    drift_threshold: float = 0.05,    # 5 % drift triggers rebalance
) -> list[dict]:
    """Compute rebalancing orders.

    :param positions:        current holdings: ticker → {shares, currency, market_cap_eur}
    :param prices_eur:       latest prices in EUR
    :param target_weights:   target weights summing to ≤ 1
    :param cash_eur:         current cash balance
    :param drift_threshold:  minimum |drift| to trigger a trade
    :returns: list of order dicts (JSON-serialisable)
    """
    # Total NAV
    equity = sum(
        positions.get(t, {}).get("shares", 0) * prices_eur.get(t, 0)
        for t in positions
    )
    nav = equity + cash_eur
    if nav <= 0:
        return []

    orders: list[RebalanceOrder] = []
    all_tickers = set(positions) | set(target_weights)

    for ticker in all_tickers:
        price    = prices_eur.get(ticker, 0.0)
        if price <= 0:
            continue

        cur_shares  = positions.get(ticker, {}).get("shares", 0)
        currency    = positions.get(ticker, {}).get("currency", "USD")
        market_cap  = positions.get(ticker, {}).get("market_cap_eur", 2e9)
        cur_value   = cur_shares * price
        cur_pct     = cur_value / nav
        tgt_pct     = target_weights.get(ticker, 0.0)
        drift       = cur_pct - tgt_pct

        if abs(drift) < drift_threshold:
            orders.append(RebalanceOrder(
                ticker, "hold", 0, price, 0.0, cur_pct, tgt_pct, drift, 0.0,
                f"Drift {drift:+.1%} < seuil {drift_threshold:.0%}",
            ))
            continue

        target_value  = tgt_pct * nav
        target_shares = int(target_value / price)
        diff_shares   = target_shares - cur_shares

        if diff_shares > 0:
            notional = diff_shares * price
            costs    = total_trade_cost(
                notional, broker,
                asset_type="stock_us" if currency == "USD" else "stock_eu",
                currency=currency, market_cap_eur=market_cap, side="buy",
            )
            orders.append(RebalanceOrder(
                ticker, "buy", diff_shares, price, notional,
                cur_pct, tgt_pct, drift, costs["total"],
                f"Sous-pondéré de {-drift:.1%} — acheter {diff_shares} parts",
            ))
        elif diff_shares < 0:
            shares_to_sell = abs(diff_shares)
            notional = shares_to_sell * price
            costs = total_trade_cost(
                notional, broker,
                asset_type="stock_us" if currency == "USD" else "stock_eu",
                currency=currency, market_cap_eur=market_cap, side="sell",
            )
            orders.append(RebalanceOrder(
                ticker, "sell", shares_to_sell, price, notional,
                cur_pct, tgt_pct, drift, costs["total"],
                f"Sur-pondéré de {drift:.1%} — vendre {shares_to_sell} parts",
            ))

    return [asdict(o) for o in orders]
