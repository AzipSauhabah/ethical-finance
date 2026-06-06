"""
:file: tests/test_regression.py
:brief: Non-regression tests for bugs fixed in production.
"""

from __future__ import annotations

from datetime import date
import pytest

pytestmark = pytest.mark.unit


class TestMarketValueNoAllowFractional:
    def test_market_value_does_not_accept_allow_fractional(self):
        from backend.backtest.portfolio import Portfolio
        pf = Portfolio(initial_capital=10_000, broker="degiro", account_type="CTO")
        with pytest.raises(TypeError):
            pf.market_value({"AAPL": 100.0}, allow_fractional=True)  # NOSONAR intentional invalid arg test

    def test_market_value_accepts_only_prices_eur(self):
        from backend.backtest.portfolio import Portfolio
        pf = Portfolio(initial_capital=10_000, broker="degiro", account_type="CTO")
        result = pf.market_value({"AAPL": 100.0})
        assert isinstance(result, (int, float))


class TestPDFUnboundLocalError:
    def test_generate_pdf_no_unbound_local_error(self):
        pytest.importorskip("reportlab", reason="reportlab not installed")
        from backend.report.pdf import generate_pdf
        tearsheet = {
            "meta": {"generated_at": "2024-01-01 00:00:00", "strategy": "buy_hold", "period": "1y", "tickers": ["AAPL"],
                     "start": "2023-01-01", "end": "2024-01-01",
                     "broker": "degiro", "account_type": "CTO", "benchmark": "^GSPC"},
            "metrics": {"total_return": 0.1, "cagr": 0.1, "annualised_vol": 0.15,
                        "sharpe": 0.8, "sortino": 1.0, "max_drawdown": -0.05,
                        "calmar": 1.5, "var_95": -0.02, "cvar_95": -0.03,
                        "hit_rate": 0.55, "profit_factor": 1.2, "beta": 0.9,
                        "alpha": 0.01, "skewness": 0.1, "kurtosis": 3.0, "omega": 1.1},
            "significance": {"sharpe_tstat": 2.0, "sharpe_pvalue": 0.04, "significant": True},
            "stress_tests": [],
            "cost_summary": {"total_costs": 100.0, "commission": 70.0, "slippage": 20.0, "taxes": 10.0},
            "cost_breakdown": {},
            "nav_chart": [{"date": "2023-01-01", "nav": 10000}, {"date": "2024-01-01", "nav": 11000}],
            "benchmark_chart": [{"date": "2023-01-01", "nav": 10000}, {"date": "2024-01-01", "nav": 10500}],
            "drawdown_chart": [{"date": "2023-01-01", "drawdown": 0.0}],
            "cost_chart": [],
            "allocation_chart": [{"ticker": "AAPL", "weight": 1.0}],
            "positions": {},
        }
        try:
            generate_pdf(tearsheet)
        except UnboundLocalError as e:
            pytest.fail(f"UnboundLocalError regression: {e}")


class TestStrategyFallback:
    def test_known_strategy_instantiates(self):
        from backend.strategies.registry import strategy_registry
        strategy_registry.auto_discover()
        s = strategy_registry.get("epr5")
        assert s is not None

    def test_unknown_strategy_returns_none(self):
        from backend.strategies.registry import strategy_registry
        strategy_registry.auto_discover()
        result = strategy_registry.get("nonexistent_xyz")
        assert result is None


class TestZipCompatibility:
    def test_nav_series_no_strict_kwarg_error(self):
        from backend.backtest.portfolio import Portfolio
        pf = Portfolio(initial_capital=10_000, broker="degiro", account_type="CTO")
        pf.snapshot(date(2024, 1, 2), {})
        pf.snapshot(date(2024, 1, 3), {})
        try:
            nav = pf.nav_series()
            assert len(nav) == 2
        except TypeError as e:
            pytest.fail(f"zip strict= regression: {e}")

    def test_costs_series_no_strict_kwarg_error(self):
        from backend.backtest.portfolio import Portfolio
        pf = Portfolio(initial_capital=10_000, broker="degiro", account_type="CTO")
        pf.snapshot(date(2024, 1, 2), {})
        try:
            costs = pf.costs_series()
            assert len(costs) == 1
        except TypeError as e:
            pytest.fail(f"zip strict= regression: {e}")
