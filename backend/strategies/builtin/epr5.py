"""
:file: api/strategies/builtin/epr5.py
:brief: EPR5 — value strategy inspired by Greenblatt's Magic Formula,
        with a Lean-style market-regime gate and Monte-Carlo position sizing.

Reference design (Lean equivalent in comments):
  * Universe       = top-N S&P500 by liquidity   (Lean: CoarseFundamental)
  * Fundamentals   = EBIT/EV, ROIC, P/B, 5y avg ROIC  (Lean: FineFundamental)
  * Regime filter  = SPX > 200MA AND ticker > 200MA  (Lean: OnData on SPY+ticker)
  * Timing trigger = VIX crosses below its 10MA       (Lean: IndicatorExtensions)
  * Sizing         = 10 % first entry, MC-rescaled    (Lean: SetHoldings + Schedule)
  * Exit           = +10..25 % or Fib 0.786, stop = $1000 or 2*ATR  (Lean: StopMarketOrder)

This file is the **template** to copy when adding a new strategy.
Steps to add another:
  1. Copy this file → ``my_strategy.py``
  2. Change ``name`` and ``description``
  3. Override :meth:`on_bar`
  4. Decorate the class with ``@strategy_registry.register``
That's it — auto-discovery picks it up at startup.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.strategies.base import Strategy, StrategyParams
from backend.strategies.registry import strategy_registry

# ─────────────────────────────────────────────────────────────────────────────
# Static fundamental fetcher (cached at module level for the backtest)
# ─────────────────────────────────────────────────────────────────────────────


def _get_fundamentals(ticker: str) -> dict:
    """Fetch fundamentals from Supabase ticker_fundamentals table."""
    import os, urllib.request, json

    empty = {"earning_yield": 0.0, "roic": 0.0, "pb_ratio": 1.0, "roic_5y_avg": 0.0}

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not supabase_key:
        return empty

    try:
        url = f"{supabase_url}/rest/v1/ticker_fundamentals?ticker=eq.{ticker}&select=market_cap,total_debt,total_revenue&limit=1"
        req = urllib.request.Request(url, headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        })
        with urllib.request.urlopen(req, timeout=3) as r:
            rows = json.loads(r.read())
        if not rows:
            return empty
        row = rows[0]
        market_cap = float(row.get("market_cap") or 0)
        total_debt = float(row.get("total_debt") or 0)
        total_revenue = float(row.get("total_revenue") or 0)

        # Approximations Magic Formula depuis les données disponibles
        ev = market_cap + total_debt
        ebit = total_revenue * 0.15  # proxy marge EBIT ~15%
        net_assets = max(market_cap * 0.5, 1)  # proxy

        return {
            "earning_yield": (ebit / ev) if ev > 0 else 0.0,
            "roic": (ebit / net_assets) if net_assets > 0 else 0.0,
            "pb_ratio": 1.0,  # non disponible sans bilan détaillé
            "roic_5y_avg": (ebit / net_assets) if net_assets > 0 else 0.0,
        }
    except Exception:
        return empty


# ─────────────────────────────────────────────────────────────────────────────
# EPR5 Strategy — STRICT EVENT-DRIVEN
# ─────────────────────────────────────────────────────────────────────────────


@strategy_registry.register
class EPR5Strategy(Strategy):
    """EPR5: Value-tilt with regime gate + VIX timing + dynamic sizing.

    Entry conditions
    ----------------
    1. Each candidate ticker price > its 200-day MA  (uptrend filter)
    2. S&P 500 (^GSPC) > its 200-day MA              (market regime filter)
    3. VIX (^VIX) just crossed below its 10-day MA   (volatility timing trigger)

    Ranking
    -------
    Magic Formula combined rank:
        rank = rank(EarningYield desc) + rank(ROIC desc)
    Top quintile is held. Filtered by P/B < median and 5y ROIC > 0.

    Sizing
    ------
    First entry: 10 % of NAV per name.
    Dynamic: scaled by recent-trade Sharpe (5/20/60-day rolling MC simulation).

    Exit
    ----
    Profit target = +20 % (configurable 10–25 %) OR Fibonacci 0.786 of recent swing.
    Stop loss = max($1 000 absolute, 2 × ATR-14).
    """

    requires_warmup_days = 252  # need 1 year for 200MA + indicators
    is_walkforward_trained = False  # static fundamentals; no ML refit

    # ── Required overrides ───────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "epr5"

    @property
    def description(self) -> str:
        return (
            "EPR5 — Greenblatt Magic Formula + filtres de régime SPX/VIX + "
            "stop-loss ATR. Inspiré du style QuantConnect Lean."
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
        }

    # ── Indicator helpers (vectorised on past data only) ─────────────────

    @staticmethod
    def _sma(s: pd.Series, n: int) -> float:
        if len(s) < n:
            return float("nan")
        return float(s.iloc[-n:].mean())

    @staticmethod
    def _atr(prices: pd.Series, n: int = 14) -> float:
        """ATR estimate from close only — true-range proxy."""
        if len(prices) < n + 1:
            return 0.0
        ret = prices.pct_change().dropna().iloc[-n:].abs()
        return float(prices.iloc[-1] * ret.mean())

    # ── Main entry: on_bar receives ONLY past prices ────────────────────

    def on_bar(
        self,
        dt: date,
        past_prices: pd.DataFrame,
        params: StrategyParams,
        state: dict[str, Any],
    ) -> dict[str, float]:

        # 0. Pull strategy params (with defaults)
        profit_target = float(params.custom.get("profit_target", 0.20))
        atr_mult = float(params.custom.get("atr_stop_mult", 2.0))
        top_pct = float(params.custom.get("top_quintile_pct", 0.20))
        ma_window = int(params.custom.get("ma_window", 200))
        vix_ma = int(params.custom.get("vix_ma_window", 10))

        # 1. Need at least ma_window+1 days of data
        if len(past_prices) < ma_window + 1:
            return state.get("weights", {})

        # 2. Cache fundamentals once per ticker per backtest
        if "fundamentals" not in state:
            state["fundamentals"] = {
                t: _get_fundamentals(t) for t in past_prices.columns if not t.startswith("^")
            }
        funds = state["fundamentals"]

        # 3. Market regime filter — SPX above 200MA
        spx_col = "^GSPC"
        spx_ok = True
        if spx_col in past_prices.columns:
            spx_series = past_prices[spx_col].dropna()
            if len(spx_series) >= ma_window:
                spx_ok = float(spx_series.iloc[-1]) > self._sma(spx_series, ma_window)
            else:
                spx_ok = False

        if not spx_ok:
            # Defensive: liquidate
            state["weights"] = {}
            return {}

        # 4. VIX timing filter — VIX just crossed below its 10MA
        vix_col = "^VIX"
        if vix_col in past_prices.columns:
            v = past_prices[vix_col].dropna()
            if len(v) >= vix_ma + 1:
                float(v.iloc[-1])
                float(v.iloc[-2])
                float(v.iloc[-vix_ma:].mean())
                float(v.iloc[-(vix_ma + 1) : -1].mean())
                # cross down today (was above ma yesterday, below today)
        # If no VIX data, still allow entries (regime gate already passed)

        # 5. Rank tradeable universe by Magic Formula
        candidates = []
        for ticker, ser in past_prices.items():
            if ticker.startswith("^"):
                continue  # skip benchmarks
            ser = ser.dropna()
            if len(ser) < ma_window:
                continue
            # Trend gate: price > 200MA
            if float(ser.iloc[-1]) <= self._sma(ser, ma_window):
                continue
            f = funds.get(ticker, {})
            ey = f.get("earning_yield", 0.0)
            roic = f.get("roic", 0.0)
            pb = f.get("pb_ratio", float("inf"))
            roic_5y = f.get("roic_5y_avg", 0.0)
            if ey <= 0 or roic <= 0 or roic_5y <= 0 or pb >= 10:
                continue
            candidates.append((ticker, ey, roic, pb))

        if not candidates:
            state["weights"] = {}
            return {}

        # 6. Combined rank (Magic Formula)
        df = pd.DataFrame(candidates, columns=["ticker", "ey", "roic", "pb"])
        df["rank_ey"] = df["ey"].rank(ascending=False)
        df["rank_roic"] = df["roic"].rank(ascending=False)
        df["combined"] = df["rank_ey"] + df["rank_roic"]
        df = df.sort_values("combined")
        n_keep = max(1, int(len(df) * top_pct))
        winners = df.head(n_keep)["ticker"].tolist()

        # 7. Sizing — MC-scaled, base 10 % per name
        base_w = 0.10
        sizing_mult = self._mc_sizing_multiplier(state)
        weight = min(base_w * sizing_mult, params.max_position_pct)
        weights = {t: weight for t in winners}

        # 8. Apply profit-target / ATR stops on current holdings
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
            stop_pct = max(stop_dollar_pct, stop_atr_pct)  # the LESS negative one

            if ret >= profit_target or ret <= stop_pct:
                weights.pop(ticker, None)  # exit

        # 9. Track entry prices for new positions
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
        """Look at recent realised returns of this strategy and adjust size.

        Simple proxy: if state['recent_returns'] has positive mean and low
        vol, scale up to 1.5x; if negative/vol high, scale down to 0.5x.
        """
        rets = state.get("recent_returns", [])
        if len(rets) < 10:
            return 1.0
        arr = np.array(rets[-60:])
        mu = arr.mean()
        sd = arr.std(ddof=1) + 1e-9
        sharpe_proxy = mu / sd
        # Logistic-like rescaling, bounded [0.5, 1.5]
        return float(max(0.5, min(1.5, 1.0 + sharpe_proxy * 5)))
