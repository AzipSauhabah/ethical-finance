"""
tests/test_montecarlo.py
Tests unitaires — backend.quant.montecarlo
"""
import pytest
import numpy as np
import pandas as pd

pytestmark = pytest.mark.unit


def _price_series(n=300, seed=42):
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0005, 0.015, n)
    prices = 100 * np.exp(np.cumsum(returns))
    return pd.Series(prices)


class TestGBMPaths:
    def test_shape(self):
        from backend.quant.montecarlo import _gbm_paths
        paths = _gbm_paths(s0=100, mu=0.1, sigma=0.2, n_days=252, n_paths=50)
        assert paths.shape == (50, 253)

    def test_first_col_is_s0(self):
        from backend.quant.montecarlo import _gbm_paths
        paths = _gbm_paths(s0=100, mu=0.1, sigma=0.2, n_days=10, n_paths=20)
        assert np.allclose(paths[:, 0], 100.0)

    def test_positive_values(self):
        from backend.quant.montecarlo import _gbm_paths
        paths = _gbm_paths(s0=100, mu=0.0, sigma=0.3, n_days=50, n_paths=100)
        assert (paths > 0).all()

    def test_reproducible(self):
        from backend.quant.montecarlo import _gbm_paths
        p1 = _gbm_paths(100, 0.1, 0.2, 50, 10, seed=1)
        p2 = _gbm_paths(100, 0.1, 0.2, 50, 10, seed=1)
        assert np.allclose(p1, p2)


class TestBootstrapPaths:
    def test_shape(self):
        from backend.quant.montecarlo import _bootstrap_paths
        hist = np.random.default_rng(0).normal(0.0005, 0.015, 500)
        paths = _bootstrap_paths(hist, s0=100, n_days=60, n_paths=30, block_size=10)
        assert paths.shape == (30, 61)

    def test_first_col_is_s0(self):
        from backend.quant.montecarlo import _bootstrap_paths
        hist = np.random.default_rng(0).normal(0.0005, 0.015, 300)
        paths = _bootstrap_paths(hist, s0=200, n_days=20, n_paths=10)
        assert np.allclose(paths[:, 0], 200.0)


class TestRunSimulation:
    def test_gbm_returns_mcresult(self):
        from backend.quant.montecarlo import run_simulation, MCResult
        result = run_simulation(_price_series(), initial_capital=10000, n_paths=100, n_days=60, method="gbm")
        assert isinstance(result, MCResult)

    def test_bootstrap_returns_mcresult(self):
        from backend.quant.montecarlo import run_simulation, MCResult
        result = run_simulation(_price_series(), initial_capital=10000, n_paths=100, n_days=60, method="bootstrap")
        assert isinstance(result, MCResult)

    def test_percentiles_ordered(self):
        from backend.quant.montecarlo import run_simulation
        r = run_simulation(_price_series(), 10000, n_paths=200, n_days=60)
        assert r.percentile_5 <= r.percentile_25 <= r.median <= r.percentile_75 <= r.percentile_95

    def test_prob_loss_between_0_1(self):
        from backend.quant.montecarlo import run_simulation
        r = run_simulation(_price_series(), 10000, n_paths=200, n_days=60)
        assert 0.0 <= r.prob_loss <= 1.0

    def test_paths_sample_shape(self):
        from backend.quant.montecarlo import run_simulation
        r = run_simulation(_price_series(), 10000, n_paths=200, n_days=60)
        assert r.paths_sample.shape[0] <= 50
        assert r.paths_sample.shape[1] == 61

    def test_expected_return_is_float(self):
        from backend.quant.montecarlo import run_simulation
        r = run_simulation(_price_series(), 10000, n_paths=100, n_days=30)
        assert isinstance(r.expected_return, float)

    def test_var_is_float(self):
        from backend.quant.montecarlo import run_simulation
        r = run_simulation(_price_series(), 10000, n_paths=100, n_days=30)
        assert isinstance(r.var_95, float)


class TestCalibrateStrategy:
    def test_returns_default_when_skopt_missing(self, monkeypatch):
        import builtins
        real_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == "skopt":
                raise ImportError
            return real_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", mock_import)
        from backend.quant import montecarlo
        import importlib
        importlib.reload(montecarlo)
        result = montecarlo.calibrate_strategy(
            lambda p, params: pd.Series([0.001]*99),
            pd.DataFrame({"A": _price_series(100).values}),
            {"lookback": (10, 50)}
        )
        assert isinstance(result, dict)
