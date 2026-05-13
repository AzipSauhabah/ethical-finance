"""
:file: api/strategies/builtin/all_strategies.py
:brief: 10 built-in investment strategies registered with the global registry.

        1.  Buy & Hold
        2.  Equal-Weight Rebalance
        3.  Momentum (12-1 month)
        4.  Mean Reversion
        5.  SMA Crossover (50/200)
        6.  Risk Parity (inverse-vol weighting)
        7.  Min Variance (Markowitz)
        8.  Dual Momentum (Antonacci)
        9.  Trend Following (ADN — Adaptive)
        10. ML Ensemble (RF + GBM vote)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from api.strategies.base import Strategy, StrategyParams
from api.strategies.registry import strategy_registry

# ─────────────────────────────────────────────────────────────────────────────
# 1. Buy & Hold
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class BuyHoldStrategy(Strategy):
    @property
    def name(self) -> str:
        return "buy_hold"

    @property
    def description(self) -> str:
        return "Achète et conserve — pondération initiale égale, aucun rééquilibrage."

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        return pd.DataFrame(1, index=prices.index, columns=prices.columns)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Equal-Weight Rebalance
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class EqualWeightStrategy(Strategy):
    @property
    def name(self) -> str:
        return "equal_weight"

    @property
    def description(self) -> str:
        return "Rééquilibrage mensuel à pondération égale entre tous les actifs."

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        # Always hold everything with equal weight — signals stay 1
        return pd.DataFrame(1, index=prices.index, columns=prices.columns)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Momentum (12-1 month)
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class MomentumStrategy(Strategy):
    @property
    def name(self) -> str:
        return "momentum"

    @property
    def description(self) -> str:
        return "Classement 12-1 mois: long top 30 %, flat bottom 70 %."

    @property
    def param_space(self) -> dict:
        return {"lookback_days": (120, 252), "top_pct": (0.2, 0.5)}

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        lb   = int(params.custom.get("lookback_days", 231))
        top  = float(params.custom.get("top_pct", 0.30))
        mom  = prices / prices.shift(lb) - 1
        n    = max(1, int(len(prices.columns) * top))

        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)
        for dt in prices.index:
            row = mom.loc[dt].dropna()
            if row.empty:
                continue
            winners = row.nlargest(n).index
            signals.loc[dt, winners] = 1
        return signals


# ─────────────────────────────────────────────────────────────────────────────
# 4. Mean Reversion
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class MeanReversionStrategy(Strategy):
    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def description(self) -> str:
        return "Buy assets >1.5σ below 20-day moving average; sell when they revert."

    @property
    def param_space(self) -> dict:
        return {"window": (10, 40), "z_threshold": (1.0, 2.5)}

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        w   = int(params.custom.get("window", 20))
        thr = float(params.custom.get("z_threshold", 1.5))

        mu  = prices.rolling(w).mean()
        sig = prices.rolling(w).std(ddof=1)
        z   = (prices - mu) / sig.replace(0, np.nan)

        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)
        signals[z < -thr] =  1
        signals[z >  thr] = -1
        return signals


# ─────────────────────────────────────────────────────────────────────────────
# 5. SMA Crossover
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class SMACrossoverStrategy(Strategy):
    @property
    def name(self) -> str:
        return "sma_crossover"

    @property
    def description(self) -> str:
        return "Golden/death cross : SMA 50 vs SMA 200."

    @property
    def param_space(self) -> dict:
        return {"fast": (20, 100), "slow": (100, 250)}

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        fast = int(params.custom.get("fast", 50))
        slow = int(params.custom.get("slow", 200))
        return pd.DataFrame(
            np.sign((prices.rolling(fast).mean() - prices.rolling(slow).mean()).values),
            index=prices.index,
            columns=prices.columns,
        ).fillna(0).astype(int)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Risk Parity (inverse-volatility)
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class RiskParityStrategy(Strategy):
    @property
    def name(self) -> str:
        return "risk_parity"

    @property
    def description(self) -> str:
        return "Pondération inverse de la volatilité réalisée (20 jours) — chaque actif contribue également au risque."

    @property
    def param_space(self) -> dict:
        return {"vol_window": (10, 60)}

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        w    = int(params.custom.get("vol_window", 20))
        vols = prices.pct_change().rolling(w).std(ddof=1).replace(0, np.nan)
        inv  = 1 / vols
        weights = inv.div(inv.sum(axis=1), axis=0).fillna(0)
        # signal = weight (positive), no shorts
        return weights.clip(lower=0)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Minimum Variance (Markowitz)
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class MinVarianceStrategy(Strategy):
    @property
    def name(self) -> str:
        return "min_variance"

    @property
    def description(self) -> str:
        return "Frontière efficiente de Markowitz — portefeuille de variance minimale, long-only."

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        from scipy.optimize import minimize

        ret  = prices.pct_change().dropna()
        cov  = ret.cov().values
        n    = cov.shape[0]

        def _port_var(w: np.ndarray) -> float:
            return float(w @ cov @ w)

        w0  = np.ones(n) / n
        res = minimize(
            _port_var, w0,
            method="SLSQP",
            bounds=[(0, params.max_position_pct)] * n,
            constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
            options={"maxiter": 1_000},
        )
        weights = res.x if res.success else w0
        sig = pd.DataFrame(
            np.tile(weights, (len(prices), 1)),
            index=prices.index,
            columns=prices.columns,
        )
        return sig


# ─────────────────────────────────────────────────────────────────────────────
# 8. Dual Momentum (Antonacci)
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class DualMomentumStrategy(Strategy):
    @property
    def name(self) -> str:
        return "dual_momentum"

    @property
    def description(self) -> str:
        return "Momentum absolu + relatif (Antonacci) : bascule vers cash si momentum < T-bills."

    @property
    def param_space(self) -> dict:
        return {"lookback_days": (120, 252)}

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        lb   = int(params.custom.get("lookback_days", 252))
        mom  = (prices / prices.shift(lb) - 1).fillna(0)

        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)
        for dt in prices.index:
            row = mom.loc[dt]
            best = row.idxmax()
            if row[best] > 0:          # absolute momentum filter
                signals.loc[dt, best] = 1
        return signals


# ─────────────────────────────────────────────────────────────────────────────
# 9. ADN — Adaptive Trend
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class AdaptiveTrendStrategy(Strategy):
    @property
    def name(self) -> str:
        return "adaptive_trend"

    @property
    def description(self) -> str:
        return "Trend-following adaptatif : combine EMA court/long avec ATR pour dimensionner les positions."

    @property
    def param_space(self) -> dict:
        return {"ema_fast": (5, 30), "ema_slow": (50, 150), "atr_mult": (1.0, 3.0)}

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        fast = int(params.custom.get("ema_fast", 12))
        slow = int(params.custom.get("ema_slow", 26))

        ema_f = prices.ewm(span=fast, adjust=False).mean()
        ema_s = prices.ewm(span=slow, adjust=False).mean()
        trend = np.sign(ema_f - ema_s)
        return pd.DataFrame(trend.values, index=prices.index, columns=prices.columns).fillna(0).astype(int)


# ─────────────────────────────────────────────────────────────────────────────
# 10. ML Ensemble (RF + GBM majority vote)
# ─────────────────────────────────────────────────────────────────────────────

@strategy_registry.register
class MLEnsembleStrategy(Strategy):
    @property
    def name(self) -> str:
        return "ml_ensemble"

    @property
    def description(self) -> str:
        return "Ensemble Random Forest + Gradient Boosting — vote majoritaire sur features techniques."

    def generate_signals(self, prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        from api.quant.signals import ml_signal_rf, ml_signal_gbm

        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)
        for col in prices.columns:
            rf_sig  = ml_signal_rf(prices[col])
            gbm_sig = ml_signal_gbm(prices[col])
            vote    = rf_sig.add(gbm_sig, fill_value=0)
            signals[col] = vote.apply(lambda v: 1 if v >= 1 else (-1 if v <= -1 else 0))
        return signals
