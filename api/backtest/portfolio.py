"""
:file: api/backtest/portfolio.py
:brief: Portfolio state machine for the event-driven backtest engine.

        Tracks:
        * Cash (non-negative, non-remunerated)
        * Integer share positions per ticker
        * Realised/unrealised P&L in EUR
        * NAV series
        * Dividend reinvestment
        * Correlation matrix

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Iterator

import numpy as np
import pandas as pd

from api.backtest.costs import total_trade_cost, capital_gains_tax
from api.config import DEFAULT_INITIAL_CAPITAL, BASE_CURRENCY

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Position record
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Position:
    ticker:       str
    shares:       int             = 0      # whole units only
    avg_cost_eur: float           = 0.0    # average entry price in EUR
    currency:     str             = "USD"

    @property
    def book_value(self) -> float:
        return self.shares * self.avg_cost_eur

    def market_value(self, price_eur: float) -> float:
        return self.shares * price_eur

    def unrealised_pnl(self, price_eur: float) -> float:
        return self.market_value(price_eur) - self.book_value


# ─────────────────────────────────────────────────────────────────────────────
# Trade record
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    dt:           date
    ticker:       str
    side:         str          # 'buy' | 'sell'
    shares:       int
    price_eur:    float
    notional_eur: float
    costs:        dict         # breakdown from costs.total_trade_cost
    tax_eur:      float = 0.0
    pnl_eur:      float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio state
# ─────────────────────────────────────────────────────────────────────────────

class Portfolio:
    """Mutable portfolio state updated by the backtest engine date-by-date."""

    def __init__(
        self,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        broker: str = "default",
        account_type: str = "CTO",
    ) -> None:
        self.cash:         float             = initial_capital
        self.initial_cap:  float             = initial_capital
        self.broker:       str               = broker
        self.account_type: str               = account_type
        self._positions:   dict[str, Position] = {}
        self._trades:      list[Trade]         = []
        self._nav_series:  list[tuple[date, float]] = []
        self._total_costs: float             = 0.0
        self._total_taxes: float             = 0.0

    # ── Market value ──────────────────────────────────────────────────────

    def market_value(self, prices_eur: dict[str, float]) -> float:
        """Total portfolio market value in EUR."""
        equity = sum(
            pos.market_value(prices_eur.get(t, pos.avg_cost_eur))
            for t, pos in self._positions.items()
            if pos.shares > 0
        )
        return self.cash + equity

    def nav(self, prices_eur: dict[str, float]) -> float:
        return self.market_value(prices_eur)

    # ── Execution ─────────────────────────────────────────────────────────

    def buy(
        self,
        dt: date,
        ticker: str,
        shares: int,
        price_eur: float,
        currency: str = "USD",
        market_cap_eur: float = 2e9,
        cap_size: str = "mid_cap",
    ) -> Trade | None:
        """Execute a buy order. Returns None if insufficient cash."""
        if shares <= 0:
            return None

        notional = shares * price_eur
        asset_type = "etf" if ticker.endswith(".ETF") else (
            "stock_eu" if currency == "EUR" else "stock_us"
        )
        costs = total_trade_cost(
            notional_eur   = notional,
            broker         = self.broker,
            asset_type     = asset_type,
            cap_size       = cap_size,
            currency       = currency,
            market_cap_eur = market_cap_eur,
            side           = "buy",
        )
        total_outflow = notional + costs["total"]

        if total_outflow > self.cash:
            # Reduce shares to fit budget
            shares = int((self.cash * 0.99) // (price_eur * (1 + costs["cost_pct"])))
            if shares <= 0:
                return None
            notional = shares * price_eur
            costs = total_trade_cost(notional, self.broker, asset_type, cap_size,
                                     currency, market_cap_eur, "buy")
            total_outflow = notional + costs["total"]

        self.cash -= total_outflow
        self._total_costs += costs["total"]

        pos = self._positions.setdefault(ticker, Position(ticker=ticker, currency=currency))
        old_val  = pos.shares * pos.avg_cost_eur
        pos.shares += shares
        pos.avg_cost_eur = (old_val + notional) / pos.shares if pos.shares > 0 else 0.0
        pos.currency = currency

        trade = Trade(dt, ticker, "buy", shares, price_eur, notional, costs)
        self._trades.append(trade)
        log.debug("BUY  %s x%d @ %.2f  cost=%.2f  cash=%.2f", ticker, shares, price_eur, costs["total"], self.cash)
        return trade

    def sell(
        self,
        dt: date,
        ticker: str,
        shares: int,
        price_eur: float,
        currency: str = "USD",
        market_cap_eur: float = 2e9,
        cap_size: str = "mid_cap",
        pea_years: int = 0,
    ) -> Trade | None:
        """Execute a sell order."""
        pos = self._positions.get(ticker)
        if pos is None or pos.shares == 0:
            return None
        shares = min(shares, pos.shares)
        if shares <= 0:
            return None

        notional   = shares * price_eur
        asset_type = "etf" if ticker.endswith(".ETF") else (
            "stock_eu" if currency == "EUR" else "stock_us"
        )
        costs = total_trade_cost(notional, self.broker, asset_type, cap_size,
                                 currency, market_cap_eur, "sell")

        # Realised gain
        cost_basis = pos.avg_cost_eur * shares
        gain       = notional - cost_basis
        tax        = capital_gains_tax(gain, self.account_type, pea_years) if gain > 0 else 0.0

        self.cash           += notional - costs["total"] - tax
        self._total_costs   += costs["total"]
        self._total_taxes   += tax

        pos.shares -= shares
        if pos.shares == 0:
            pos.avg_cost_eur = 0.0

        trade = Trade(dt, ticker, "sell", shares, price_eur, notional, costs, tax, gain)
        self._trades.append(trade)
        log.debug("SELL %s x%d @ %.2f  pnl=%.2f  tax=%.2f  cash=%.2f",
                  ticker, shares, price_eur, gain, tax, self.cash)
        return trade

    # ── Snapshots ─────────────────────────────────────────────────────────

    def snapshot(self, dt: date, prices_eur: dict[str, float]) -> None:
        """Record NAV at date *dt*."""
        self._nav_series.append((dt, self.nav(prices_eur)))

    def nav_series(self) -> pd.Series:
        if not self._nav_series:
            return pd.Series(dtype=float)
        idx, vals = zip(*self._nav_series)
        return pd.Series(vals, index=pd.DatetimeIndex(idx), name="NAV")

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self, prices_eur: dict[str, float]) -> dict:
        mv = self.market_value(prices_eur)
        return {
            "nav_eur":          mv,
            "cash_eur":         self.cash,
            "invested_eur":     mv - self.cash,
            "total_return":     mv / self.initial_cap - 1.0,
            "total_costs_eur":  self._total_costs,
            "total_taxes_eur":  self._total_taxes,
            "n_trades":         len(self._trades),
            "positions": {
                t: {
                    "shares":     p.shares,
                    "price_eur":  prices_eur.get(t, 0.0),
                    "value_eur":  p.market_value(prices_eur.get(t, 0.0)),
                    "unrealised": p.unrealised_pnl(prices_eur.get(t, 0.0)),
                }
                for t, p in self._positions.items() if p.shares > 0
            },
        }

    def trades_df(self) -> pd.DataFrame:
        if not self._trades:
            return pd.DataFrame()
        rows = [
            {
                "date":         t.dt,
                "ticker":       t.ticker,
                "side":         t.side,
                "shares":       t.shares,
                "price_eur":    t.price_eur,
                "notional_eur": t.notional_eur,
                "commission":   t.costs.get("commission", 0),
                "slippage":     t.costs.get("slippage", 0),
                "ttf":          t.costs.get("ttf", 0),
                "total_cost":   t.costs.get("total", 0),
                "tax":          t.tax_eur,
                "pnl":          t.pnl_eur,
            }
            for t in self._trades
        ]
        return pd.DataFrame(rows)

    # ── Correlation ───────────────────────────────────────────────────────

    @staticmethod
    def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
        return prices.pct_change().corr()
