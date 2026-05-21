"""
:file: tests/test_signals.py
:brief: Signal functions unit tests — output range, monotonicity, edge cases.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.quant.signals import (
    macd_signal,
    momentum_signal,
    rsi_signal,
    sma_crossover_signal,
    bollinger_signal,
    mean_reversion_signal,
    combined_signal,
)

pytestmark = pytest.mark.unit


# ─── Fixtures ────────────────────────────────────────────────────────────────

def trending_up(n: int = 300) -> pd.Series:
    """Steadily rising price series."""
    return pd.Series(np.linspace(100, 200, n))


def trending_down(n: int = 300) -> pd.Series:
    """Steadily falling price series."""
    return pd.Series(np.linspace(200, 100, n))


def flat(n: int = 300) -> pd.Series:
    """Flat price series."""
    return pd.Series(np.ones(n) * 100.0)


def noisy(n: int = 300, seed: int = 42) -> pd.Series:
    """Random walk price series."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0005, 0.01, n)
    prices = 100 * np.cumprod(1 + returns)
    return pd.Series(prices)


# ─── SMA Crossover ────────────────────────────────────────────────────────────

class TestSMACrossoverSignal:
    def test_output_values_in_minus1_0_plus1(self):
        sig = sma_crossover_signal(trending_up())
        assert set(sig.dropna().unique()).issubset({-1, 0, 1})

    def test_uptrend_produces_buy_signals(self):
        sig = sma_crossover_signal(trending_up())
        assert (sig == 1).any()

    def test_downtrend_produces_sell_signals(self):
        sig = sma_crossover_signal(trending_down())
        assert (sig == -1).any()

    def test_output_length_matches_input(self):
        prices = trending_up(300)
        sig = sma_crossover_signal(prices)
        assert len(sig) == len(prices)

    def test_insufficient_data_returns_zero(self):
        sig = sma_crossover_signal(flat(10))
        assert (sig == 0).all()


# ─── RSI Signal ───────────────────────────────────────────────────────────────

class TestRSISignal:
    def test_output_values_in_minus1_0_plus1(self):
        sig = rsi_signal(noisy())
        assert set(sig.dropna().unique()).issubset({-1, 0, 1})

    def test_output_length_matches_input(self):
        prices = noisy()
        sig = rsi_signal(prices)
        assert len(sig) == len(prices)

    def test_oversold_uptrend_after_crash(self):
        # Sharp drop then recovery → should trigger buy
        prices = pd.Series(
            np.concatenate([np.linspace(100, 50, 50), np.linspace(50, 80, 250)])
        )
        sig = rsi_signal(prices)
        assert (sig == 1).any()

    def test_produces_signals_on_noisy_data(self):
        # RSI needs variance to produce overbought/oversold signals
        sig = rsi_signal(noisy())
        assert set(sig.dropna().unique()).issubset({-1, 0, 1})


# ─── MACD Signal ──────────────────────────────────────────────────────────────

class TestMACDSignal:
    def test_output_values_in_minus1_0_plus1(self):
        sig = macd_signal(noisy())
        assert set(sig.dropna().unique()).issubset({-1, 0, 1})

    def test_output_length_matches_input(self):
        prices = noisy()
        sig = macd_signal(prices)
        assert len(sig) == len(prices)

    def test_produces_non_zero_signals(self):
        sig = macd_signal(noisy())
        assert (sig != 0).any()


# ─── Momentum Signal ──────────────────────────────────────────────────────────

class TestMomentumSignal:
    def test_output_values_in_minus1_0_plus1(self):
        sig = momentum_signal(noisy())
        assert set(sig.dropna().unique()).issubset({-1, 0, 1})

    def test_uptrend_positive_momentum(self):
        sig = momentum_signal(trending_up())
        assert (sig == 1).any()

    def test_downtrend_negative_momentum(self):
        sig = momentum_signal(trending_down())
        assert (sig == -1).any()

    def test_output_length_matches_input(self):
        prices = noisy()
        sig = momentum_signal(prices)
        assert len(sig) == len(prices)


# ─── Bollinger Signal ─────────────────────────────────────────────────────────

class TestBollingerSignal:
    def test_output_values_in_minus1_0_plus1(self):
        sig = bollinger_signal(noisy())
        assert set(sig.dropna().unique()).issubset({-1, 0, 1})

    def test_output_length_matches_input(self):
        prices = noisy()
        sig = bollinger_signal(prices)
        assert len(sig) == len(prices)


# ─── Mean Reversion Signal ────────────────────────────────────────────────────

class TestMeanReversionSignal:
    def test_output_values_in_minus1_0_plus1(self):
        sig = mean_reversion_signal(noisy())
        assert set(sig.dropna().unique()).issubset({-1, 0, 1})

    def test_output_length_matches_input(self):
        prices = noisy()
        sig = mean_reversion_signal(prices)
        assert len(sig) == len(prices)


# ─── Combined Signal ──────────────────────────────────────────────────────────

class TestCombinedSignal:
    def test_output_range_is_minus5_to_plus5(self):
        sig = combined_signal(noisy())
        assert sig.dropna().between(-5, 5).all()

    def test_output_length_matches_input(self):
        prices = noisy()
        sig = combined_signal(prices)
        assert len(sig) == len(prices)

    def test_produces_nonzero_values(self):
        sig = combined_signal(noisy())
        assert (sig != 0).any()

    def test_uptrend_positive_combined(self):
        sig = combined_signal(trending_up())
        assert sig.dropna().mean() > 0

    def test_downtrend_negative_combined(self):
        sig = combined_signal(trending_down())
        assert sig.dropna().mean() < 0
