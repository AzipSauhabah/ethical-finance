"""
backend/quant/factors.py
Pipeline de facteurs — style Zipline CustomFactor
Chaque facteur est calculable sur un univers de tickers depuis les données DB.

Usage dans une stratégie :
    from backend.quant.factors import MomentumFactor, ValueFactor, QualityFactor, FactorPipeline

    pipeline = FactorPipeline([
        MomentumFactor(lookback=252, weight=1.0),
        ValueFactor(metric="fcf_yield", weight=1.0),
        QualityFactor(metric="roe", weight=1.0),
    ])
    scores = pipeline.compute(dt, past_prices, fundamentals)
    top_tickers = scores.nlargest(10).index.tolist()
"""
from __future__ import annotations
import logging
from typing import Any
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


# ── Base ──────────────────────────────────────────────────────────────────────
class Factor:
    """Classe de base pour tous les facteurs."""
    name: str = "base"
    weight: float = 1.0

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def compute(
        self,
        dt: "pd.Timestamp",
        past_prices: "pd.DataFrame",
        fundamentals: dict[str, dict] | None = None,
    ) -> "pd.Series":
        """
        Retourne un score par ticker (normalisé Z-score).
        past_prices: DataFrame[date, ticker]
        fundamentals: {ticker: {net_margin, fcf_yield, roe, ...}}
        """
        raise NotImplementedError

    @staticmethod
    def _zscore(s: "pd.Series") -> "pd.Series":
        """Normalise en Z-score cross-sectionnel."""
        std = s.std()
        if std == 0 or pd.isna(std):
            return s * 0
        return (s - s.mean()) / std

    @staticmethod
    def _winsorize(s: "pd.Series", pct: float = 0.05) -> "pd.Series":
        """Coupe les outliers aux percentiles pct et 1-pct."""
        lo, hi = s.quantile(pct), s.quantile(1 - pct)
        return s.clip(lo, hi)


# ── Facteurs prix ─────────────────────────────────────────────────────────────
class MomentumFactor(Factor):
    """
    Momentum prix sur lookback jours (excluant le dernier mois — skip-1).
    Classique Jegadeesh & Titman (1993).
    """
    name = "momentum"

    def __init__(self, lookback: int = 252, skip: int = 21, weight: float = 1.0):
        super().__init__(weight)
        self.lookback = lookback
        self.skip = skip

    def compute(self, dt, past_prices, fundamentals=None):
        if len(past_prices) < self.lookback + self.skip:
            return pd.Series(dtype=float)
        start = past_prices.iloc[-(self.lookback + self.skip)]
        end = past_prices.iloc[-self.skip]
        rets = (end / start.replace(0, np.nan) - 1).dropna()
        return self._zscore(self._winsorize(rets))


class ReversalFactor(Factor):
    """
    Retournement court terme sur lookback jours.
    Contra-momentum sur 1-4 semaines.
    """
    name = "reversal"

    def __init__(self, lookback: int = 21, weight: float = 1.0):
        super().__init__(weight)
        self.lookback = lookback

    def compute(self, dt, past_prices, fundamentals=None):
        if len(past_prices) < self.lookback:
            return pd.Series(dtype=float)
        rets = (past_prices.iloc[-1] / past_prices.iloc[-self.lookback].replace(0, np.nan) - 1).dropna()
        return self._zscore(self._winsorize(-rets))  # inverse du momentum


class VolatilityFactor(Factor):
    """
    Faible volatilité — facteur Low-Vol (Frazzini & Pedersen 2014).
    Tickers moins volatils ont tendance à surperformer risk-adjusted.
    """
    name = "low_volatility"

    def __init__(self, lookback: int = 63, weight: float = 1.0):
        super().__init__(weight)
        self.lookback = lookback

    def compute(self, dt, past_prices, fundamentals=None):
        if len(past_prices) < self.lookback:
            return pd.Series(dtype=float)
        vols = past_prices.iloc[-self.lookback:].pct_change().std()
        return self._zscore(-vols)  # inverse: faible vol = score élevé


