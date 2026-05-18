"""
:file: api/strategies/base.py
:brief: Abstract base for all strategies.

        STRICT event-driven contract:
        * The engine calls :meth:`on_bar` once per trading day.
        * The strategy receives only ``past_prices`` up to and including the
          current bar — no look-ahead is possible by construction.
        * The strategy returns a target-weight dict for the next bar.

        Legacy ``generate_signals`` is kept for backward compatibility but
        marked DEPRECATED.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd


@dataclass
class StrategyParams:
    initial_capital: float = 30_000.0
    monthly_contribution: float = 0.0
    max_position_pct: float = 0.25
    stop_loss_pct: float | None = 0.10
    broker: str = "default"
    allow_fractional: bool = False   # True uniquement pour Revolut
    use_adjusted_close: bool = True  # True = dividendes réinvestis (adj_close), False = prix brut (close)
    account_type: str = "CTO"
    rebalance_frequency: str = "monthly"
    custom: dict[str, Any] = field(default_factory=dict)
    use_var_constraint: bool = False


class PositionManager:
    """
    Mixin fournissant stops par position, trailing stops et ATR sizing.
    Toutes les stratégies héritent de ces méthodes via Strategy.

    Utilisation dans on_bar :
    -------------------------
    weights, entry_prices = self.apply_stops(weights, past_prices, state)
    weight = self.size_by_atr(ticker, past_prices, risk_pct=0.01)
    """

    # ── ATR helper ───────────────────────────────────────────────────────

    @staticmethod
    def atr(prices: pd.Series, n: int = 14) -> float:
        """ATR-14 en valeur absolue (même unité que le prix)."""
        if len(prices) < n + 1:
            return float(prices.iloc[-1]) * 0.02  # fallback 2%
        daily_ranges = prices.pct_change().abs().iloc[-n:]
        return float(prices.iloc[-1] * daily_ranges.mean())

    # ── Position sizing par ATR ───────────────────────────────────────────

    def size_by_atr(
        self,
        ticker: str,
        past_prices: pd.DataFrame,
        risk_pct: float = 0.01,
        stop_atr_mult: float = 2.0,
        max_weight: float = 0.25,
    ) -> float:
        """
        Calcule le poids optimal selon le risque en ATR.

        Formule : poids = risk_pct / (stop_atr_mult × ATR / prix)

        Exemple : risk=1%, ATR=2%, stop=2×ATR=4% → poids=25%
        Exemple : risk=1%, ATR=4%, stop=2×ATR=8% → poids=12.5%

        Args:
            ticker:        symbole du titre
            past_prices:   DataFrame des prix passés
            risk_pct:      % de NAV à risquer par trade (défaut 1%)
            stop_atr_mult: multiple d'ATR pour le stop (défaut 2.0)
            max_weight:    poids maximum (défaut 25%)

        Returns:
            poids entre 0 et max_weight
        """
        if ticker not in past_prices.columns:
            return 0.0
        prices = past_prices[ticker].dropna()
        if len(prices) < 15:
            return risk_pct  # fallback minimal
        current = float(prices.iloc[-1])
        atr_val = self.atr(prices)
        stop_pct = stop_atr_mult * atr_val / max(current, 1e-9)
        weight = risk_pct / max(stop_pct, 0.001)
        return min(weight, max_weight)

    # ── Stops par position ────────────────────────────────────────────────

    def apply_stops(
        self,
        weights: dict[str, float],
        past_prices: pd.DataFrame,
        state: dict,
        stop_loss_pct: float = 0.08,
        profit_target_pct: float | None = None,
        use_trailing: bool = False,
        trailing_pct: float = 0.15,
        stop_atr_mult: float | None = None,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """
        Applique les stops sur les positions existantes.

        Gère trois types de stops (cumulables) :
        1. Stop loss fixe : ferme si P&L ≤ -stop_loss_pct
        2. Profit target : ferme si P&L ≥ profit_target_pct
        3. Trailing stop : ferme si prix redescend de trailing_pct depuis le pic
        4. Stop ATR : ferme si prix < entrée - stop_atr_mult × ATR

        Args:
            weights:          poids actuels {ticker: poids}
            past_prices:      DataFrame des prix passés
            state:            dict persistant de la stratégie
            stop_loss_pct:    stop loss fixe (défaut 8%)
            profit_target_pct: objectif de gain (None = désactivé)
            use_trailing:     activer le trailing stop
            trailing_pct:     recul depuis le pic pour trailing (défaut 15%)
            stop_atr_mult:    multiple ATR pour le stop (None = désactivé)

        Returns:
            (weights_après_stops, entry_prices)
        """
        weights = dict(weights)
        entry_prices = state.setdefault("entry_prices", {})
        high_prices = state.setdefault("high_prices", {})  # pour trailing

        to_close = []

        for ticker in list(weights.keys()):
            if ticker not in past_prices.columns:
                to_close.append(ticker)
                continue

            prices = past_prices[ticker].dropna()
            if prices.empty:
                continue

            current = float(prices.iloc[-1])
            entry = entry_prices.get(ticker)

            if entry is None or entry <= 0:
                # Pas d'entrée enregistrée → enregistrer maintenant
                entry_prices[ticker] = current
                entry = current

            pnl = current / entry - 1

            # 1. Stop loss fixe
            if pnl <= -stop_loss_pct:
                to_close.append(ticker)
                continue

            # 2. Profit target
            if profit_target_pct is not None and pnl >= profit_target_pct:
                to_close.append(ticker)
                continue

            # 3. Trailing stop
            if use_trailing:
                peak = high_prices.get(ticker, current)
                peak = max(peak, current)
                high_prices[ticker] = peak
                drawdown_from_peak = current / peak - 1
                if drawdown_from_peak <= -trailing_pct:
                    to_close.append(ticker)
                    continue

            # 4. Stop ATR
            if stop_atr_mult is not None and len(prices) >= 15:
                atr_val = self.atr(prices)
                stop_price = entry - stop_atr_mult * atr_val
                if current < stop_price:
                    to_close.append(ticker)
                    continue

        # Fermer les positions touchées
        for ticker in set(to_close):
            weights.pop(ticker, None)
            entry_prices.pop(ticker, None)
            high_prices.pop(ticker, None)

        # Enregistrer le prix d'entrée des nouvelles positions
        for ticker, w in weights.items():
            if ticker not in entry_prices and ticker in past_prices.columns:
                entry_prices[ticker] = float(past_prices[ticker].iloc[-1])

        return weights, entry_prices

    # ── Trailing stop standalone ──────────────────────────────────────────

    def update_trailing_stops(
        self,
        weights: dict[str, float],
        past_prices: pd.DataFrame,
        state: dict,
        trailing_pct: float = 0.15,
    ) -> dict[str, float]:
        """
        Met à jour les trailing stops et ferme les positions touchées.
        Version standalone si on ne veut que le trailing sans stop fixe.
        """
        weights, _ = self.apply_stops(
            weights,
            past_prices,
            state,
            stop_loss_pct=999.0,  # désactive le stop fixe
            use_trailing=True,
            trailing_pct=trailing_pct,
        )
        return weights


class Strategy(PositionManager, abc.ABC):
    """Strict event-driven strategy contract.

    Subclasses override ``on_bar``. The engine guarantees that ``past_prices``
    contains only history up to and *including* the current ``dt`` — no future
    rows are visible.
    """

    requires_warmup_days: int = 30
    """Minimum number of past bars needed before signals can be generated."""

    is_walkforward_trained: bool = False
    """True if this strategy re-fits a model during the walk; the engine will
    refit every ``walkforward_refit_days`` bars (default 60)."""

    walkforward_refit_days: int = 60

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def description(self) -> str: ...

    @property
    def benchmark(self) -> str:
        return "^GSPC"

    @property
    def param_space(self) -> dict[str, Any]:
        return {}

    # ── New event-driven API ─────────────────────────────────────────────

    @abc.abstractmethod
    def on_bar(
        self,
        dt: date,
        past_prices: pd.DataFrame,
        params: StrategyParams,
        state: dict[str, Any],
    ) -> dict[str, float]:
        """Compute target portfolio weights AFTER seeing the bar ``dt``.

        :param dt:          current trading date
        :param past_prices: prices up to and including ``dt`` (no future rows)
        :param params:      user parameters
        :param state:       persistent per-strategy state dict; the engine
                            allocates one fresh dict at the start of the run
                            and passes it on every call.  Use it to cache
                            fitted models, lookback buffers, etc.
        :returns: mapping ticker → target weight ∈ [0, 1].  Sum ≤ 1; cash =
                  1 − sum.  Tickers not in the dict are treated as weight 0.
        """

    # ── Legacy vectorised path (kept for old custom strategies) ──────────

    def generate_signals(
        self,
        prices: pd.DataFrame,
        params: StrategyParams,
    ) -> pd.DataFrame:
        """DEPRECATED. Use :meth:`on_bar` instead.

        Default implementation invokes ``on_bar`` row by row to produce a
        signal matrix.  Strategies wanting maximum performance should
        override only ``on_bar``.
        """
        state: dict[str, Any] = {}
        rows = []
        idx = []
        for ts in prices.index:
            dt = ts.date() if hasattr(ts, "date") else ts
            past = prices.loc[:ts]
            if len(past) < self.requires_warmup_days:
                rows.append({c: 0.0 for c in prices.columns})
            else:
                rows.append(self.on_bar(dt, past, params, state))
            idx.append(ts)
        return pd.DataFrame(rows, index=idx).fillna(0)

    def validate_params(self, params: StrategyParams) -> None:
        if params.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not (0 < params.max_position_pct <= 1):
            raise ValueError("max_position_pct must be in (0, 1]")

    def __repr__(self) -> str:
        return f"<Strategy name={self.name!r}>"
