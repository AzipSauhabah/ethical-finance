"""
:file: tests/test_portfolio.py
:brief: Portfolio unit tests — position management, NAV, costs, cash invariants.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.backtest.portfolio import Portfolio, Position

pytestmark = pytest.mark.unit


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_portfolio(capital: float = 10_000.0) -> Portfolio:
    return Portfolio(initial_capital=capital, broker="degiro", account_type="CTO")


# ─── Position ────────────────────────────────────────────────────────────────

class TestPosition:
    def test_book_value_equals_shares_times_cost(self):
        p = Position(ticker="AAPL", shares=10, avg_cost_eur=50.0)
        assert p.book_value == pytest.approx(500.0)

    def test_market_value_uses_current_price(self):
        p = Position(ticker="AAPL", shares=10, avg_cost_eur=50.0)
        assert p.market_value(price_eur=60.0) == pytest.approx(600.0)

    def test_unrealised_pnl_positive_on_gain(self):
        p = Position(ticker="AAPL", shares=10, avg_cost_eur=50.0)
        assert p.unrealised_pnl(price_eur=60.0) == pytest.approx(100.0)

    def test_unrealised_pnl_negative_on_loss(self):
        p = Position(ticker="AAPL", shares=10, avg_cost_eur=50.0)
        assert p.unrealised_pnl(price_eur=40.0) == pytest.approx(-100.0)

    def test_zero_shares_zero_market_value(self):
        p = Position(ticker="AAPL", shares=0, avg_cost_eur=50.0)
        assert p.market_value(price_eur=100.0) == pytest.approx(0.0)


# ─── Portfolio — initialisation ──────────────────────────────────────────────

class TestPortfolioInit:
    def test_initial_cash_correct(self):
        pf = make_portfolio(10_000)
        assert pf.cash == pytest.approx(10_000.0)

    def test_initial_market_value_equals_cash(self):
        pf = make_portfolio(10_000)
        assert pf.market_value({}) == pytest.approx(10_000.0)

    def test_no_positions_initially(self):
        pf = make_portfolio()
        assert len(pf._positions) == 0


# ─── Portfolio — buy ─────────────────────────────────────────────────────────

class TestPortfolioBuy:
    def test_cash_decreases_after_buy(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=10, price_eur=100.0, country="US")
        assert pf.cash < 10_000.0

    def test_position_created_after_buy(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=10, price_eur=100.0, country="US")
        assert "AAPL" in pf._positions
        assert pf._positions["AAPL"].shares == 10

    def test_market_value_increases_after_buy(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=10, price_eur=100.0, country="US")
        mv = pf.market_value({"AAPL": 100.0})
        assert mv == pytest.approx(10_000.0, rel=0.01)

    def test_buy_capped_to_available_cash(self):
        pf = make_portfolio(1_000)
        result = pf.buy(date(2024, 1, 2), "AAPL", shares=100, price_eur=100.0, country="US")
        # buy() buys as many shares as cash allows, never exceeds cash
        assert pf.cash >= 0

    def test_avg_cost_updated_on_second_buy(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=5, price_eur=100.0, country="US")
        pf.buy(date(2024, 1, 3), "AAPL", shares=5, price_eur=200.0, country="US")
        assert pf._positions["AAPL"].avg_cost_eur == pytest.approx(150.0, rel=0.01)


# ─── Portfolio — sell ────────────────────────────────────────────────────────

class TestPortfolioSell:
    def test_cash_increases_after_sell(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=10, price_eur=100.0, country="US")
        cash_before = pf.cash
        pf.sell(date(2024, 1, 3), "AAPL", shares=5, price_eur=120.0, country="US")
        assert pf.cash > cash_before

    def test_shares_decrease_after_sell(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=10, price_eur=100.0, country="US")
        pf.sell(date(2024, 1, 3), "AAPL", shares=5, price_eur=120.0, country="US")
        assert pf._positions["AAPL"].shares == 5

    def test_sell_capped_to_held_shares(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=5, price_eur=100.0, country="US")
        # sell() sells at most what is held, cash must stay >= 0
        pf.sell(date(2024, 1, 3), "AAPL", shares=10, price_eur=100.0, country="US")
        assert pf.cash >= 0
        assert pf._positions.get("AAPL", None) is None or pf._positions["AAPL"].shares == 0


# ─── Portfolio — NAV series ───────────────────────────────────────────────────

class TestPortfolioNavSeries:
    def test_nav_series_empty_without_snapshots(self):
        pf = make_portfolio(10_000)
        # nav_series() returns empty series when no snapshots
        nav = pf.nav_series()
        assert len(nav) == 0

    def test_nav_series_length_matches_snapshots(self):
        pf = make_portfolio(10_000)
        for i in range(1, 4):
            pf.snapshot(date(2024, 1, i), {})
        nav = pf.nav_series()
        assert len(nav) == 3

    def test_nav_series_never_negative(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=10, price_eur=100.0, country="US")
        for i in range(2, 10):
            pf.snapshot(date(2024, 1, i), {"AAPL": max(1.0, 100.0 - i * 5)})
        nav = pf.nav_series()
        assert (nav >= 0).all()

    def test_nav_series_starts_near_initial_cash(self):
        pf = make_portfolio(10_000)
        pf.snapshot(date(2024, 1, 2), {})
        nav = pf.nav_series()
        assert nav.iloc[0] == pytest.approx(10_000.0, rel=0.01)


# ─── Portfolio — costs series ────────────────────────────────────────────────

class TestPortfolioCostsSeries:
    def test_costs_series_monotone_after_trades(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=5, price_eur=100.0, country="US")
        pf.snapshot(date(2024, 1, 2), {"AAPL": 100.0})
        pf.buy(date(2024, 1, 3), "MSFT", shares=3, price_eur=150.0, country="US")
        pf.snapshot(date(2024, 1, 3), {"AAPL": 100.0, "MSFT": 150.0})
        costs = pf.costs_series()
        total = costs['costs_eur']
        assert total.is_monotonic_increasing

    def test_costs_series_non_negative(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=5, price_eur=100.0, country="US")
        pf.snapshot(date(2024, 1, 2), {"AAPL": 100.0})
        costs = pf.costs_series()
        assert (costs['costs_eur'] >= 0).all()


# ─── Portfolio — summary ─────────────────────────────────────────────────────

class TestPortfolioSummary:
    def test_summary_contains_expected_keys(self):
        pf = make_portfolio(10_000)
        pf.buy(date(2024, 1, 2), "AAPL", shares=5, price_eur=100.0, country="US")
        summary = pf.summary({"AAPL": 110.0})
        for key in ("cash_eur", "invested_eur", "nav_eur", "n_trades"):
            assert key in summary

    def test_summary_total_nav_positive(self):
        pf = make_portfolio(10_000)
        summary = pf.summary({})
        assert summary["nav_eur"] > 0
