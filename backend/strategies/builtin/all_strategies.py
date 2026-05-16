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

Every strategy is implemented in :meth:`on_bar` only.  At each bar,
the engine passes ``past_prices`` containing rows up to and including
the current date.  No future data is accessible — strict causality.

Strategies that fit ML models flag ``is_walkforward_trained = True``;
the engine refits them every ``walkforward_refit_days`` bars to
amortise CPU cost while preserving causality.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.strategies.base import Strategy
from backend.strategies.registry import strategy_registry


def _min_variance_numpy(cov: np.ndarray, max_w: float = 0.25, n_iter: int = 500) -> np.ndarray:
    """Min variance optimization via projected gradient descent."""
    n = cov.shape[0]
    w = np.ones(n) / n
    lr = 0.01
    for _ in range(n_iter):
        grad = 2 * cov @ w
        w = w - lr * grad
        # Project onto simplex with bounds [0, max_w]
        w = np.clip(w, 0, max_w)
        s = w.sum()
        if s > 0:
            w = w / s
    return w


# ─────────────────────────────────────────────────────────────────────────────
# 1. Buy & Hold
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class BuyHoldStrategy(Strategy):
    requires_warmup_days = 1

    @property
    def name(self) -> str:
        return "buy_hold"

    @property
    def description(self) -> str:
        return "Achète et conserve à pondération égale, aucun rééquilibrage."

    def on_bar(self, dt, past_prices, params, state):
        # Buy once at first opportunity, then hold forever
        if state.get("invested"):
            return state["weights"]
        n = len(past_prices.columns)
        weights = {c: 1.0 / n for c in past_prices.columns}
        state["invested"] = True
        state["weights"] = weights
        return weights


# ─────────────────────────────────────────────────────────────────────────────
# 2. Equal-weight (periodic rebalance)
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class EqualWeightStrategy(Strategy):
    requires_warmup_days = 1

    @property
    def name(self) -> str:
        return "equal_weight"

    @property
    def description(self) -> str:
        return "Rééquilibrage périodique à pondération égale."

    def on_bar(self, dt, past_prices, params, state):
        n = len(past_prices.columns)
        return {c: 1.0 / n for c in past_prices.columns}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Momentum 12-1
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class MomentumStrategy(Strategy):
    requires_warmup_days = 252

    @property
    def name(self) -> str:
        return "momentum"

    @property
    def description(self) -> str:
        return "Momentum 12-1 mois : long le top quintile, plat le reste."

    @property
    def param_space(self) -> dict:
        return {"lookback_days": (120, 252), "top_pct": (0.2, 0.5)}

    def on_bar(self, dt, past_prices, params, state):
        lb = int(params.custom.get("lookback_days", 231))
        top = float(params.custom.get("top_pct", 0.30))
        if len(past_prices) < lb + 21:
            return {}
        # 12-1 momentum: total return from t-lb-21 to t-21 (skip last month)
        recent = past_prices.iloc[-21]
        past = past_prices.iloc[-(lb + 21)]
        mom = (recent / past - 1).dropna()
        if mom.empty:
            return {}
        n_top = max(1, int(len(mom) * top))
        winners = mom.nlargest(n_top).index
        w = 1.0 / n_top
        return {t: w for t in winners}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Mean reversion (Z-score)
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class MeanReversionStrategy(Strategy):
    requires_warmup_days = 25

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def description(self) -> str:
        return "Mean reversion : achète les actifs sous-cotés (Z < -1.5σ)."

    @property
    def param_space(self) -> dict:
        return {"window": (10, 40), "z_threshold": (1.0, 2.5)}

    def on_bar(self, dt, past_prices, params, state):
        w = int(params.custom.get("window", 20))
        thr = float(params.custom.get("z_threshold", 1.5))
        if len(past_prices) < w + 1:
            return {}
        recent = past_prices.iloc[-w:]
        mu = recent.mean()
        sd = recent.std(ddof=1).replace(0, np.nan)
        z = (past_prices.iloc[-1] - mu) / sd
        oversold = z[z < -thr].dropna().index
        if len(oversold) == 0:
            return {}
        w_each = 1.0 / len(oversold)
        return {t: w_each for t in oversold}


