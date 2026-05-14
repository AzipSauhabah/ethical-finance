"""
:file: tests/test_metrics.py
:brief: Unit tests for quant metrics — pure functions, no I/O.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from api.quant.metrics import (
    all_metrics,
    annualised_volatility,
    cagr,
    calmar_ratio,
    cvar_historical,
    drawdown_series,
    excess_kurtosis,
    hit_rate,
    max_drawdown,
    omega_ratio,
    profit_factor,
    sharpe_ratio,
    skewness,
    sortino_ratio,
    total_return,
    var_historical,
)

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# Sanity / edge-case tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBasicMetrics:
    def test_total_return_constant_returns(self):
        """1% daily for 10 days → (1.01)^10 - 1."""
        r = np.full(10, 0.01)
        expected = (1.01**10) - 1
        assert math.isclose(total_return(r), expected, rel_tol=1e-9)

    def test_total_return_with_loss(self):
        r = np.array([0.1, -0.1])
        # (1.1 * 0.9) - 1 = -0.01
        assert math.isclose(total_return(r), -0.01, rel_tol=1e-9)

    def test_cagr_one_year_horizon(self):
        """Constant 0.05 % daily for 252 days → CAGR ≈ 13.4 %."""
        r = np.full(252, 0.0005)
        c = cagr(r)
        # cumulative = 1.0005^252 ≈ 1.134
        assert 0.13 < c < 0.14

    def test_annualised_vol_constant_returns_is_zero(self):
        r = np.full(100, 0.001)
        assert annualised_volatility(r) < 1e-9

    def test_annualised_vol_scales_with_sqrt_252(self):
        rng = np.random.default_rng(1)
        r = rng.normal(0, 0.01, 1000)
        vol = annualised_volatility(r)
        assert math.isclose(vol, 0.01 * math.sqrt(252), rel_tol=0.1)


class TestSharpeRatio:
    def test_sharpe_positive_for_positive_excess(self, stable_returns):
        s = sharpe_ratio(stable_returns)
        assert s > 0

    def test_sharpe_zero_vol_handles_gracefully(self):
        """Constant returns → division by ~0 produces a huge but finite number.
        This is mathematically expected (Sharpe → ∞). We just verify no crash."""
        import math

        r = np.full(100, 0.001)
        result = sharpe_ratio(r)
        assert math.isfinite(result)  # not NaN, not inf — just very large

    def test_sharpe_consistent_with_manual_calc(self, deterministic_returns):
        rf_d = 0.035 / 252
        excess = deterministic_returns - rf_d
        expected = (np.mean(excess) / np.std(excess, ddof=1)) * math.sqrt(252)
        assert math.isclose(sharpe_ratio(deterministic_returns), expected, rel_tol=1e-9)


class TestSortinoRatio:
    def test_sortino_infinite_when_no_downside(self):
        r = np.full(100, 0.001)
        s = sortino_ratio(r)
        assert s == float("inf") or s > 100  # depending on impl

    def test_sortino_geq_sharpe_for_skewed_positive(self, stable_returns):
        """Strategies with mostly positive returns: Sortino ≥ Sharpe."""
        s_sharpe = sharpe_ratio(stable_returns)
        s_sortino = sortino_ratio(stable_returns)
        if math.isfinite(s_sortino):
            assert s_sortino >= s_sharpe - 1e-9


class TestDrawdown:
    def test_max_drawdown_never_positive(self, deterministic_returns):
        assert max_drawdown(deterministic_returns) <= 0

    def test_max_drawdown_monotone_uptrend_is_zero(self):
        r = np.full(50, 0.001)
        assert max_drawdown(r) == 0.0

    def test_drawdown_series_starts_at_zero(self, deterministic_returns):
        dd = drawdown_series(deterministic_returns)
        assert dd[0] == 0.0

    def test_drawdown_series_minimum_equals_max_drawdown(self, deterministic_returns):
        dd = drawdown_series(deterministic_returns)
        mdd = max_drawdown(deterministic_returns)
        assert math.isclose(dd.min(), mdd, rel_tol=1e-9)


class TestVaRCVaR:
    def test_var_increases_with_confidence(self, deterministic_returns):
        v95 = var_historical(deterministic_returns, 0.95)
        v99 = var_historical(deterministic_returns, 0.99)
        assert v99 >= v95

    def test_cvar_geq_var(self, deterministic_returns):
        """CVaR is always ≥ VaR (expected shortfall beyond the threshold)."""
        v = var_historical(deterministic_returns, 0.95)
        c = cvar_historical(deterministic_returns, 0.95)
        assert c >= v - 1e-9


class TestCalmarRatio:
    def test_calmar_zero_when_no_drawdown(self):
        r = np.full(252, 0.001)
        c = calmar_ratio(r)
        assert c == 0.0


class TestHitRateProfitFactor:
    def test_hit_rate_in_zero_one(self, deterministic_returns):
        h = hit_rate(deterministic_returns)
        assert 0.0 <= h <= 1.0

    def test_profit_factor_positive_skew(self, stable_returns):
        pf = profit_factor(stable_returns)
        assert pf > 1.0


class TestDistribution:
    def test_skewness_finite(self, deterministic_returns):
        s = skewness(deterministic_returns)
        assert math.isfinite(s)

    def test_kurtosis_finite(self, deterministic_returns):
        k = excess_kurtosis(deterministic_returns)
        assert math.isfinite(k)

    def test_omega_positive(self, deterministic_returns):
        o = omega_ratio(deterministic_returns)
        assert o > 0


class TestAllMetricsAggregator:
    def test_returns_dict_with_expected_keys(self, deterministic_returns):
        m = all_metrics(deterministic_returns)
        for k in (
            "total_return",
            "cagr",
            "sharpe_ratio",
            "max_drawdown",
            "var_95",
            "cvar_95",
            "hit_rate",
            "profit_factor",
        ):
            assert k in m, f"Missing key: {k}"

    def test_with_benchmark_adds_beta_alpha(self, deterministic_returns, benchmark_returns):
        m = all_metrics(deterministic_returns, benchmark_r=benchmark_returns)
        assert "beta" in m
        assert "alpha_jensen" in m
        assert "information_ratio" in m
