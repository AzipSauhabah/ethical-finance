"""
:file: backend/quant/significance.py
:brief: Statistical significance tests for strategy evaluation.
:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

from backend.config import RISK_FREE_RATE

_ANN = 252.0


class TestResult(NamedTuple):
    statistic: float
    p_value: float
    significant: bool
    confidence: float = 0.95


class BootstrapResult(NamedTuple):
    estimate: float
    ci_lower: float
    ci_upper: float
    n_samples: int


def _norm_cdf(x: float) -> float:
    """Approximation of the normal CDF using math.erfc."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


def _t_cdf(t: float, df: int) -> float:
    """Approximation of the Student-t CDF using regularized incomplete beta."""
    # Use scipy-free approximation via continued fraction
    if df <= 0:
        return 0.5
    # Simple normal approximation for large df
    if df > 30:
        return _norm_cdf(t)
    # Regularized incomplete beta approximation
    a = df / 2.0
    b = 0.5
    # Use the relationship: t_cdf(t, df) = 1 - 0.5 * I(df/(df+t^2), df/2, 1/2)
    xx = df / (df + t * t)
    betai = _betainc(a, b, xx)
    if t >= 0:
        return 1.0 - 0.5 * betai
    else:
        return 0.5 * betai


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function approximation."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Use continued fraction expansion
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    # Lentz's continued fraction
    eps = 1e-8
    fpmin = 1e-30
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, 100):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return front * h


def _linregress(x: np.ndarray, y: np.ndarray):
    """Simple OLS regression — returns (slope, intercept, r, p, se)."""
    n = len(x)
    mx, my = x.mean(), y.mean()
    ss_xx = ((x - mx) ** 2).sum()
    ss_xy = ((x - mx) * (y - my)).sum()
    slope = ss_xy / ss_xx if ss_xx != 0 else 0.0
    intercept = my - slope * mx
    y_hat = slope * x + intercept
    ss_res = ((y - y_hat) ** 2).sum()
    ss_tot = ((y - my) ** 2).sum()
    r = math.sqrt(max(0, 1 - ss_res / ss_tot)) if ss_tot != 0 else 0.0
    se = math.sqrt(ss_res / (n - 2) / ss_xx) if (n > 2 and ss_xx != 0) else 0.0
    return slope, intercept, r, 0.0, se


def jobson_korkie(
    r_a: np.ndarray,
    r_b: np.ndarray,
    rf: float = RISK_FREE_RATE,
) -> TestResult:
    rf_d = rf / _ANN
    n = min(len(r_a), len(r_b))
    a, b = r_a[:n] - rf_d, r_b[:n] - rf_d
    mu_a, mu_b = a.mean(), b.mean()
    s_a, s_b = a.std(ddof=1), b.std(ddof=1)
    if s_a == 0 or s_b == 0:
        return TestResult(0.0, 1.0, False)
    sr_a = mu_a / s_a
    sr_b = mu_b / s_b
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
    p_val = float(2 * (1 - _norm_cdf(abs(z))))
    return TestResult(z, p_val, p_val < 0.05)


def bootstrap_ci(
    r: np.ndarray,
    stat_fn: callable,
    n_samples: int = 5_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapResult:
    rng = np.random.default_rng(seed)
    n = len(r)
    samples = np.array([stat_fn(r[rng.integers(0, n, size=n)]) for _ in range(n_samples)])
    alpha = (1 - confidence) / 2
    lo = float(np.quantile(samples, alpha))
    hi = float(np.quantile(samples, 1 - alpha))
    return BootstrapResult(stat_fn(r), lo, hi, n_samples)


def alpha_ttest(
    r: np.ndarray,
    market_r: np.ndarray,
    rf: float = RISK_FREE_RATE,
) -> TestResult:
    rf_d = rf / _ANN
    n = min(len(r), len(market_r))
    y = r[:n] - rf_d
    x = market_r[:n] - rf_d
    slope, intercept, r_val, p_val, se = _linregress(x, y)
    t_stat = float(intercept / se) if se != 0 else 0.0
    p_alpha = float(2 * (1 - _t_cdf(abs(t_stat), df=n - 2)))
    return TestResult(t_stat, p_alpha, p_alpha < 0.05)


def whites_reality_check(
    strategy_returns: list[np.ndarray],
    benchmark_r: np.ndarray,
    n_bootstrap: int = 1_000,
    seed: int = 42,
) -> float:
    rng = np.random.default_rng(seed)
    n = min(len(benchmark_r), *(len(r) for r in strategy_returns))
    diffs = np.array([(s[:n] - benchmark_r[:n]).mean() for s in strategy_returns])
    best_mean = diffs.max()
    boot_maxes = []
    for _ in range(n_bootstrap):
        boot_diffs = []
        for s in strategy_returns:
            idx = rng.integers(0, n, size=n)
            boot_diffs.append((s[:n][idx] - benchmark_r[:n][idx]).mean())
        boot_maxes.append(max(boot_diffs))
    p_val = float(np.mean(np.array(boot_maxes) >= best_mean))
    return p_val
