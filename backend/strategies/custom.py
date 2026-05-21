"""
:file: api/strategies/custom.py
:brief: Builder interface for user-defined custom strategies.

        Users pass a JSON description of their strategy logic via the API;
        the builder compiles it into a Strategy subclass at runtime.

        Supported rule types:
        * ``sma_crossover``   — fast/slow MA crossover
        * ``rsi``             — RSI oversold/overbought
        * ``momentum``        — N-day momentum
        * ``mean_reversion``  — Z-score mean reversion
        * ``always_long``     — trivial buy-and-hold

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from backend.strategies.base import Strategy, StrategyParams
from backend.strategies.registry import strategy_registry

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Rule compilers (pure functions)
# ─────────────────────────────────────────────────────────────────────────────


def _compile_rule(rule: dict[str, Any]):
    """Return a function(prices: pd.Series) → pd.Series of signals."""
    kind = rule.get("type", "").lower()

    if kind == "sma_crossover":
        fast = int(rule.get("fast", 50))
        slow = int(rule.get("slow", 200))

        def _fn(p: pd.Series) -> pd.Series:
            import numpy as np

            return (
                pd.Series(
                    np.sign(p.rolling(fast).mean() - p.rolling(slow).mean()),
                    index=p.index,
                )
                .fillna(0)
                .astype(int)
            )

        return _fn

    elif kind == "rsi":
        period = int(rule.get("period", 14))
        oversold = float(rule.get("oversold", 30))
        overbought = float(rule.get("overbought", 70))

        def _fn(p: pd.Series) -> pd.Series:
            delta = p.diff()
            gain = delta.clip(lower=0).rolling(period).mean()
            loss = (-delta.clip(upper=0)).rolling(period).mean()
            rs = gain / loss.replace(0, float("nan"))
            rsi = 100 - (100 / (1 + rs))
            sig = pd.Series(0, index=p.index)
            sig[rsi < oversold] = 1
            sig[rsi > overbought] = -1
            return sig

        return _fn

    elif kind == "momentum":
        lb = int(rule.get("lookback", 20))

        def _fn(p: pd.Series) -> pd.Series:
            import numpy as np

            return (
                pd.Series(
                    np.sign(p.pct_change(lb)),
                    index=p.index,
                )
                .fillna(0)
                .astype(int)
            )

        return _fn

    elif kind == "mean_reversion":
        w = int(rule.get("window", 20))
        thr = float(rule.get("z_threshold", 1.5))

        def _fn(p: pd.Series) -> pd.Series:
            mu = p.rolling(w).mean()
            sig = p.rolling(w).std(ddof=1)
            z = (p - mu) / sig.replace(0, float("nan"))
            s = pd.Series(0, index=p.index)
            s[z < -thr] = 1
            s[z > thr] = -1
            return s

        return _fn

    else:  # always_long / fallback

        def _fn(p: pd.Series) -> pd.Series:
            return pd.Series(1, index=p.index)

        return _fn


# ─────────────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────────────


def _apply_combination_rules(prices: pd.DataFrame, compiled_rules: list, combination: str) -> "pd.DataFrame":
    """Apply combination rules to prices and return signal DataFrame."""
    import numpy as np
    import pandas as pd

    signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)
    n = len(compiled_rules)
    for col in prices.columns:
        vote = pd.concat([fn(prices[col]) for fn in compiled_rules], axis=1).sum(axis=1)
        if combination == "all":
            signals[col] = (vote == n).astype(int) - (vote == -n).astype(int)
        elif combination == "any":
            signals[col] = np.sign(vote)
        else:
            threshold = n / 2
            def _vote_to_signal(v, th=threshold):
                if v > th:
                    return 1
                if v < -th:
                    return -1
                return 0
            signals[col] = vote.apply(_vote_to_signal)
    return signals


def build_custom_strategy(definition: dict[str, Any]) -> Strategy:
    """Compile a JSON strategy definition into a Strategy instance.

    :param definition: dict with keys:
        * ``name`` (str)
        * ``description`` (str)
        * ``rules`` (list of rule dicts)
        * ``combination`` (``'all'`` | ``'any'`` | ``'majority'``)
        * ``benchmark`` (ticker str, optional)
    :returns: registered Strategy instance

    :raises ValueError: if *name* is missing or already registered as a builtin
    """
    strat_name = str(definition.get("name", "custom")).lower().replace(" ", "_")
    strat_desc = str(definition.get("description", "User-defined strategy"))
    rules_def = list(definition.get("rules", [{"type": "always_long"}]))
    combination = str(definition.get("combination", "majority"))
    bench = str(definition.get("benchmark", "^GSPC"))

    compiled_rules = [_compile_rule(r) for r in rules_def]

    def _generate_signals(prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
        return _apply_combination_rules(prices, compiled_rules, combination)

    # Build class dynamically
    strat_cls = type(
        f"Custom_{strat_name}",
        (Strategy,),
        {
            "name": property(lambda self, n=strat_name: n),
            "description": property(lambda self, d=strat_desc: d),
            "benchmark": property(lambda self, b=bench: b),
            "generate_signals": _generate_signals,
        },
    )

    # Register (overwrite if already exists)
    strategy_registry.register(strat_cls)
    log.info("Custom strategy '%s' registered with %d rules.", strat_name, len(compiled_rules))
    return strat_cls()
