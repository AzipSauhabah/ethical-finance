"""
:file: tests/test_strategies.py
:brief: Sanity tests for built-in strategies.

        Each strategy must:
        * Return a dict[str, float] with weights summing to ≤ 1
        * Never raise on warmup data
        * Not look at the future (enforced by engine tests)
"""

from __future__ import annotations

import pytest
from backend.strategies.base import StrategyParams
from backend.strategies.registry import strategy_registry

pytestmark = pytest.mark.unit

# Make sure all built-ins are registered
strategy_registry.auto_discover()


# ─────────────────────────────────────────────────────────────────────────────
# Parametrised over EVERY registered strategy
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def all_strategy_names() -> list[str]:
    return [s["name"] for s in strategy_registry.list_all()]


class TestStrategyContract:
    @pytest.mark.parametrize("strat_name", [s["name"] for s in strategy_registry.list_all()])
    def test_on_bar_returns_dict(self, strat_name, deterministic_prices):
        strategy = strategy_registry.get_instance(strat_name)
        params = StrategyParams(initial_capital=10_000)
        state: dict = {}

        # Pass full history to ensure warmup is satisfied
        last_ts = deterministic_prices.index[-1]
        weights = strategy.on_bar(
            last_ts.date(),
            deterministic_prices,
            params,
            state,
        )

        assert isinstance(weights, dict), f"{strat_name}: expected dict, got {type(weights)}"

    @pytest.mark.parametrize("strat_name", [s["name"] for s in strategy_registry.list_all()])
    def test_weights_in_valid_range(self, strat_name, deterministic_prices):
        strategy = strategy_registry.get_instance(strat_name)
        params = StrategyParams(initial_capital=10_000)
        state: dict = {}

        last_ts = deterministic_prices.index[-1]
        weights = strategy.on_bar(last_ts.date(), deterministic_prices, params, state)

        for ticker, w in weights.items():
            assert 0.0 <= w <= 1.0, f"{strat_name}: weight for {ticker} is {w}, must be in [0, 1]"

    @pytest.mark.parametrize("strat_name", [s["name"] for s in strategy_registry.list_all()])
    def test_weights_sum_at_most_one(self, strat_name, deterministic_prices):
        strategy = strategy_registry.get_instance(strat_name)
        params = StrategyParams(initial_capital=10_000)
        state: dict = {}

        last_ts = deterministic_prices.index[-1]
        weights = strategy.on_bar(last_ts.date(), deterministic_prices, params, state)

        total = sum(weights.values())
        # Allow tiny floating point slack
        assert (
            total <= 1.0 + 1e-6
        ), f"{strat_name}: weights sum to {total}, must be ≤ 1.0 (cash is remainder)"

    @pytest.mark.parametrize("strat_name", [s["name"] for s in strategy_registry.list_all()])
    def test_handles_insufficient_warmup_gracefully(self, strat_name, deterministic_prices):
        """Called with too little history → should return empty dict, not raise."""
        strategy = strategy_registry.get_instance(strat_name)
        params = StrategyParams(initial_capital=10_000)
        state: dict = {}

        tiny = deterministic_prices.iloc[:2]  # only 2 days
        try:
            weights = strategy.on_bar(tiny.index[-1].date(), tiny, params, state)
            assert isinstance(weights, dict)
        except Exception as e:
            pytest.fail(f"{strat_name}: raised on tiny warmup: {e}")


class TestRegistryDiscovery:
    def test_all_builtin_strategies_discovered(self):
        names = [s["name"] for s in strategy_registry.list_all()]
        expected = [
            "buy_hold",
            "equal_weight",
            "momentum",
            "mean_reversion",
            "sma_crossover",
            "risk_parity",
            "min_variance",
            "dual_momentum",
            "adaptive_trend",
            "ml_ensemble",
            "epr5",
        ]
        for name in expected:
            assert name in names, f"Missing strategy: {name}"

    def test_strategy_metadata_complete(self):
        for s in strategy_registry.list_all():
            assert s["name"], "Empty name!"
            assert s["description"], f"Empty description for {s['name']}"
            assert s["benchmark"], f"Empty benchmark for {s['name']}"
