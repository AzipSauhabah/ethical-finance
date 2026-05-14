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
    initial_capital:      float       = 30_000.0
    monthly_contribution: float       = 0.0
    max_position_pct:     float       = 0.25
    stop_loss_pct:        float | None = 0.10
    broker:               str         = "default"
    account_type:         str         = "CTO"
    rebalance_frequency:  str         = "monthly"
    custom:               dict[str, Any] = field(default_factory=dict)


class Strategy(abc.ABC):
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
        self, prices: pd.DataFrame, params: StrategyParams,
    ) -> pd.DataFrame:
        """DEPRECATED. Use :meth:`on_bar` instead.

        Default implementation invokes ``on_bar`` row by row to produce a
        signal matrix.  Strategies wanting maximum performance should
        override only ``on_bar``.
        """
        state: dict[str, Any] = {}
        rows = []
        idx  = []
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
