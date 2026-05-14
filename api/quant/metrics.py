"""
:file: api/quant/metrics.py
:brief: 25+ risk/return metrics computed from daily return series.
        All functions are pure — no I/O, no side-effects.
        Designed for both per-strategy and per-ticker analysis.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

from api.config import RISK_FREE_RATE

# ─────────────────────────────────────────────────────────────────────────────
# Fundamental building blocks
# ─────────────────────────────────────────────────────────────────────────────

_ANN = 252.0  # trading days per year


def _to_arr(r: Sequence[float] | pd.Series) -> np.ndarray:
    return np.asarray(r, dtype=float)


def _excess(r: np.ndarray, rf_daily: float) -> np.ndarray:
    return r - rf_daily


def _downside(r: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    return r[r < threshold]


def _nav(r: np.ndarray) -> np.ndarray:
    """Cumulative NAV from daily returns."""
    return np.cumprod(1.0 + r)


# ─────────────────────────────────────────────────────────────────────────────
# Returns & NAV
# ─────────────────────────────────────────────────────────────────────────────


def total_return(r: Sequence[float]) -> float:
    arr = _to_arr(r)
    return float(np.prod(1.0 + arr) - 1.0)


def cagr(r: Sequence[float], n_days: int | None = None) -> float:
    arr = _to_arr(r)
    n = n_days or len(arr)
    cum = float(np.prod(1.0 + arr))
    return float(cum ** (_ANN / n) - 1.0) if n > 0 else 0.0


def annualised_volatility(r: Sequence[float]) -> float:
    return float(np.std(_to_arr(r), ddof=1) * math.sqrt(_ANN))


# ─────────────────────────────────────────────────────────────────────────────
# Risk-adjusted metrics
# ─────────────────────────────────────────────────────────────────────────────


def sharpe_ratio(r: Sequence[float], rf: float = RISK_FREE_RATE) -> float:
    arr = _to_arr(r)
    rf_d = rf / _ANN
    excess = _excess(arr, rf_d)
    std = float(np.std(excess, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * math.sqrt(_ANN))


def sortino_ratio(r: Sequence[float], rf: float = RISK_FREE_RATE) -> float:
    arr = _to_arr(r)
    rf_d = rf / _ANN
    exc = _excess(arr, rf_d)
    down = _downside(arr, 0.0)
    if len(down) == 0:
        return float("inf")
    downside_std = float(np.std(down, ddof=1)) * math.sqrt(_ANN)
    if downside_std == 0:
        return 0.0
    return float(np.mean(exc) * _ANN / downside_std)


def calmar_ratio(r: Sequence[float]) -> float:
    c = cagr(r)
    mdd = max_drawdown(r)
    if mdd == 0:
        return 0.0
    return abs(c / mdd)


def omega_ratio(r: Sequence[float], threshold: float = 0.0) -> float:
    """Omega = E[gains above threshold] / E[losses below threshold]."""
    arr = _to_arr(r)
    gains = arr[arr > threshold] - threshold
    losses = threshold - arr[arr < threshold]
    if losses.sum() == 0:
        return float("inf")
    return float(gains.sum() / losses.sum())


def treynor_ratio(r: Sequence[float], beta: float, rf: float = RISK_FREE_RATE) -> float:
    if beta == 0:
        return 0.0
    return float((cagr(r) - rf) / beta)


def information_ratio(r: Sequence[float], benchmark_r: Sequence[float]) -> float:
    arr = _to_arr(r)
    bench = _to_arr(benchmark_r)
    diff = arr - bench
    std = float(np.std(diff, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(diff) / std * math.sqrt(_ANN))


# ─────────────────────────────────────────────────────────────────────────────
# Drawdown metrics
# ─────────────────────────────────────────────────────────────────────────────


def max_drawdown(r: Sequence[float]) -> float:
    """Maximum peak-to-trough drawdown (negative number)."""
    nav = _nav(_to_arr(r))
    peak = np.maximum.accumulate(nav)
    dd = (nav - peak) / peak
    return float(dd.min())


def drawdown_series(r: Sequence[float]) -> np.ndarray:
    nav = _nav(_to_arr(r))
    peak = np.maximum.accumulate(nav)
    return (nav - peak) / peak


def average_drawdown(r: Sequence[float]) -> float:
    dd = drawdown_series(r)
    neg = dd[dd < 0]
    return float(neg.mean()) if len(neg) else 0.0


def recovery_factor(r: Sequence[float]) -> float:
    tr = total_return(r)
    mdd = abs(max_drawdown(r))
    return float(tr / mdd) if mdd else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Value at Risk & CVaR (Expected Shortfall)
# ─────────────────────────────────────────────────────────────────────────────


def var_historical(r: Sequence[float], confidence: float = 0.95) -> float:
    """Historical VaR at *confidence* level (positive = loss)."""
    arr = np.sort(_to_arr(r))
    idx = int((1.0 - confidence) * len(arr))
    return float(-arr[idx])


def cvar_historical(r: Sequence[float], confidence: float = 0.95) -> float:
    """Conditional VaR (Expected Shortfall) — average beyond VaR threshold."""
    arr = np.sort(_to_arr(r))
    cutoff = int((1.0 - confidence) * len(arr))
    return float(-arr[:cutoff].mean())


def var_parametric(r: Sequence[float], confidence: float = 0.95) -> float:
    """Gaussian parametric VaR."""
    from scipy.stats import norm  # lazy import

    arr = _to_arr(r)
    mu, sigma = float(np.mean(arr)), float(np.std(arr, ddof=1))
    return float(-(mu + norm.ppf(1 - confidence) * sigma))


# ─────────────────────────────────────────────────────────────────────────────
# Distribution & tail risk
# ─────────────────────────────────────────────────────────────────────────────


def skewness(r: Sequence[float]) -> float:
    from scipy.stats import skew

    return float(skew(_to_arr(r)))


def excess_kurtosis(r: Sequence[float]) -> float:
    from scipy.stats import kurtosis

    return float(kurtosis(_to_arr(r)))


def tail_ratio(r: Sequence[float], pct: float = 0.05) -> float:
    """95th-percentile gain / 95th-percentile loss magnitude."""
    arr = _to_arr(r)
    gain = float(np.percentile(arr, 100 * (1 - pct)))
    loss = float(abs(np.percentile(arr, 100 * pct)))
    return float(gain / loss) if loss else 0.0


def hit_rate(r: Sequence[float]) -> float:
    arr = _to_arr(r)
    return float((arr > 0).mean())


def profit_factor(r: Sequence[float]) -> float:
    arr = _to_arr(r)
    gains = arr[arr > 0].sum()
    losses = abs(arr[arr < 0].sum())
    return float(gains / losses) if losses else float("inf")


# ─────────────────────────────────────────────────────────────────────────────
# Beta & correlation
# ─────────────────────────────────────────────────────────────────────────────


def beta(r: Sequence[float], market_r: Sequence[float]) -> float:
    arr = _to_arr(r)
    mkt = _to_arr(market_r)
    n = min(len(arr), len(mkt))
    cov = np.cov(arr[:n], mkt[:n])
    var = cov[1, 1]
    return float(cov[0, 1] / var) if var != 0 else 1.0


def alpha_jensen(
    r: Sequence[float],
    market_r: Sequence[float],
    rf: float = RISK_FREE_RATE,
) -> float:
    b = beta(r, market_r)
    cagr_p = cagr(r)
    cagr_m = cagr(market_r)
    return float(cagr_p - (rf + b * (cagr_m - rf)))


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate — compute all metrics at once
# ─────────────────────────────────────────────────────────────────────────────


def all_metrics(
    r: Sequence[float],
    benchmark_r: Sequence[float] | None = None,
    beta_val: float | None = None,
    rf: float = RISK_FREE_RATE,
) -> dict:
    """Compute all 25+ metrics in one call.

    :returns: flat dict of metric_name → float
    """
    arr = _to_arr(r)
    bench = _to_arr(benchmark_r) if benchmark_r is not None else None

    m: dict[str, float] = {
        "total_return": total_return(arr),
        "cagr": cagr(arr),
        "annualised_volatility": annualised_volatility(arr),
        "sharpe_ratio": sharpe_ratio(arr, rf),
        "sortino_ratio": sortino_ratio(arr, rf),
        "calmar_ratio": calmar_ratio(arr),
        "omega_ratio": omega_ratio(arr),
        "max_drawdown": max_drawdown(arr),
        "average_drawdown": average_drawdown(arr),
        "recovery_factor": recovery_factor(arr),
        "var_95": var_historical(arr, 0.95),
        "cvar_95": cvar_historical(arr, 0.95),
        "var_99": var_historical(arr, 0.99),
        "cvar_99": cvar_historical(arr, 0.99),
        "var_parametric_95": var_parametric(arr, 0.95),
        "skewness": skewness(arr),
        "excess_kurtosis": excess_kurtosis(arr),
        "tail_ratio": tail_ratio(arr),
        "hit_rate": hit_rate(arr),
        "profit_factor": profit_factor(arr),
    }

    if beta_val is not None:
        m["treynor_ratio"] = treynor_ratio(arr, beta_val, rf)

    if bench is not None:
        m["beta"] = beta(arr, bench)
        m["alpha_jensen"] = alpha_jensen(arr, bench, rf)
        m["information_ratio"] = information_ratio(arr, bench)

    return m