# ── Facteurs fondamentaux ─────────────────────────────────────────────────────
class ValueFactor(Factor):
    """
    Facteur Value depuis les fondamentaux DB.
    Métriques: fcf_yield, pe_ratio (inverse), ev_ebitda (inverse), net_margin
    """
    name = "value"
    HIGHER_IS_BETTER = {"fcf_yield", "net_margin", "earning_yield_sec"}
    LOWER_IS_BETTER  = {"pe_ratio", "ev_ebitda", "debt_equity"}

    def __init__(self, metric: str = "fcf_yield", weight: float = 1.0):
        super().__init__(weight)
        self.metric = metric

    def compute(self, dt, past_prices, fundamentals=None):
        if not fundamentals:
            return pd.Series(dtype=float)
        tickers = list(past_prices.columns)
        scores = {}
        for t in tickers:
            v = (fundamentals.get(t) or {}).get(self.metric)
            if v is not None:
                scores[t] = float(v)
        s = pd.Series(scores)
        if s.empty:
            return s
        if self.metric in self.LOWER_IS_BETTER:
            s = -s
        return self._zscore(self._winsorize(s))


class QualityFactor(Factor):
    """
    Facteur Quality depuis les fondamentaux DB.
    Métriques: roe (calculé), net_margin, fcf_yield, roic_sec
    """
    name = "quality"

    def __init__(self, metric: str = "net_margin", weight: float = 1.0):
        super().__init__(weight)
        self.metric = metric

    def compute(self, dt, past_prices, fundamentals=None):
        if not fundamentals:
            return pd.Series(dtype=float)
        tickers = list(past_prices.columns)
        scores = {}
        for t in tickers:
            fund = fundamentals.get(t) or {}
            if self.metric == "roe":
                # ROE calculé depuis net_margin + total_revenue + total_equity
                nm = fund.get("net_margin")
                rev = fund.get("total_revenue")
                eq = fund.get("total_equity")
                if nm and rev and eq and eq > 0:
                    scores[t] = nm * rev / eq
            else:
                v = fund.get(self.metric)
                if v is not None:
                    scores[t] = float(v)
        s = pd.Series(scores)
        return self._zscore(self._winsorize(s)) if not s.empty else s


class ShariaFactor(Factor):
    """
    Filtre Finance Islamique — score binaire 1/0.
    Permet d'intégrer la conformité AAOIFI comme facteur dans le pipeline.
    """
    name = "sharia"

    def __init__(self, weight: float = 1.0):
        super().__init__(weight)

    def compute(self, dt, past_prices, fundamentals=None):
        if not fundamentals:
            return pd.Series(dtype=float)
        tickers = list(past_prices.columns)
        scores = {}
        for t in tickers:
            fund = fundamentals.get(t) or {}
            # Critères AAOIFI
            debt_ok = (fund.get("sharia_debt_ratio") or 1.0) <= 0.33
            income_ok = (fund.get("sharia_income_ratio") or 1.0) <= 0.05
            haram_ok = (fund.get("haram_revenue_ratio") or 1.0) <= 0.05
            scores[t] = 1.0 if (debt_ok and income_ok and haram_ok) else -999.0
        return pd.Series(scores)


# ── Pipeline ──────────────────────────────────────────────────────────────────
class FactorPipeline:
    """
    Combine plusieurs facteurs en un score composite pondéré.

    Usage:
        pipeline = FactorPipeline([
            MomentumFactor(lookback=252, weight=1.0),
            ValueFactor(metric="fcf_yield", weight=0.5),
            QualityFactor(metric="net_margin", weight=0.5),
        ])
        scores = pipeline.compute(dt, past_prices, fundamentals)
        top10 = scores.nlargest(10).index.tolist()
    """

    def __init__(self, factors: list[Factor]):
        self.factors = factors
        total_w = sum(f.weight for f in factors) or 1.0
        self._weights = [f.weight / total_w for f in factors]

    def compute(
        self,
        dt: "pd.Timestamp",
        past_prices: "pd.DataFrame",
        fundamentals: dict[str, dict] | None = None,
    ) -> "pd.Series":
        """Retourne un score composite par ticker."""
        composite: pd.Series | None = None

        for factor, w in zip(self.factors, self._weights):
            try:
                score = factor.compute(dt, past_prices, fundamentals)
                if score.empty:
                    continue
                # Filtre dur : ShariaFactor avec score < -1 exclut le ticker
                if factor.name == "sharia":
                    if composite is None:
                        composite = score
                    else:
                        composite = composite.reindex(score.index)
                        composite[score < -1] = -999.0
                    continue
                weighted = score * w
                if composite is None:
                    composite = weighted
                else:
                    common = composite.index.intersection(weighted.index)
                    composite = composite.reindex(common).fillna(0) + weighted.reindex(common).fillna(0)
            except Exception as e:
                log.warning("Factor %s error: %s", factor.name, e)

        return composite if composite is not None else pd.Series(dtype=float)
