"""
:file: tests/conftest.py
:brief: Shared pytest fixtures for the test suite.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def deterministic_prices() -> pd.DataFrame:
    """A 3-ticker, 500-day price DataFrame with known stochastic properties.

    Seeded so tests are reproducible.
    """
    rng = np.random.default_rng(42)
    n_days = 500
    dates = pd.bdate_range("2020-01-01", periods=n_days)

    # Three tickers with different drift / vol
    aapl = 100 * np.exp(np.cumsum(rng.normal(0.0008, 0.018, n_days)))
    msft = 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.016, n_days)))
    googl = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.020, n_days)))

    return pd.DataFrame(
        {"AAPL": aapl, "MSFT": msft, "GOOGL": googl},
        index=dates,
    )


@pytest.fixture
def deterministic_returns() -> np.ndarray:
    """500-day daily returns series with known stats."""
    rng = np.random.default_rng(42)
    return rng.normal(0.0008, 0.015, 500)


@pytest.fixture
def stable_returns() -> np.ndarray:
    """Pure positive drift, very low vol — Sharpe should be very high."""
    rng = np.random.default_rng(7)
    return rng.normal(0.002, 0.005, 250)


@pytest.fixture
def benchmark_returns() -> np.ndarray:
    """A market-like return series for benchmark comparison tests."""
    rng = np.random.default_rng(123)
    return rng.normal(0.0004, 0.012, 500)


@pytest.fixture
def fx_rates() -> dict[str, float]:
    return {"USDEUR": 0.92, "EURUSD": 1.087}


@pytest.fixture
def currencies() -> dict[str, str]:
    return {"AAPL": "USD", "MSFT": "USD", "GOOGL": "USD"}
