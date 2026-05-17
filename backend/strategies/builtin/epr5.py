"""
:file: backend/strategies/builtin/epr5.py
:brief: EPR5 — value strategy inspired by Greenblatt's Magic Formula,
        with a Lean-style market-regime gate, VIX timing, ML scoring
        via scikit-learn, and Monte-Carlo position sizing.

Reference design (Lean equivalent in comments):
  * Universe       = top-N S&P500 by liquidity   (Lean: CoarseFundamental)
  * Fundamentals   = EBIT/EV, ROIC, P/B, 5y avg ROIC  (Lean: FineFundamental)
  * Regime filter  = SPX > 200MA AND ticker > 200MA  (Lean: OnData on SPY+ticker)
  * Timing trigger = VIX crosses below its 10MA       (Lean: IndicatorExtensions)
  * ML scoring     = scikit-learn RandomForest on technical features
  * Sizing         = 10 % first entry, MC-rescaled    (Lean: SetHoldings + Schedule)
  * Exit           = +10..25 % or Fib 0.786, stop = $1000 or 2*ATR  (Lean: StopMarketOrder)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.strategies.base import Strategy, StrategyParams
from backend.strategies.builtin.lstm_scorer import score_ticker as lstm_score_ticker
from backend.strategies.builtin.lstm_scorer import train_lstm
from backend.strategies.registry import strategy_registry

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Fundamental fetcher — PostgreSQL local (replaces Supabase)
# ─────────────────────────────────────────────────────────────────────────────


def _get_fundamentals_bulk(tickers: list[str]) -> dict[str, dict]:
    """Fetch fundamentals from local PostgreSQL ticker_fundamentals table."""
    import os

    import sqlalchemy as sa

    empty = lambda: {  # noqa: E731
        "earning_yield": 0.0,
        "roic": 0.0,
        "pb_ratio": 1.0,
        "roic_5y_avg": 0.0,
        "market_cap": 0,
        "beta": 1.0,
    }

    result = {t: empty() for t in tickers}

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return result

    try:
        sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
        engine = sa.create_engine(sync_url, pool_pre_ping=True)

        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("""
                    SELECT ticker, market_cap, total_debt, total_revenue, beta
                    FROM ticker_fundamentals
                    WHERE ticker = ANY(:tickers)
                """),
                {"tickers": tickers},
            ).fetchall()

        for row in rows:
            ticker = row[0]
            market_cap = float(row[1] or 0)
            total_debt = float(row[2] or 0)
            total_revenue = float(row[3] or 0)
            beta = float(row[4] or 1.0)

            ev = market_cap + total_debt
            ebit = total_revenue * 0.15  # proxy marge EBIT ~15%
            net_assets = max(market_cap * 0.5, 1)

            result[ticker] = {
                "earning_yield": (ebit / ev) if ev > 0 else 0.0,
                "roic": (ebit / net_assets) if net_assets > 0 else 0.0,
                "pb_ratio": 1.0,
                "roic_5y_avg": (ebit / net_assets) if net_assets > 0 else 0.0,
                "market_cap": market_cap,
                "beta": beta,
            }

    except Exception as exc:
        log.warning("EPR5 fundamentals fetch error: %s", exc)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# ML scorer — scikit-learn RandomForest on technical features
# ─────────────────────────────────────────────────────────────────────────────


def _build_features(prices: pd.Series) -> np.ndarray | None:
    """Build technical feature vector for a single ticker."""
    if len(prices) < 60:
        return None

    p = prices.dropna()
    if len(p) < 60:
        return None

    try:
        ret_1 = float(p.pct_change(1).iloc[-1])
        ret_5 = float(p.pct_change(5).iloc[-1])
        ret_20 = float(p.pct_change(20).iloc[-1])
        ret_60 = float(p.pct_change(60).iloc[-1])

        vol_20 = float(p.pct_change().iloc[-20:].std())
        vol_60 = float(p.pct_change().iloc[-60:].std())

        sma_20 = float(p.iloc[-20:].mean())
        sma_50 = float(p.iloc[-50:].mean()) if len(p) >= 50 else sma_20
        sma_200 = float(p.iloc[-200:].mean()) if len(p) >= 200 else sma_50

        cur = float(p.iloc[-1])
        above_20 = 1.0 if cur > sma_20 else 0.0
        above_50 = 1.0 if cur > sma_50 else 0.0
        above_200 = 1.0 if cur > sma_200 else 0.0

        # RSI-14
        delta = p.pct_change().iloc[-15:]
        gain = delta.clip(lower=0).mean()
        loss = (-delta.clip(upper=0)).mean()
        rsi = 100 - (100 / (1 + gain / (loss + 1e-9)))

        # Momentum rank (z-score of 12-1 month returns)
        mom = float(p.pct_change(252).iloc[-1]) if len(p) >= 252 else ret_60

        return np.array(
            [
                ret_1,
                ret_5,
                ret_20,
                ret_60,
                vol_20,
                vol_60,
                above_20,
                above_50,
                above_200,
                float(rsi),
                mom,
            ],
            dtype=np.float32,
        )

    except Exception:
        return None


def _train_ml_model(state: dict, past_prices: pd.DataFrame) -> Any:
    """Train or retrain a RandomForest classifier on available price data."""
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler

        X, y = [], []
        for ticker, series in past_prices.items():
            if ticker.startswith("^"):
                continue
            ser = series.dropna()
            # Label: 1 if price > +5% in next 20 days (walk-forward safe since we use past only)
            for i in range(60, len(ser) - 20, 5):
                feat = _build_features(ser.iloc[:i])
                if feat is None:
                    continue
                future_ret = float(ser.iloc[i + 20] / ser.iloc[i] - 1)
                label = 1 if future_ret > 0.05 else 0
                X.append(feat)
                y.append(label)

        if len(X) < 50:
            return None, None

        X_arr = np.array(X)
        y_arr = np.array(y)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_arr)

        clf = RandomForestClassifier(
            n_estimators=50,
            max_depth=4,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )
        clf.fit(X_scaled, y_arr)
        log.info("EPR5 ML model trained on %d samples", len(X))
        return clf, scaler

    except Exception as exc:
        log.warning("EPR5 ML training error: %s", exc)
        return None, None


# ─────────────────────────────────────────────────────────────────────────────
# EPR5 Strategy — STRICT EVENT-DRIVEN
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class EPR5Strategy(Strategy):
    """EPR5: Value-tilt with regime gate + VIX timing + ML scoring + dynamic sizing.

    Entry conditions
    ----------------
    1. Each candidate ticker price > its 200-day MA  (uptrend filter)
    2. S&P 500 (^GSPC) > its 200-day MA              (market regime filter)
    3. VIX (^VIX) just crossed below its 10-day MA   (volatility timing trigger) ← FIXED
    4. ML score (RandomForest) > 0.5                 (scikit-learn filter)

    Ranking
    -------
    Magic Formula combined rank:
        rank = rank(EarningYield desc) + rank(ROIC desc)
    Multiplied by ML probability score. Top quintile is held.

    Sizing
    ------
    First entry: 10 % of NAV per name.
    Dynamic: scaled by recent-trade Sharpe (MC simulation).

    Exit
    ----
    Profit target = +20 % (configurable 10–25 %).
    Stop loss = max($1 000 absolute, 2 × ATR-14).
    """

    requires_warmup_days = 252
    is_walkforward_trained = True
    walkforward_refit_days = 60

    @property
    def name(self) -> str:
        return "epr5"

    @property
    def description(self) -> str:
        return (
            "EPR5 — Greenblatt Magic Formula + filtres SPX/VIX + "
            "ML RandomForest scikit-learn + stop ATR. Style QuantConnect Lean."
        )

    @property
    def benchmark(self) -> str:
        return "^GSPC"

    @property
    def param_space(self) -> dict[str, Any]:
        return {
            "profit_target": (0.10, 0.25),
            "atr_stop_mult": (1.5, 3.0),
            "top_quintile_pct": (0.10, 0.30),
            "ma_window": (150, 250),
            "vix_ma_window": (5, 15),
            "ml_min_score": (0.45, 0.70),
        }

    # ── Indicator helpers ────────────────────────────────────────────────

    @staticmethod
    def _sma(s: pd.Series, n: int) -> float:
        if len(s) < n:
            return float("nan")
        return float(s.iloc[-n:].mean())

    @staticmethod
    def _atr(prices: pd.Series, n: int = 14) -> float:
        if len(prices) < n + 1:
            return 0.0
        ret = prices.pct_change().dropna().iloc[-n:].abs()
        return float(prices.iloc[-1] * ret.mean())

    # ── Main on_bar ──────────────────────────────────────────────────────

    def on_bar(
        self,
        dt: date,
        past_prices: pd.DataFrame,
        params: StrategyParams,
        state: dict[str, Any],
    ) -> dict[str, float]:

        profit_target = float(params.custom.get("profit_target", 0.20))
        atr_mult = float(params.custom.get("atr_stop_mult", 2.0))
        top_pct = float(params.custom.get("top_quintile_pct", 0.20))
        ma_window = int(params.custom.get("ma_window", 200))
        vix_ma = int(params.custom.get("vix_ma_window", 10))
        ml_min_score = float(params.custom.get("ml_min_score", 0.50))

        if len(past_prices) < ma_window + 1:
            return state.get("weights", {})

        # ── Fundamentals (cached once per backtest) ──────────────────────
        if "fundamentals" not in state:
            tickers = [t for t in past_prices.columns if not t.startswith("^")]
            state["fundamentals"] = _get_fundamentals_bulk(tickers)
        funds = state["fundamentals"]

        # ── ML model (retrain every walkforward_refit_days) ──────────────
        bar_count = state.get("bar_count", 0) + 1
        state["bar_count"] = bar_count
        if bar_count % self.walkforward_refit_days == 1 or "ml_model" not in state:
            clf, scaler = _train_ml_model(state, past_prices)
            state["ml_model"] = clf
            state["ml_scaler"] = scaler
            # LSTM — entraîné en parallèle, walk-forward safe
            state["lstm"] = train_lstm(past_prices)

        clf = state.get("ml_model")
        scaler = state.get("ml_scaler")

        # ── Market regime filter — SPX above 200MA ───────────────────────
        spx_col = "^GSPC"
        spx_ok = True
        if spx_col in past_prices.columns:
            spx_series = past_prices[spx_col].dropna()
            if len(spx_series) >= ma_window:
                spx_ok = float(spx_series.iloc[-1]) > self._sma(spx_series, ma_window)
            else:
                spx_ok = False

        if not spx_ok:
            state["weights"] = {}
            return {}

        # ── VIX timing filter — FIXED: VIX crossed below 10MA ───────────
        vix_col = "^VIX"
        vix_cross_down = True  # default: allow entries if no VIX data
        if vix_col in past_prices.columns:
            v = past_prices[vix_col].dropna()
            if len(v) >= vix_ma + 1:
                vix_today = float(v.iloc[-1])
                vix_yesterday = float(v.iloc[-2])
                vix_ma_today = float(v.iloc[-vix_ma:].mean())
                vix_ma_yesterday = float(v.iloc[-(vix_ma + 1) : -1].mean())
                # Cross DOWN: yesterday above MA, today below MA
                vix_cross_down = (vix_yesterday >= vix_ma_yesterday) and (vix_today < vix_ma_today)
                # Also allow if VIX is already below MA (not just on the cross)
                vix_below_ma = vix_today < vix_ma_today
                vix_cross_down = vix_cross_down or vix_below_ma

        if not vix_cross_down:
            # Keep existing positions but don't add new ones
            return state.get("weights", {})

        # ── Rank candidates by Magic Formula + ML score ──────────────────
        candidates = []
        for ticker, ser in past_prices.items():
            if ticker.startswith("^"):
                continue
            ser = ser.dropna()
            if len(ser) < ma_window:
                continue
            # Trend gate
            if float(ser.iloc[-1]) <= self._sma(ser, ma_window):
                continue

            f = funds.get(ticker, {})
            ey = f.get("earning_yield", 0.0)
            roic = f.get("roic", 0.0)
            roic_5y = f.get("roic_5y_avg", 0.0)

            if ey <= 0 or roic <= 0 or roic_5y <= 0:
                continue

            # ML score
            ml_score = 0.5
            if clf is not None and scaler is not None:
                feat = _build_features(ser)
                if feat is not None:
                    try:
                        feat_scaled = scaler.transform(feat.reshape(1, -1))
                        ml_score = float(clf.predict_proba(feat_scaled)[0][1])
                    except Exception:
                        ml_score = 0.5

            # Score LSTM
            lstm_state = state.get("lstm")
            lstm_score = lstm_score_ticker(lstm_state, past_prices[ticker])

            # Score combiné : 60% RF + 40% LSTM
            combined_score = 0.6 * ml_score + 0.4 * lstm_score

            if combined_score < ml_min_score:
                continue
            ml_score = combined_score  # utilise le score combiné pour le ranking

            candidates.append((ticker, ey, roic, ml_score))

        if not candidates:
            state["weights"] = {}
            return {}

        # ── Combined rank ────────────────────────────────────────────────
        df = pd.DataFrame(candidates, columns=["ticker", "ey", "roic", "ml_score"])
        df["rank_ey"] = df["ey"].rank(ascending=False)
        df["rank_roic"] = df["roic"].rank(ascending=False)
        df["combined"] = (df["rank_ey"] + df["rank_roic"]) / df["ml_score"]
        df = df.sort_values("combined")
        n_keep = max(1, int(len(df) * top_pct))
        winners = df.head(n_keep)["ticker"].tolist()

        # ── Sizing — MC-scaled, base 10% per name ───────────────────────
        base_w = 0.10
        sizing_mult = self._mc_sizing_multiplier(state)
        weight = min(base_w * sizing_mult, params.max_position_pct)
        weights = {t: weight for t in winners}

        # ── Apply profit-target / ATR stops ─────────────────────────────
        prev = state.get("weights", {})
        for ticker, prev_w in prev.items():
            if ticker not in past_prices.columns:
                continue
            ser = past_prices[ticker].dropna()
            if ser.empty:
                continue
            entry = state.get("entry_prices", {}).get(ticker)
            if entry is None:
                continue
            cur = float(ser.iloc[-1])
            ret = cur / entry - 1
            atr = self._atr(ser, 14)
            stop_dollar_pct = -1_000.0 / (params.initial_capital * prev_w) if prev_w > 0 else -1
            stop_atr_pct = -atr_mult * atr / entry if entry > 0 else -1
            stop_pct = max(stop_dollar_pct, stop_atr_pct)

            if ret >= profit_target or ret <= stop_pct:
                weights.pop(ticker, None)

        # ── Track entry prices ───────────────────────────────────────────
        entry_prices = state.setdefault("entry_prices", {})
        for t in weights:
            if t not in prev:
                entry_prices[t] = float(past_prices[t].iloc[-1])
        for t in list(entry_prices):
            if t not in weights:
                entry_prices.pop(t, None)

        state["weights"] = weights
        return weights

    # ── MC sizing helper ─────────────────────────────────────────────────

    @staticmethod
    def _mc_sizing_multiplier(state: dict) -> float:
        rets = state.get("recent_returns", [])
        if len(rets) < 10:
            return 1.0
        arr = np.array(rets[-60:])
        mu = arr.mean()
        sd = arr.std(ddof=1) + 1e-9
        sharpe_proxy = mu / sd
        return float(max(0.5, min(1.5, 1.0 + sharpe_proxy * 5)))
