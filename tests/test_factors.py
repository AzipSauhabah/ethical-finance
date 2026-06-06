"""
tests/test_factors.py
Tests unitaires — backend.quant.factors
"""
import pytest
import numpy as np
import pandas as pd

pytestmark = pytest.mark.unit


def _prices(tickers=("A", "B", "C"), n=300, seed=42):
    rng = np.random.default_rng(seed)
    data = {}
    for t in tickers:
        ret = rng.normal(0.0005, 0.015, n)
        data[t] = 100 * np.exp(np.cumsum(ret))
    return pd.DataFrame(data, index=pd.date_range("2020-01-01", periods=n, freq="B"))


def _fundamentals():
    return {
        "A": {"net_margin": 0.15, "fcf_yield": 0.08, "roe": 0.20,
              "earnings_yield": 0.10, "roic": 0.18,
              "total_revenue": 1e9, "total_equity": 5e8},
        "B": {"net_margin": 0.05, "fcf_yield": 0.03, "roe": 0.08,
              "earnings_yield": 0.05, "roic": 0.07,
              "total_revenue": 5e8, "total_equity": 3e8},
        "C": {"net_margin": 0.25, "fcf_yield": 0.12, "roe": 0.30,
              "earnings_yield": 0.15, "roic": 0.22,
              "total_revenue": 2e9, "total_equity": 8e8},
    }


class TestFactor:
    def test_zscore_normal(self):
        from backend.quant.factors import Factor
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        z = Factor._zscore(s)
        assert abs(z.mean()) < 1e-10

    def test_zscore_zero_std(self):
        from backend.quant.factors import Factor
        z = Factor._zscore(pd.Series([1.0, 1.0, 1.0]))
        assert (z == 0).all()

    def test_winsorize(self):
        from backend.quant.factors import Factor
        s = pd.Series([0.0, 1.0, 2.0, 3.0, 100.0])
        assert Factor._winsorize(s, pct=0.05).max() < 100.0

    def test_compute_raises(self):
        from backend.quant.factors import Factor
        with pytest.raises(NotImplementedError):
            Factor().compute(pd.Timestamp("2021-01-01"), pd.DataFrame())


class TestMomentumFactor:
    def test_compute_returns_series(self):
        from backend.quant.factors import MomentumFactor
        prices = _prices(n=300)
        result = MomentumFactor(lookback=252).compute(prices.index[-1], prices)
        assert isinstance(result, pd.Series) and len(result) == 3

    def test_insufficient_data(self):
        from backend.quant.factors import MomentumFactor
        assert len(MomentumFactor(lookback=252).compute(_prices(n=10).index[-1], _prices(n=10))) == 0


class TestVolatilityFactor:
    def test_compute_returns_series(self):
        from backend.quant.factors import VolatilityFactor
        prices = _prices(n=100)
        result = VolatilityFactor(lookback=60).compute(prices.index[-1], prices)
        assert isinstance(result, pd.Series)

    def test_insufficient_data(self):
        from backend.quant.factors import VolatilityFactor
        assert len(VolatilityFactor(lookback=60).compute(_prices(n=5).index[-1], _prices(n=5))) == 0


class TestValueFactor:
    def test_fcf_yield(self):
        from backend.quant.factors import ValueFactor
        prices = _prices(n=100)
        result = ValueFactor(metric="fcf_yield").compute(prices.index[-1], prices, _fundamentals())
        assert isinstance(result, pd.Series) and len(result) == 3

    def test_earnings_yield(self):
        from backend.quant.factors import ValueFactor
        prices = _prices(n=100)
        result = ValueFactor(metric="earnings_yield").compute(prices.index[-1], prices, _fundamentals())
        assert isinstance(result, pd.Series)

    def test_missing_fundamentals(self):
        from backend.quant.factors import ValueFactor
        assert len(ValueFactor(metric="fcf_yield").compute(_prices(n=100).index[-1], _prices(n=100), None)) == 0


class TestQualityFactor:
    def test_net_margin(self):
        from backend.quant.factors import QualityFactor
        prices = _prices(n=100)
        result = QualityFactor(metric="net_margin").compute(prices.index[-1], prices, _fundamentals())
        assert isinstance(result, pd.Series) and len(result) == 3

    def test_roe_with_full_data(self):
        from backend.quant.factors import QualityFactor
        prices = _prices(n=100)
        result = QualityFactor(metric="roe").compute(prices.index[-1], prices, _fundamentals())
        assert isinstance(result, pd.Series) and len(result) == 3

    def test_missing_fundamentals(self):
        from backend.quant.factors import QualityFactor
        assert len(QualityFactor(metric="net_margin").compute(_prices(n=100).index[-1], _prices(n=100), None)) == 0


class TestShariaFactor:
    def test_returns_series(self):
        from backend.quant.factors import ShariaFactor
        prices = _prices(n=100)
        fund = {t: {"is_sharia": True} for t in ("A", "B", "C")}
        result = ShariaFactor().compute(prices.index[-1], prices, fund)
        assert isinstance(result, pd.Series)

    def test_missing_fundamentals(self):
        from backend.quant.factors import ShariaFactor
        result = ShariaFactor().compute(_prices(n=100).index[-1], _prices(n=100), None)
        assert isinstance(result, pd.Series)


class TestFactorPipeline:
    def test_combined(self):
        from backend.quant.factors import FactorPipeline, MomentumFactor, ValueFactor, QualityFactor
        prices = _prices(n=300)
        pipeline = FactorPipeline([
            MomentumFactor(lookback=252, weight=1.0),
            ValueFactor(metric="fcf_yield", weight=1.0),
            QualityFactor(metric="net_margin", weight=1.0),
        ])
        scores = pipeline.compute(prices.index[-1], prices, _fundamentals())
        assert isinstance(scores, pd.Series) and len(scores) > 0

    def test_empty_pipeline(self):
        from backend.quant.factors import FactorPipeline
        scores = FactorPipeline([]).compute(_prices(n=300).index[-1], _prices(n=300))
        assert isinstance(scores, pd.Series)

    def test_top_n(self):
        from backend.quant.factors import FactorPipeline, MomentumFactor
        prices = _prices(n=300)
        scores = FactorPipeline([MomentumFactor(lookback=252)]).compute(prices.index[-1], prices)
        assert len(scores.nlargest(2)) == 2
