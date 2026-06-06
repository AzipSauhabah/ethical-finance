"""
tests/test_custom_strategy.py
Tests unitaires — backend.strategies.custom (build_custom_strategy)
"""
import pytest
import numpy as np
import pandas as pd

pytestmark = pytest.mark.unit


def _prices(tickers=("AAPL", "MSFT", "GOOGL"), n=300, seed=42):
    rng = np.random.default_rng(seed)
    data = {t: 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n))) for t in tickers}
    return pd.DataFrame(data, index=pd.date_range("2020-01-01", periods=n, freq="B"))


def _simple_definition(name="test_strat"):
    return {
        "name": name,
        "description": "Test strategy",
        "rules": [{"type": "always_long"}],
        "combination": "majority",
    }


class TestBuildCustomStrategy:
    def test_returns_strategy_instance(self):
        from backend.strategies.custom import build_custom_strategy
        from backend.strategies.base import Strategy
        s = build_custom_strategy(_simple_definition("strat_a"))
        assert isinstance(s, Strategy)

    def test_strategy_has_name(self):
        from backend.strategies.custom import build_custom_strategy
        s = build_custom_strategy(_simple_definition("strat_b"))
        assert "strat_b" in s.name

    def test_default_rules(self):
        from backend.strategies.custom import build_custom_strategy
        s = build_custom_strategy({"name": "strat_c"})
        assert s is not None

    def test_combination_all(self):
        from backend.strategies.custom import build_custom_strategy
        s = build_custom_strategy({
            "name": "strat_d",
            "rules": [{"type": "always_long"}],
            "combination": "all",
        })
        assert s is not None

    def test_combination_any(self):
        from backend.strategies.custom import build_custom_strategy
        s = build_custom_strategy({
            "name": "strat_e",
            "rules": [{"type": "always_long"}],
            "combination": "any",
        })
        assert s is not None

    def test_on_bar_returns_dict(self):
        from backend.strategies.custom import build_custom_strategy
        from backend.strategies.base import StrategyParams
        prices = _prices(n=200)
        s = build_custom_strategy(_simple_definition("strat_f"))
        params = StrategyParams()
        result = s.on_bar(prices.index[-1], prices, params, {})
        assert isinstance(result, dict)

    def test_weights_non_negative(self):
        from backend.strategies.custom import build_custom_strategy
        from backend.strategies.base import StrategyParams
        prices = _prices(n=200)
        s = build_custom_strategy(_simple_definition("strat_g"))
        result = s.on_bar(prices.index[-1], prices, StrategyParams(), {})
        assert all(v >= 0 for v in result.values())

    def test_benchmark_default(self):
        from backend.strategies.custom import build_custom_strategy
        s = build_custom_strategy(_simple_definition("strat_h"))
        assert isinstance(s.benchmark, str)


class TestCompileRule:
    def test_always_long(self):
        from backend.strategies.custom import _compile_rule
        rule = _compile_rule({"type": "always_long"})
        assert callable(rule)

    def test_momentum_rule(self):
        from backend.strategies.custom import _compile_rule
        rule = _compile_rule({"type": "momentum", "lookback": 60})
        assert callable(rule)

    def test_unknown_rule_type(self):
        from backend.strategies.custom import _compile_rule
        rule = _compile_rule({"type": "unknown_xyz"})
        assert callable(rule)
