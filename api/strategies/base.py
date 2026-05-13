"""
:file: api/strategies/base.py
:brief: Abstract base class for all investment strategies.

        Uses the Template Method pattern: subclasses implement
        ``generate_signals()``; the base class handles everything else.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class StrategyParams:
    """User-facing parameter bundle passed to every strategy."""
    initial_capital:     float = 30_000.0
    monthly_contribution: float = 0.0
    max_position_pct:    float = 0.25     # max weight per asset
    stop_loss_pct:       float | None = 0.10
    broker:              str   = "default"
    account_type:        str   = "CTO"    # CTO | PEA
    rebalance_frequency: str   = "monthly"  # daily | weekly | monthly | quarterly
    custom:              dict  = field(default_factory=dict)


class Strategy(abc.ABC):
    """Abstract strategy.  All built-in and custom strategies inherit from this.

    Template method pattern:
      * Override :meth:`generate_signals` to define entry/exit logic.
      * Optionally override :meth:`param_space` for Bayesian calibration.
      * Optionally override :meth:`name` and :meth:`description`.
    """

    # ── Required overrides ────────────────────────────────────────────────

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``'momentum'``."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """One-sentence description shown in the UI."""

    @abc.abstractmethod
    def generate_signals(
        self,
        prices: pd.DataFrame,
        params: StrategyParams,
    ) -> pd.DataFrame:
        """Return a DataFrame of signals aligned to *prices* index.

        :param prices: adjusted close prices (columns = tickers)
        :param params: user-facing parameters
        :returns: DataFrame with same index as *prices*; columns = tickers;
                  values ∈ {-1, 0, +1}
        """

    # ── Optional overrides ────────────────────────────────────────────────

    @property
    def param_space(self) -> dict[str, Any]:
        """Parameter search space for Bayesian calibration.

        :returns: dict mapping param names to (lo, hi) tuples or choice lists.
                  Empty dict → no calibration.
        """
        return {}

    @property
    def benchmark(self) -> str:
        """Default benchmark ticker for this strategy."""
        return "^GSPC"

    # ── Concrete helpers ──────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<Strategy name={self.name!r}>"

    def validate_params(self, params: StrategyParams) -> None:
        """Raise ValueError if params are invalid for this strategy."""
        if params.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not (0 < params.max_position_pct <= 1):
            raise ValueError("max_position_pct must be in (0, 1]")