# ─────────────────────────────────────────────────────────────────────────────
# 5. SMA crossover
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class SMACrossoverStrategy(Strategy):
    requires_warmup_days = 200

    @property
    def name(self) -> str:
        return "sma_crossover"

    @property
    def description(self) -> str:
        return "Golden cross : long quand SMA 50 > SMA 200."

    @property
    def param_space(self) -> dict:
        return {"fast": (20, 100), "slow": (100, 250)}

    def on_bar(self, dt, past_prices, params, state):
        fast = int(params.custom.get("fast", 50))
        slow = int(params.custom.get("slow", 200))
        if len(past_prices) < slow:
            return {}
        ma_f = past_prices.iloc[-fast:].mean()
        ma_s = past_prices.iloc[-slow:].mean()
        longs = ma_f[ma_f > ma_s].index
        if len(longs) == 0:
            return {}
        w = 1.0 / len(longs)
        return {t: w for t in longs}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Risk parity (inverse vol)
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class RiskParityStrategy(Strategy):
    requires_warmup_days = 25

    @property
    def name(self) -> str:
        return "risk_parity"

    @property
    def description(self) -> str:
        return "Risk parity : pondération inverse de la vol 20j."

    @property
    def param_space(self) -> dict:
        return {"vol_window": (10, 60)}

    def on_bar(self, dt, past_prices, params, state):
        w = int(params.custom.get("vol_window", 20))
        if len(past_prices) < w + 2:
            return {}
        rets = past_prices.iloc[-w:].pct_change().dropna()
        vols = rets.std(ddof=1).replace(0, np.nan).dropna()
        if vols.empty:
            return {}
        inv = 1.0 / vols
        weights = (inv / inv.sum()).clip(upper=params.max_position_pct)
        weights = weights / weights.sum()
        return weights.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Min variance (refit every walkforward_refit_days)
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class MinVarianceStrategy(Strategy):
    requires_warmup_days = 60
    is_walkforward_trained = True
    walkforward_refit_days = 60

    @property
    def name(self) -> str:
        return "min_variance"

    @property
    def description(self) -> str:
        return "Markowitz min variance — recalibré toutes les 60 séances."

    def on_bar(self, dt, past_prices, params, state):
        # Refit covariance + weights only every walkforward_refit_days bars
        last_fit = state.get("last_fit_idx", -(10**9))
        cur_idx = len(past_prices)
        if cur_idx - last_fit < self.walkforward_refit_days and "weights" in state:
            return state["weights"]

        rets = past_prices.iloc[-252:].pct_change().dropna()
        if rets.empty:
            return {}
        cov = rets.cov().values
        n = cov.shape[0]

        try:
            # Gradient descent numpy pour Min Variance
            w_opt = _min_variance_numpy(cov, params.max_position_pct)
        except Exception:
            w_opt = np.ones(n) / n

        weights = {t: float(w_opt[i]) for i, t in enumerate(rets.columns)}
        state["last_fit_idx"] = cur_idx
        state["weights"] = weights
        return weights


# ─────────────────────────────────────────────────────────────────────────────
# 8. Dual momentum (Antonacci)
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class DualMomentumStrategy(Strategy):
    requires_warmup_days = 252

    @property
    def name(self) -> str:
        return "dual_momentum"

    @property
    def description(self) -> str:
        return "Dual momentum Antonacci : meilleur actif si abs momentum > 0, sinon cash."

    @property
    def param_space(self) -> dict:
        return {"lookback_days": (120, 252)}

    def on_bar(self, dt, past_prices, params, state):
        lb = int(params.custom.get("lookback_days", 252))
        if len(past_prices) < lb + 1:
            return {}
        recent = past_prices.iloc[-1]
        past = past_prices.iloc[-lb]
        mom = (recent / past - 1).dropna()
        if mom.empty or mom.max() <= 0:
            return {}  # all cash
        best = mom.idxmax()
        return {best: min(1.0, params.max_position_pct * 4)}  # concentrate


