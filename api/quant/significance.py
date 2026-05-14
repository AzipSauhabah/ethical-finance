"""
:file: api/quant/significance.py
:brief: Statistical significance tests for strategy evaluation.

        Tests implemented:
        * Jobson-Korkie (Sharpe ratio difference)
        * Bootstrap confidence intervals
        * Jensen alpha t-test
        * White's Reality Check (multiple testing correction)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
from scipy import stats

from api.config import RISK_FREE_RATE

_ANN = 252.0


# ─────────────────────────────────────────────────────────────────────────────
# Result containers
# ─────────────────────────────────────────────────────────────────────────────


class TestResult(NamedTuple):
    statistic: float
    p_value: float
    significant: bool  # True if p < 0.05
    confidence: float = 0.95


class BootstrapResult(NamedTuple):
    estimate: float
    ci_lower: float
    ci_upper: float
    n_samples: int


# ─────────────────────────────────────────────────────────────────────────────
# Jobson-Korkie test (H0: Sharpe_A == Sharpe_B)
# ─────────────────────────────────────────────────────────────────────────────


def jobson_korkie(
    r_a: np.ndarray,
    r_b: np.ndarray,
    rf: float = RISK_FREE_RATE,
) -> TestResult:
    """Test whether two Sharpe ratios are significantly different.

    Reference: Jobson & Korkie (1981), *Journal of Financial Economics*.

    :param r_a: daily returns of strategy A
    :param r_b: daily returns of strategy B
    :returns: TestResult(z-stat, p-value, significant)
    """
    rf_d = rf / _ANN
    n = min(len(r_a), len(r_b))
    a, b = r_a[:n] - rf_d, r_b[:n] - rf_d

    mu_a, mu_b = a.mean(), b.mean()
    s_a, s_b = a.std(ddof=1), b.std(ddof=1)

    if s_a == 0 or s_b == 0:
        return TestResult(0.0, 1.0, False)

    sr_a = mu_a / s_a
    sr_b = mu_b / s_b

    # Variance of SR difference (Memmel 2003 correction)
    rho = float(np.corrcoef(a, b)[0, 1])
    var_d = (
        (1 / n)
        * (
            2 * s_a**2 * s_b**2
            - 2 * s_a * s_b * rho
            + 0.5 * sr_a**2 * s_b**2
            + 0.5 * sr_b**2 * s_a**2
            - sr_a * sr_b * s_a * s_b * rho**2
        )
        / (s_a**2 * s_b**2)
    )
    if var_d <= 0:
        return TestResult(0.0, 1.0, False)

    z = (sr_a - sr_b) * math.sqrt(n) / math.sqrt(var_d * n)
    p_val = float(2 * (1 - stats.norm.cdf(abs(z))))
    return TestResult(z, p_val, p_val < 0.05)


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap CI
# ─────────────────────────────────────────────────────────────────────────────


def bootstrap_ci(
    r: np.ndarray,
    stat_fn: callable,
    n_samples: int = 5_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapResult:
    """Bootstrap confidence interval for any scalar statistic.

    :param stat_fn: function(np.ndarray) → float
    :param n_samples: number of bootstrap resamples
    :param confidence: e.g. 0.95 for 95 % CI
    """
    rng = np.random.default_rng(seed)
    n = len(r)
    samples = np.array([stat_fn(r[rng.integers(0, n, size=n)]) for _ in range(n_samples)])
    alpha = (1 - confidence) / 2
    lo, hi = float(np.quantile(samples, alpha)), float(np.quantile(samples, 1 - alpha))
    return BootstrapResult(stat_fn(r), lo, hi, n_samples)


# ─────────────────────────────────────────────────────────────────────────────
# Jensen alpha t-test
# ─────────────────────────────────────────────────────────────────────────────


def alpha_ttest(
    r: np.ndarray,
    market_r: np.ndarray,
    rf: float = RISK_FREE_RATE,
) -> TestResult:
    """Test whether Jensen's alpha is significantly different from zero.

    Uses OLS regression of excess returns on market excess returns.
    """
    rf_d = rf / _ANN
    n = min(len(r), len(market_r))
    y = r[:n] - rf_d
    x = market_r[:n] - rf_d

    slope, intercept, r_val, p_val, se = stats.linregress(x, y)
    # annualise alpha
    float(intercept * _ANN)
    t_stat = float(intercept / se) if se != 0 else 0.0
    p_alpha = float(2 * (1 - stats.t.cdf(abs(t_stat), df=n - 2)))
    return TestResult(t_stat, p_alpha, p_alpha < 0.05)


# ─────────────────────────────────────────────────────────────────────────────
# White's Reality Check (multiple testing)
# ─────────────────────────────────────────────────────────────────────────────


def whites_reality_check(
    strategy_returns: list[np.ndarray],
    benchmark_r: np.ndarray,
    n_bootstrap: int = 1_000,
    seed: int = 42,
) -> float:
    """White (2000) reality check p-value for the best strategy.

    Tests H0: no strategy beats the benchmark after accounting for data
    snooping across *len(strategy_returns)* strategies.

    :returns: p-value (low → significant outperformance)
    """
    rng = np.random.default_rng(seed)
    n = min(len(benchmark_r), *(len(r) for r in strategy_returns))
    diffs = np.array([(s[:n] - benchmark_r[:n]).mean() for s in strategy_returns])
    best_mean = diffs.max()

    # Bootstrap distribution of max mean under H0
    boot_maxes = []
    for _ in range(n_bootstrap):
        boot_diffs = []
        for s in strategy_returns:
            idx = rng.integers(0, n, size=n)
            boot_diffs.append((s[:n][idx] - benchmark_r[:n][idx]).mean())
        boot_maxes.append(max(boot_diffs))

    p_val = float(np.mean(np.array(boot_maxes) >= best_mean))
    return p_val
