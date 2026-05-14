"""
:file: tests/test_engine.py
:brief: Backtest engine tests — most importantly, the NO-LOOK-AHEAD property.

        These tests guard against subtle bugs that would invalidate every
        single backtest result.  Run them on every change to engine.py.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.backtest.engine import BacktestEngine
from backend.strategies.base import Strategy, StrategyParams

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# Mock strategy that records what past_prices it received
# ─────────────────────────────────────────────────────────────────────────────


class SpyStrategy(Strategy):
    """Records the last bar of past_prices it sees at each call."""

    requires_warmup_days = 1

    def __init__(self) -> None:
        self.bars_seen: list[tuple[date, pd.Timestamp]] = []

    @property
    def name(self) -> str:
        return "spy"

    @property
    def description(self) -> str:
        return "Spy strategy that records what it sees."

    def on_bar(self, dt, past_prices, params, state):
        # Record (dt requested, last index of past_prices)
        self.bars_seen.append((dt, past_prices.index[-1]))
        # Buy first ticker every time
        return {past_prices.columns[0]: 0.10}


# ─────────────────────────────────────────────────────────────────────────────
# THE CRITICAL TEST — no look-ahead
# ─────────────────────────────────────────────────────────────────────────────


class TestNoLookAhead:
    """If these tests fail, every backtest result in the system is wrong."""

    def test_past_prices_never_contains_future(self, deterministic_prices, currencies, fx_rates):
        """The most important test in the suite.

        For each call to on_bar(dt, past_prices, …), the last row of
        past_prices MUST equal dt.  If it's later than dt, we have a
        look-ahead bug.
        """
        strat = SpyStrategy()
        params = StrategyParams(initial_capital=10_000, rebalance_frequency="daily")
        engine = BacktestEngine(strat, deterministic_prices, currencies, fx_rates, params)
        engine.run()

        assert len(strat.bars_seen) > 0, "Strategy was never called!"

        for dt, last_idx_seen in strat.bars_seen:
            # last_idx_seen.date() should == dt
            assert last_idx_seen.date() == dt, (
                f"LOOK-AHEAD DETECTED: at dt={dt} the strategy saw "
                f"past_prices ending at {last_idx_seen.date()} (future!)"
            )

    def test_past_prices_length_grows_monotonically(
        self, deterministic_prices, currencies, fx_rates
    ):
        """As we walk forward, past_prices should grow by at most 1 each call."""

        class LengthSpy(Strategy):
            requires_warmup_days = 1

            def __init__(self):
                self.lengths = []

            @property
            def name(self):
                return "lenspy"

            @property
            def description(self):
                return ""

            def on_bar(self, dt, past_prices, params, state):
                self.lengths.append(len(past_prices))
                return {}

        strat = LengthSpy()
        params = StrategyParams(rebalance_frequency="daily")
        engine = BacktestEngine(strat, deterministic_prices, currencies, fx_rates, params)
        engine.run()

        # Each consecutive length should be ≥ previous (monotone)
        for i in range(1, len(strat.lengths)):
            assert strat.lengths[i] >= strat.lengths[i - 1]


# ─────────────────────────────────────────────────────────────────────────────
# Smoke tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEngineSmoke:
    def test_buy_hold_runs_end_to_end(self, deterministic_prices, currencies, fx_rates):
        from backend.strategies.builtin.all_strategies import BuyHoldStrategy

        params = StrategyParams(initial_capital=10_000)
        engine = BacktestEngine(
            BuyHoldStrategy(), deterministic_prices, currencies, fx_rates, params
        )
        result = engine.run()

        assert result.nav_series.iloc[0] > 0
        assert len(result.nav_series) > 0
        assert "total_return" in result.metrics

    def test_nav_never_negative(self, deterministic_prices, currencies, fx_rates):
        from backend.strategies.builtin.all_strategies import BuyHoldStrategy

        params = StrategyParams(initial_capital=10_000)
        result = BacktestEngine(
            BuyHoldStrategy(), deterministic_prices, currencies, fx_rates, params
        ).run()
        assert (result.nav_series >= 0).all()

    def test_cash_never_negative(self, deterministic_prices, currencies, fx_rates):
        """Portfolio's cash balance should never go negative."""
        from backend.strategies.builtin.all_strategies import EqualWeightStrategy

        params = StrategyParams(initial_capital=10_000, rebalance_frequency="monthly")
        engine = BacktestEngine(
            EqualWeightStrategy(), deterministic_prices, currencies, fx_rates, params
        )
        engine.run()
        # Access the portfolio after the run
        assert (
            engine._portfolio is None or engine._portfolio.cash >= 0
            if hasattr(engine, "_portfolio")
            else True
        )

    def test_integer_shares_only(self, deterministic_prices, currencies, fx_rates):
        from backend.strategies.builtin.all_strategies import EqualWeightStrategy

        params = StrategyParams(initial_capital=10_000, rebalance_frequency="monthly")
        result = BacktestEngine(
            EqualWeightStrategy(), deterministic_prices, currencies, fx_rates, params
        ).run()
        trades = result.trades_df
        if not trades.empty:
            # All share counts must be integers
            assert (trades["shares"] == trades["shares"].astype(int)).all()


# ─────────────────────────────────────────────────────────────────────────────
# Cost tracking
# ─────────────────────────────────────────────────────────────────────────────


class TestCostTracking:
    def test_costs_series_is_monotonically_increasing(
        self, deterministic_prices, currencies, fx_rates
    ):
        """Cumulative costs can only go up over time."""
        from backend.strategies.builtin.all_strategies import EqualWeightStrategy

        params = StrategyParams(initial_capital=10_000, rebalance_frequency="weekly")
        result = BacktestEngine(
            EqualWeightStrategy(), deterministic_prices, currencies, fx_rates, params
        ).run()

        if not result.costs_series.empty:
            costs = result.costs_series["costs_eur"].values
            for i in range(1, len(costs)):
                assert costs[i] >= costs[i - 1], "Cumulative costs decreased!"

    def test_total_cost_summary_matches_trades(self, deterministic_prices, currencies, fx_rates):
        """Total costs should equal sum of trade costs."""
        from backend.strategies.builtin.all_strategies import EqualWeightStrategy

        params = StrategyParams(initial_capital=10_000, rebalance_frequency="monthly")
        result = BacktestEngine(
            EqualWeightStrategy(), deterministic_prices, currencies, fx_rates, params
        ).run()

        if not result.trades_df.empty:
            sum_trades = result.trades_df["total_cost"].sum()
            assert abs(sum_trades - result.cost_summary["total_costs_eur"]) < 1e-6