# ─────────────────────────────────────────────────────────────────────────────
# 9. Adaptive trend (EMA)
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class AdaptiveTrendStrategy(Strategy):
    requires_warmup_days = 100

    @property
    def name(self) -> str:
        return "adaptive_trend"

    @property
    def description(self) -> str:
        return "Trend following adaptatif : EMA rapide vs EMA lente."

    @property
    def param_space(self) -> dict:
        return {"ema_fast": (5, 30), "ema_slow": (50, 150)}

    def on_bar(self, dt, past_prices, params, state):
        fast = int(params.custom.get("ema_fast", 12))
        slow = int(params.custom.get("ema_slow", 26))
        if len(past_prices) < slow + 5:
            return {}
        ema_f = past_prices.ewm(span=fast, adjust=False).mean().iloc[-1]
        ema_s = past_prices.ewm(span=slow, adjust=False).mean().iloc[-1]
        trending_up = ema_f > ema_s
        longs = ema_f[trending_up].index
        if len(longs) == 0:
            return {}
        w = 1.0 / len(longs)
        return {t: w for t in longs}


# ─────────────────────────────────────────────────────────────────────────────
# 10. ML ensemble — walk-forward refit
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class MLEnsembleStrategy(Strategy):
    requires_warmup_days = 252
    is_walkforward_trained = True
    walkforward_refit_days = 60

    @property
    def name(self) -> str:
        return "ml_ensemble"

    @property
    def description(self) -> str:
        return "RF + Gradient Boosting — walk-forward refit toutes les 60 séances."

    def _build_features(self, series: pd.Series) -> pd.DataFrame:
        df = pd.DataFrame(index=series.index)
        df["ret_1"] = series.pct_change(1)
        df["ret_5"] = series.pct_change(5)
        df["ret_20"] = series.pct_change(20)
        df["vol_10"] = df["ret_1"].rolling(10).std(ddof=1)
        df["mom_60"] = series / series.shift(60) - 1
        # RSI proxy
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        df["rsi"] = 100 - 100 / (1 + (gain / loss.replace(0, np.nan)))
        return df.dropna()

    def on_bar(self, dt, past_prices, params, state):
        last_fit = state.get("last_fit_idx", -(10**9))
        cur_idx = len(past_prices)

        if cur_idx - last_fit < self.walkforward_refit_days and "models" in state:
            # Predict using cached models on the latest features
            return self._predict(state["models"], past_prices)

        # Refit
        try:
            from sklearn.ensemble import HistGradientBoostingClassifier as LGBMClassifier
        except ImportError:
            return {}

        models: dict[str, Any] = {}
        for col in past_prices.columns:
            X = self._build_features(past_prices[col])
            if len(X) < 100:
                continue
            fwd = past_prices[col].shift(-5).pct_change(5).reindex(X.index)
            y = np.where(fwd > 0.01, 1, np.where(fwd < -0.01, -1, 0))
            X_train = X.iloc[:-5]
            y_train = y[:-5]
            if len(X_train) < 50:
                continue
            rf = LGBMClassifier(max_iter=100, max_depth=4, random_state=42)
            gbm = LGBMClassifier(
                n_estimators=100, max_depth=4, random_state=42, boosting_type="gbdt", verbose=-1
            )
            rf.fit(X_train, y_train)
            gbm.fit(X_train, y_train)
            models[col] = (rf, gbm)

        state["last_fit_idx"] = cur_idx
        state["models"] = models
        return self._predict(models, past_prices)

    def _predict(self, models, past_prices):
        longs = []
        for col, (rf, gbm) in models.items():
            X = self._build_features(past_prices[col])
            if X.empty:
                continue
            feat = X.iloc[[-1]]
            vote = int(rf.predict(feat.values)[0]) + int(gbm.predict(feat.values)[0])
            if vote >= 2:
                longs.append(col)
        if not longs:
            return {}
        w = 1.0 / len(longs)
        return {t: w for t in longs}
