"""
:file: api/backtest/engine.py
:brief: Event-driven backtest engine.

        Simulates the market date-by-date (path-dependent), applying:
        * Strategy signals
        * Integer share sizing
        * Stop-loss checks
        * Monthly contributions
        * FX conversion (USD → EUR)
        * Dividend reinvestment (via yfinance adjusted prices)

        Uses the backtesting.py framework conventions where applicable,
        but is implemented from scratch for full cost/tax transparency.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterator

import numpy as np
import pandas as pd

from api.backtest.portfolio import Portfolio
from api.config import DEFAULT_INITIAL_CAPITAL, RISK_FREE_RATE, BENCHMARKS
from api.quant.metrics import all_metrics, drawdown_series
from api.strategies.base import Strategy, StrategyParams

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    strategy_name:   str
    nav_series:      pd.Series
    returns_series:  pd.Series
    drawdown_series: pd.Series
    metrics:         dict
    trades_df:       pd.DataFrame
    cost_summary:    dict
    positions_final: dict


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (generators for lazy evaluation)
# ─────────────────────────────────────────────────────────────────────────────

def _trading_dates(prices: pd.DataFrame) -> Iterator[date]:
    """Yield each date in the price index — lazy generator."""
    for ts in prices.index:
        yield ts.date() if hasattr(ts, "date") else ts


def _fx_convert(
    prices_native: dict[str, float],
    currencies: dict[str, str],
    fx_rates: dict[str, float],
) -> dict[str, float]:
    """Convert per-ticker prices to EUR using cached FX rates."""
    result = {}
    for ticker, price in prices_native.items():
        ccy = currencies.get(ticker, "USD")
        if ccy == "EUR":
            result[ticker] = price
        else:
            rate = fx_rates.get(f"{ccy}EUR", 1.0 / fx_rates.get(f"EUR{ccy}", 1.0) or 1.0)
            result[ticker] = price * rate
    return result


def _target_shares(
    target_weight: float,
    nav_eur: float,
    price_eur: float,
    max_pos_pct: float = 0.25,
) -> int:
    """Compute integer share count for a target portfolio weight."""
    if price_eur <= 0:
        return 0
    capped_w = min(target_weight, max_pos_pct)
    return int((nav_eur * capped_w) // price_eur)


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

class BacktestEngine:
    """Event-driven backtest engine.

    :param strategy:  Strategy instance
    :param prices:    DataFrame[date, ticker] — adjusted closes (native currency)
    :param currencies: dict[ticker, currency_code]
    :param fx_rates:  dict['{FROM}{TO}', rate] — e.g. {'USDEUR': 0.92}
    :param params:    StrategyParams
    """

    def __init__(
        self,
        strategy:   Strategy,
        prices:     pd.DataFrame,
        currencies: dict[str, str] | None = None,
        fx_rates:   dict[str, float] | None = None,
        params:     StrategyParams | None = None,
    ) -> None:
        self.strategy   = strategy
        self.prices     = prices
        self.currencies = currencies or {t: "USD" for t in prices.columns}
        self.fx_rates   = fx_rates   or {"USDEUR": 0.92, "EURUSD": 1.087}
        self.params     = params     or StrategyParams()
        self._portfolio: Portfolio | None = None

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self) -> BacktestResult:
        """Execute the backtest and return a :class:`BacktestResult`."""
        params   = self.params
        prices   = self.prices
        strategy = self.strategy

        portfolio = Portfolio(
            initial_capital = params.initial_capital,
            broker          = params.broker,
            account_type    = params.account_type,
        )
        self._portfolio = portfolio

        # Pre-compute all signals (vectorised for non-path-dependent strats)
        log.info("Generating signals for strategy '%s' …", strategy.name)
        signals = strategy.generate_signals(prices, params)

        # Rebalance schedule
        rebalance_dates = self._rebalance_dates(prices.index, params.rebalance_frequency)

        n_months = 0

        for dt in _trading_dates(prices):
            ts = pd.Timestamp(dt)
            if ts not in prices.index:
                continue

            # Current prices in native currency
            row_native = prices.loc[ts].to_dict()
            # Convert to EUR
            prices_eur = _fx_convert(row_native, self.currencies, self.fx_rates)

            # Monthly contribution
            if ts.day <= 5 and ts.month != (n_months % 12 + 1):
                portfolio.cash += params.monthly_contribution
                n_months = ts.month

            # Stop-loss check
            if params.stop_loss_pct is not None:
                self._apply_stop_loss(portfolio, dt, prices_eur, params.stop_loss_pct)

            # Rebalance if needed
            if ts in rebalance_dates:
                self._rebalance(portfolio, dt, ts, signals, prices_eur, params)

            # Record NAV
            portfolio.snapshot(dt, prices_eur)

        nav   = portfolio.nav_series()
        rets  = nav.pct_change().dropna()
        dd    = pd.Series(drawdown_series(rets.values), index=rets.index)
        last_prices = {t: prices[t].iloc[-1] for t in prices.columns}
        last_eur    = _fx_convert(last_prices, self.currencies, self.fx_rates)
        metrics = all_metrics(rets.values)

        return BacktestResult(
            strategy_name   = strategy.name,
            nav_series      = nav,
            returns_series  = rets,
            drawdown_series = dd,
            metrics         = metrics,
            trades_df       = portfolio.trades_df(),
            cost_summary    = {
                "total_costs_eur": portfolio._total_costs,
                "total_taxes_eur": portfolio._total_taxes,
                "cost_pct_nav":    portfolio._total_costs / params.initial_capital,
            },
            positions_final = portfolio.summary(last_eur),
        )

    # ── Rebalancing logic ─────────────────────────────────────────────────

    def _rebalance(
        self,
        portfolio: Portfolio,
        dt: date,
        ts: pd.Timestamp,
        signals: pd.DataFrame,
        prices_eur: dict[str, float],
        params: StrategyParams,
    ) -> None:
        """Translate signals into buy/sell orders."""
        row = signals.loc[ts] if ts in signals.index else None
        if row is None:
            return

        nav = portfolio.nav(prices_eur)
        if nav <= 0:
            return

        n_long = max(1, int((row > 0).sum()))
        weight = min(1.0 / n_long, params.max_position_pct)

        for ticker, sig in row.items():
            price_eur = prices_eur.get(ticker, 0.0)
            if price_eur <= 0:
                continue
            pos   = portfolio._positions.get(ticker)
            cur_s = pos.shares if pos else 0
            ccy   = self.currencies.get(ticker, "USD")

            if sig > 0:
                target_s = _target_shares(weight, nav, price_eur, params.max_position_pct)
                diff     = target_s - cur_s
                if diff > 0:
                    portfolio.buy(dt, ticker, diff, price_eur, ccy)
            elif sig <= 0 and cur_s > 0:
                portfolio.sell(dt, ticker, cur_s, price_eur, ccy)

    def _apply_stop_loss(
        self,
        portfolio: Portfolio,
        dt: date,
        prices_eur: dict[str, float],
        stop_pct: float,
    ) -> None:
        """Sell any position that has fallen more than *stop_pct* below entry."""
        for ticker, pos in list(portfolio._positions.items()):
            if pos.shares == 0 or pos.avg_cost_eur == 0:
                continue
            current = prices_eur.get(ticker, pos.avg_cost_eur)
            if current < pos.avg_cost_eur * (1 - stop_pct):
                log.debug("Stop-loss triggered for %s on %s", ticker, dt)
                portfolio.sell(dt, ticker, pos.shares, current,
                               self.currencies.get(ticker, "USD"))

    # ── Schedule helper ───────────────────────────────────────────────────

    @staticmethod
    def _rebalance_dates(idx: pd.DatetimeIndex, frequency: str) -> set:
        if frequency == "daily":
            return set(idx)
        if frequency == "weekly":
            return set(idx[idx.day_of_week == 4])   # Fridays
        if frequency == "monthly":
            return set(idx[idx.is_month_end])
        if frequency == "quarterly":
            return set(idx[idx.month.isin([3, 6, 9, 12]) & idx.is_month_end])
        return set(idx[idx.is_month_end])
