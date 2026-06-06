"""
tests/test_signals_daily.py
Tests unitaires — backend.signals.daily (fonctions pures)
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date

pytestmark = pytest.mark.unit


def _price_series(n=60, mu=0.001, sigma=0.015, seed=42):
    rng = np.random.default_rng(seed)
    ret = rng.normal(mu, sigma, n)
    prices = 100 * np.exp(np.cumsum(ret))
    return pd.Series(prices, index=pd.date_range("2024-01-01", periods=n, freq="B"))


def _prices_df(tickers=("AAPL", "MSFT"), n=60, seed=42):
    rng = np.random.default_rng(seed)
    data = {}
    for i, t in enumerate(tickers):
        ret = rng.normal(0.001, 0.015, n)
        data[t] = 100 * np.exp(np.cumsum(ret))
    return pd.DataFrame(data, index=pd.date_range("2024-01-01", periods=n, freq="B"))


class TestSentimentSignal:
    def test_bullish(self):
        from backend.signals.daily import _sentiment_signal
        assert _sentiment_signal(0.5) == 1

    def test_bearish(self):
        from backend.signals.daily import _sentiment_signal
        assert _sentiment_signal(-0.5) == -1

    def test_neutral_positive(self):
        from backend.signals.daily import _sentiment_signal
        assert _sentiment_signal(0.10) == 0

    def test_neutral_negative(self):
        from backend.signals.daily import _sentiment_signal
        assert _sentiment_signal(-0.10) == 0

    def test_boundary_positive(self):
        from backend.signals.daily import _sentiment_signal
        assert _sentiment_signal(0.15) == 1

    def test_boundary_negative(self):
        from backend.signals.daily import _sentiment_signal
        assert _sentiment_signal(-0.15) == -1

    def test_zero(self):
        from backend.signals.daily import _sentiment_signal
        assert _sentiment_signal(0.0) == 0


class TestSentLabel:
    def test_bullish(self):
        from backend.signals.daily import _sent_label
        assert _sent_label(1) == "bullish"

    def test_bearish(self):
        from backend.signals.daily import _sent_label
        assert _sent_label(-1) == "bearish"

    def test_neutral(self):
        from backend.signals.daily import _sent_label
        assert _sent_label(0) == "neutral"


class TestComputeTickerSignal:
    def test_returns_dict(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df()
        result = _compute_ticker_signal("AAPL", prices, {}, True, date.today())
        assert isinstance(result, dict)

    def test_missing_ticker_returns_none(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df()
        assert _compute_ticker_signal("ZZZZ", prices, {}, True, date.today()) is None

    def test_insufficient_data_returns_none(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df(n=5)
        assert _compute_ticker_signal("AAPL", prices, {}, True, date.today()) is None

    def test_signal_keys(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df(n=60)
        result = _compute_ticker_signal("AAPL", prices, {}, True, date.today())
        assert result is not None
        for key in ("ticker", "signal", "label", "strength", "indicators", "sentiment", "date"):
            assert key in result

    def test_signal_value_range(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df(n=60)
        result = _compute_ticker_signal("AAPL", prices, {}, True, date.today())
        assert result["signal"] in (-1, 0, 1)

    def test_label_values(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df(n=60)
        result = _compute_ticker_signal("AAPL", prices, {}, True, date.today())
        assert result["label"] in ("BUY", "SELL", "HOLD")

    def test_strength_range(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df(n=60)
        result = _compute_ticker_signal("AAPL", prices, {}, True, date.today())
        assert 0.0 <= result["strength"] <= 1.0

    def test_without_sentiment(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df(n=60)
        result = _compute_ticker_signal("AAPL", prices, {}, False, date.today())
        assert result is not None
        assert result["signal"] in (-1, 0, 1)

    def test_with_sentiment_score(self):
        from backend.signals.daily import _compute_ticker_signal
        prices = _prices_df(n=60)
        result = _compute_ticker_signal("AAPL", prices, {"AAPL": 0.8}, True, date.today())
        assert result["sentiment"]["score"] == 0.8
        assert result["sentiment"]["signal"] == "bullish"

    def test_buy_signal_when_all_positive(self):
        from backend.signals.daily import _compute_ticker_signal
        # Série fortement haussière → signal BUY probable
        rng = np.random.default_rng(0)
        ret = np.abs(rng.normal(0.005, 0.005, 80))
        prices_arr = 100 * np.exp(np.cumsum(ret))
        prices = pd.DataFrame(
            {"AAPL": prices_arr},
            index=pd.date_range("2024-01-01", periods=80, freq="B")
        )
        result = _compute_ticker_signal("AAPL", prices, {"AAPL": 0.5}, True, date.today())
        assert result is not None

    def test_sell_signal_when_all_negative(self):
        from backend.signals.daily import _compute_ticker_signal
        # Série fortement baissière → signal SELL probable
        rng = np.random.default_rng(0)
        ret = -np.abs(rng.normal(0.005, 0.005, 80))
        prices_arr = 200 * np.exp(np.cumsum(ret))
        prices = pd.DataFrame(
            {"AAPL": prices_arr},
            index=pd.date_range("2024-01-01", periods=80, freq="B")
        )
        result = _compute_ticker_signal("AAPL", prices, {"AAPL": -0.5}, True, date.today())
        assert result is not None


class TestComputeDailySignalsAsync:
    @pytest.mark.asyncio
    async def test_returns_list(self, monkeypatch):
        import pandas as pd
        from datetime import date, timedelta
        prices = _prices_df(n=60)

        async def mock_get_prices(tickers, start, end):
            return prices

        monkeypatch.setattr("backend.signals.daily.get_prices", mock_get_prices)
        from backend.signals.daily import compute_daily_signals
        result = await compute_daily_signals(["AAPL", "MSFT"], include_sentiment=False)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_empty_tickers(self, monkeypatch):
        async def mock_get_prices(tickers, start, end):
            return pd.DataFrame()
        monkeypatch.setattr("backend.signals.daily.get_prices", mock_get_prices)
        from backend.signals.daily import compute_daily_signals
        result = await compute_daily_signals([], include_sentiment=False)
        assert result == []
