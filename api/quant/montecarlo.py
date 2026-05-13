"""
:file: api/quant/montecarlo.py
:brief: Monte Carlo simulation engine with strategy parameter calibration
        via Bayesian optimisation (scikit-optimize) and GBM/bootstrap paths.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Iterator

import numpy as np
import pandas as pd

from api.config import MC_SIMULATIONS, MC_HORIZON_DAYS, RISK_FREE_RATE

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Path generators (lazy generators for memory efficiency)
# ─────────────────────────────────────────────────────────────────────────────

def _gbm_paths(
    s0: float,
    mu: float,
    sigma: float,
    n_days: int,
    n_paths: int,
    seed: int = 42,
) -> np.ndarray:
    """Vectorised GBM: returns shape (n_paths, n_days+1)."""
    rng  = np.random.default_rng(seed)
    dt   = 1 / 252
    Z    = rng.standard_normal((n_paths, n_days))
    daily = (mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * Z
    cum  = np.cumsum(daily, axis=1)
    paths = s0 * np.exp(np.hstack([np.zeros((n_paths, 1)), cum]))
    return paths


def _bootstrap_paths(
    historical_returns: np.ndarray,
    s0: float,
    n_days: int,
    n_paths: int,
    block_size: int = 20,
    seed: int = 42,
) -> np.ndarray:
    """Block bootstrap paths preserving autocorrelation structure."""
    rng   = np.random.default_rng(seed)
    n_ret = len(historical_returns)
    paths = np.empty((n_paths, n_days + 1))
    paths[:, 0] = s0

    for p in range(n_paths):
        ret_path = []
        while len(ret_path) < n_days:
            start = rng.integers(0, n_ret - block_size)
            ret_path.extend(historical_returns[start: start + block_size])
        ret_path = np.array(ret_path[:n_days])
        paths[p, 1:] = s0 * np.exp(np.cumsum(ret_path))

    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Simulation result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MCResult:
    """Container for Monte Carlo output."""
    final_values:     np.ndarray          # shape (n_paths,)
    percentile_5:     float
    percentile_25:    float
    median:           float
    percentile_75:    float
    percentile_95:    float
    prob_loss:        float               # P(final < s0)
    var_95:           float               # portfolio-level VaR
    cvar_95:          float
    expected_return:  float
    paths_sample:     np.ndarray = field(default_factory=lambda: np.array([]))  # first 50 paths


# ─────────────────────────────────────────────────────────────────────────────
# Main simulation function
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(
    prices: pd.Series,
    initial_capital: float,
    n_paths: int = MC_SIMULATIONS,
    n_days: int = MC_HORIZON_DAYS,
    method: str = "gbm",          # "gbm" | "bootstrap"
    seed: int = 42,
) -> MCResult:
    """Run Monte Carlo simulation on a price series.

    :param method: ``'gbm'`` fits log-normal, ``'bootstrap'`` resamples history
    :param n_paths: number of simulation paths
    """
    ret = prices.pct_change().dropna().values

    if method == "gbm":
        mu    = float(np.mean(ret) * 252)
        sigma = float(np.std(ret, ddof=1) * math.sqrt(252))
        paths = _gbm_paths(initial_capital, mu, sigma, n_days, n_paths, seed)
    else:
        daily_log = np.log1p(ret)
        paths = _bootstrap_paths(daily_log, initial_capital, n_days, n_paths, seed=seed)

    finals = paths[:, -1]
    returns = finals / initial_capital - 1.0
    sorted_r = np.sort(returns)
    cutoff_5 = int(0.05 * n_paths)

    return MCResult(
        final_values    = finals,
        percentile_5    = float(np.percentile(finals, 5)),
        percentile_25   = float(np.percentile(finals, 25)),
        median          = float(np.median(finals)),
        percentile_75   = float(np.percentile(finals, 75)),
        percentile_95   = float(np.percentile(finals, 95)),
        prob_loss       = float((finals < initial_capital).mean()),
        var_95          = float(-sorted_r[cutoff_5]),
        cvar_95         = float(-sorted_r[:cutoff_5].mean()),
        expected_return = float(np.mean(returns)),
        paths_sample    = paths[:50],   # return 50 paths for chart rendering
    )


# ─────────────────────────────────────────────────────────────────────────────
# Parameter calibration via Bayesian optimisation
# ─────────────────────────────────────────────────────────────────────────────

def calibrate_strategy(
    strategy_fn: Callable[[pd.DataFrame, dict], pd.Series],
    prices: pd.DataFrame,
    param_space: dict,
    objective: str = "sharpe",
    n_calls: int = 50,
    seed: int = 42,
) -> dict:
    """Optimise strategy parameters via Bayesian search (scikit-optimize).

    :param strategy_fn: callable(prices, params) → daily returns Series
    :param param_space:  dict of {name: (lo, hi)} or {name: [choices]}
    :param objective:    ``'sharpe'`` | ``'calmar'`` | ``'sortino'``
    :param n_calls:      number of Bayesian iterations
    :returns: best parameter dict
    """
    try:
        from skopt import gp_minimize
        from skopt.space import Real, Categorical, Integer
    except ImportError:
        log.warning("scikit-optimize not installed — returning default params")
        return {k: (v[0] if isinstance(v, list) else v[0]) for k, v in param_space.items()}

    from api.quant.metrics import sharpe_ratio, calmar_ratio, sortino_ratio

    _obj_map: dict[str, Callable] = {
        "sharpe":  sharpe_ratio,
        "calmar":  calmar_ratio,
        "sortino": sortino_ratio,
    }
    score_fn = _obj_map.get(objective, sharpe_ratio)

    keys = list(param_space.keys())
    dims = []
    for k, v in param_space.items():
        if isinstance(v, list):
            dims.append(Categorical(v, name=k))
        elif isinstance(v, tuple) and len(v) == 2:
            if all(isinstance(x, int) for x in v):
                dims.append(Integer(v[0], v[1], name=k))
            else:
                dims.append(Real(float(v[0]), float(v[1]), name=k))

    def _objective(values: list) -> float:
        params = dict(zip(keys, values))
        try:
            daily_r = strategy_fn(prices, params)
            score   = score_fn(daily_r.dropna().values)
            return -score   # minimise negative metric
        except Exception as exc:
            log.debug("Calibration trial failed: %s", exc)
            return 0.0

    result = gp_minimize(_objective, dims, n_calls=n_calls, random_state=seed, verbose=False)
    best   = dict(zip(keys, result.x))
    log.info("Calibration complete — best params: %s score=%.4f", best, -result.fun)
    return best
