"""
:file: api/quant/signals.py
:brief: Technical indicator signals and ML-based signal generation.

        Signal functions return a pd.Series of {-1, 0, +1} aligned to the
        price index. All are pure functions operating on price DataFrames.

        ML models: Random Forest + Gradient Boosted Trees (sklearn).

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Technical indicator helpers (vectorised, no loops)
# ─────────────────────────────────────────────────────────────────────────────

def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()

def _rsi(s: pd.Series, period: int = 14) -> pd.Series:
    delta = s.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line   = _ema(s, fast) - _ema(s, slow)
    signal_line = _ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": histogram})

def _bollinger(s: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    mid   = s.rolling(period).mean()
    sigma = s.rolling(period).std(ddof=1)
    return pd.DataFrame({"mid": mid, "upper": mid + std_dev * sigma, "lower": mid - std_dev * sigma})

def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff())
    return (direction * volume).fillna(0).cumsum()


# ─────────────────────────────────────────────────────────────────────────────
# Signal generators (return pd.Series of -1/0/+1)
# ─────────────────────────────────────────────────────────────────────────────

def sma_crossover_signal(prices: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    """Golden/death cross signal."""
    fast_ma = prices.rolling(fast).mean()
    slow_ma = prices.rolling(slow).mean()
    sig = np.sign(fast_ma - slow_ma)
    return sig.fillna(0).astype(int)


def rsi_signal(prices: pd.Series, period: int = 14, oversold: float = 30, overbought: float = 70) -> pd.Series:
    rsi = _rsi(prices, period)
    sig = pd.Series(0, index=prices.index)
    sig[rsi < oversold]   =  1
    sig[rsi > overbought] = -1
    return sig


def macd_signal(prices: pd.Series) -> pd.Series:
    df  = _macd(prices)
    sig = np.sign(df["macd"] - df["signal"])
    return sig.fillna(0).astype(int)


def bollinger_signal(prices: pd.Series) -> pd.Series:
    bb  = _bollinger(prices)
    sig = pd.Series(0, index=prices.index)
    sig[prices < bb["lower"]] =  1
    sig[prices > bb["upper"]] = -1
    return sig


def momentum_signal(prices: pd.Series, lookback: int = 20) -> pd.Series:
    mom = prices / prices.shift(lookback) - 1
    return np.sign(mom).fillna(0).astype(int)


def mean_reversion_signal(prices: pd.Series, window: int = 20, threshold: float = 1.5) -> pd.Series:
    mu    = prices.rolling(window).mean()
    sigma = prices.rolling(window).std(ddof=1)
    z     = (prices - mu) / sigma.replace(0, np.nan)
    sig   = pd.Series(0, index=prices.index)
    sig[z < -threshold] =  1
    sig[z >  threshold] = -1
    return sig


def combined_signal(prices: pd.Series) -> pd.Series:
    """Majority vote across multiple technical signals."""
    sigs = pd.concat([
        sma_crossover_signal(prices),
        rsi_signal(prices),
        macd_signal(prices),
        bollinger_signal(prices),
        momentum_signal(prices),
    ], axis=1)
    vote = sigs.sum(axis=1)
    sig  = pd.Series(0, index=prices.index)
    sig[vote >=  2] =  1
    sig[vote <= -2] = -1
    return sig


# ─────────────────────────────────────────────────────────────────────────────
# Feature engineering for ML
# ─────────────────────────────────────────────────────────────────────────────

def build_features(prices: pd.Series) -> pd.DataFrame:
    """Generate feature matrix from price series for ML models."""
    df = pd.DataFrame(index=prices.index)
    df["ret_1"]    = prices.pct_change(1)
    df["ret_5"]    = prices.pct_change(5)
    df["ret_20"]   = prices.pct_change(20)
    df["vol_10"]   = df["ret_1"].rolling(10).std(ddof=1)
    df["vol_20"]   = df["ret_1"].rolling(20).std(ddof=1)
    df["rsi_14"]   = _rsi(prices, 14) / 100.0
    df["ema_ratio"] = _ema(prices, 20) / _ema(prices, 50) - 1
    df["macd_hist"] = _macd(prices)["hist"] / prices
    bb = _bollinger(prices)
    df["bb_pos"] = (prices - bb["lower"]) / (bb["upper"] - bb["lower"] + 1e-9)
    df["mom_20"] = prices / prices.shift(20) - 1
    df["mom_60"] = prices / prices.shift(60) - 1
    return df.dropna()


def ml_signal_rf(
    prices: pd.Series,
    forward_days: int = 5,
    threshold: float = 0.01,
) -> pd.Series:
    """Random Forest signal: predict forward return sign.

    :param forward_days: number of days ahead to predict
    :param threshold: minimum return to trigger a buy/sell (dead-band)
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import label_binarize
    except ImportError:
        log.warning("sklearn not available — returning zero signal")
        return pd.Series(0, index=prices.index)

    X = build_features(prices)
    fwd_ret = prices.shift(-forward_days).pct_change(forward_days).reindex(X.index)
    y = np.where(fwd_ret > threshold, 1, np.where(fwd_ret < -threshold, -1, 0))

    # Walk-forward split: train on first 70 %, predict on rest
    n_train = int(len(X) * 0.70)
    if n_train < 50:
        return pd.Series(0, index=prices.index)

    X_tr, X_te = X.iloc[:n_train], X.iloc[n_train:]
    y_tr       = y[:n_train]

    clf = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42, n_jobs=-1)
    clf.fit(X_tr, y_tr)
    preds = clf.predict(X_te)

    sig = pd.Series(0, index=prices.index)
    sig.iloc[n_train:] = preds
    return sig


def ml_signal_gbm(
    prices: pd.Series,
    forward_days: int = 5,
    threshold: float = 0.01,
) -> pd.Series:
    """Gradient Boosted Trees (sklearn HistGradientBoosting) signal."""
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
    except ImportError:
        log.warning("sklearn not available — returning zero signal")
        return pd.Series(0, index=prices.index)

    X = build_features(prices)
    fwd_ret = prices.shift(-forward_days).pct_change(forward_days).reindex(X.index)
    y = np.where(fwd_ret > threshold, 1, np.where(fwd_ret < -threshold, -1, 0))

    n_train = int(len(X) * 0.70)
    if n_train < 50:
        return pd.Series(0, index=prices.index)

    clf = HistGradientBoostingClassifier(max_iter=300, max_depth=4, random_state=42)
    clf.fit(X.iloc[:n_train], y[:n_train])
    preds = clf.predict(X.iloc[n_train:])

    sig = pd.Series(0, index=prices.index)
    sig.iloc[n_train:] = preds
    return sig
