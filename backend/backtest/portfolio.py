"""
:file: api/backtest/portfolio.py
:brief: Portfolio state with PER-DATE cost tracking.

        Maintains:
        * Integer share positions (whole units, no fractional)
        * Cash balance (never negative)
        * Time series of (date, NAV, cumulative_costs, cumulative_taxes)
        * Trade ledger
        * Correlation matrix utility

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.backtest.costs import capital_gains_tax, total_trade_cost
from backend.config import DEFAULT_INITIAL_CAPITAL

log = logging.getLogger(__name__)


@dataclass
class Position:
    ticker: str
    shares: int = 0
    avg_cost_eur: float = 0.0
    currency: str = "USD"

    @property
    def book_value(self) -> float:
        return self.shares * self.avg_cost_eur

    def market_value(self, price_eur: float) -> float:
        return self.shares * price_eur

    def unrealised_pnl(self, price_eur: float) -> float:
        return self.market_value(price_eur) - self.book_value


@dataclass
class Trade:
    dt: date
    ticker: str
    side: str
    shares: int
    price_eur: float
    notional_eur: float
    costs: dict
    tax_eur: float = 0.0
    pnl_eur: float = 0.0


class Portfolio:
    """Mutable portfolio updated date-by-date by the engine."""

    def __init__(
        self,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        broker: str = "default",
        account_type: str = "CTO",
    ) -> None:
        self.cash: float = initial_capital
        self.initial_cap: float = initial_capital
        self.broker: str = broker
        self.account_type: str = account_type
        self._positions: dict[str, Position] = {}
        self._trades: list[Trade] = []
        # time series: list of (date, nav, cum_costs, cum_taxes, cash, invested)
        self._snapshots: list[tuple[date, float, float, float, float, float]] = []
        self._total_costs: float = 0.0
        self._total_taxes: float = 0.0

    # ── Valuation ────────────────────────────────────────────────────────

    def market_value(self, prices_eur: dict[str, float]) -> float:
        equity = sum(
            p.market_value(prices_eur.get(t, p.avg_cost_eur))
            for t, p in self._positions.items()
            if p.shares > 0
        )
        return self.cash + equity

    def invested_value(self, prices_eur: dict[str, float]) -> float:
        return sum(
            p.market_value(prices_eur.get(t, p.avg_cost_eur))
            for t, p in self._positions.items()
            if p.shares > 0
        )

    # ── Execution ────────────────────────────────────────────────────────

    def buy(
        self,
        dt: date,
        ticker: str,
        shares: int,
        price_eur: float,
        currency: str = "USD",
        market_cap_eur: float = 2e9,
        cap_size: str = "mid_cap",
        country: str = "US",
    ) -> Trade | None:
        if shares <= 0 or price_eur <= 0:
            return None
        asset_type = (
            "etf" if ticker.endswith(".ETF") else ("stock_eu" if currency == "EUR" else "stock_us")
        )

        notional = shares * price_eur
        costs = total_trade_cost(
            notional, self.broker, asset_type, cap_size, currency, market_cap_eur, "buy", country
        )
        if notional + costs["total"] > self.cash:
            # Downsize to fit
            est_unit_cost = price_eur * (1 + costs["cost_pct"] / 100)
            shares = int((self.cash * 0.995) // est_unit_cost)
            if shares <= 0:
                return None
            notional = shares * price_eur
            costs = total_trade_cost(
                notional, self.broker, asset_type, cap_size, currency, market_cap_eur, "buy", country
            )
            if notional + costs["total"] > self.cash:
                return None

        self.cash -= notional + costs["total"]
        self._total_costs += costs["total"]

        pos = self._positions.setdefault(ticker, Position(ticker, 0, 0.0, currency))
        old_val = pos.shares * pos.avg_cost_eur
        pos.shares += shares
        pos.avg_cost_eur = (old_val + notional) / pos.shares
        pos.currency = currency

        trade = Trade(dt, ticker, "buy", shares, price_eur, notional, costs)
        self._trades.append(trade)
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
        country: str = "US",
        pea_years: int = 0,
    ) -> Trade | None:
        pos = self._positions.get(ticker)
        if pos is None or pos.shares == 0:
            return None
        shares = min(shares, pos.shares)
        if shares <= 0 or price_eur <= 0:
            return None

        asset_type = (
            "etf" if ticker.endswith(".ETF") else ("stock_eu" if currency == "EUR" else "stock_us")
        )
        notional = shares * price_eur
        costs = total_trade_cost(
            notional, self.broker, asset_type, cap_size, currency, market_cap_eur, "sell", country
        )

        cost_basis = pos.avg_cost_eur * shares
        gain = notional - cost_basis
        tax = capital_gains_tax(gain, self.account_type, pea_years) if gain > 0 else 0.0

        self.cash += notional - costs["total"] - tax
        self._total_costs += costs["total"]
        self._total_taxes += tax

        pos.shares -= shares
        if pos.shares == 0:
            pos.avg_cost_eur = 0.0

        trade = Trade(dt, ticker, "sell", shares, price_eur, notional, costs, tax, gain)
        self._trades.append(trade)
        return trade

    # ── Snapshots & series ───────────────────────────────────────────────

    def snapshot(self, dt: date, prices_eur: dict[str, float]) -> None:
        invested = self.invested_value(prices_eur)
        nav = self.cash + invested
        self._snapshots.append((dt, nav, self._total_costs, self._total_taxes, self.cash, invested))

    def nav_series(self) -> pd.Series:
        if not self._snapshots:
            return pd.Series(dtype=float)
        idx, nav, *_ = zip(*self._snapshots, strict=False)
        return pd.Series(nav, index=pd.DatetimeIndex(idx), name="NAV")

    def costs_series(self) -> pd.DataFrame:
        """Cumulative costs + taxes time series."""
        if not self._snapshots:
            return pd.DataFrame()
        idx, _nav, costs, taxes, _cash, _inv = zip(*self._snapshots, strict=False)
        return pd.DataFrame(
            {"costs_eur": costs, "taxes_eur": taxes},
            index=pd.DatetimeIndex(idx),
        )

    def cash_invested_series(self) -> pd.DataFrame:
        if not self._snapshots:
            return pd.DataFrame()
        idx, _nav, _c, _t, cash, inv = zip(*self._snapshots, strict=False)
        return pd.DataFrame(
            {"cash_eur": cash, "invested_eur": inv},
            index=pd.DatetimeIndex(idx),
        )

    # ── Summary ──────────────────────────────────────────────────────────

    def summary(self, prices_eur: dict[str, float]) -> dict:
        nav = self.market_value(prices_eur)
        return {
            "nav_eur": nav,
            "cash_eur": self.cash,
            "invested_eur": nav - self.cash,
            "total_return": nav / self.initial_cap - 1.0,
            "total_costs_eur": self._total_costs,
            "total_taxes_eur": self._total_taxes,
            "n_trades": len(self._trades),
            "positions": {
                t: {
                    "shares": p.shares,
                    "price_eur": prices_eur.get(t, 0.0),
                    "value_eur": p.market_value(prices_eur.get(t, 0.0)),
                    "unrealised": p.unrealised_pnl(prices_eur.get(t, 0.0)),
                    "avg_cost": p.avg_cost_eur,
                    "weight": p.market_value(prices_eur.get(t, 0.0)) / nav if nav > 0 else 0.0,
                }
                for t, p in self._positions.items()
                if p.shares > 0
            },
        }

    def trades_df(self) -> pd.DataFrame:
        if not self._trades:
            return pd.DataFrame()
        rows = []
        for t in self._trades:
            rows.append(
                {
                    "date": t.dt,
                    "ticker": t.ticker,
                    "side": t.side,
                    "shares": t.shares,
                    "price_eur": t.price_eur,
                    "notional_eur": t.notional_eur,
                    "commission": t.costs.get("commission", 0),
                    "slippage": t.costs.get("slippage", 0),
                    "fx_spread": t.costs.get("fx_spread", 0),
                    "ttf": t.costs.get("ttf", 0),
                    "total_cost": t.costs.get("total", 0),
                    "tax": t.tax_eur,
                    "pnl": t.pnl_eur,
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
        return prices.pct_change().corr()
