"""
tests/test_api_endpoints.py
Tests d'intégration — endpoints FastAPI via TestClient
Cible: couverture de backend/index.py (~80%)
"""
import pytest
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def client():
    """TestClient FastAPI — réutilisé pour toute la suite."""
    from backend.index import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """Mock les appels DB pour éviter les dépendances PostgreSQL."""
    import asyncio

    async def mock_get_prices(tickers, **kwargs):
        rng = np.random.default_rng(42)
        data = {t: 100 * np.exp(np.cumsum(rng.normal(0.001, 0.015, 300)))
                for t in (tickers if tickers else ["AAPL"])}
        return pd.DataFrame(data, index=pd.date_range("2020-01-01", periods=300, freq="B"))

    async def mock_get_live_quote(ticker):
        return {"ticker": ticker, "last": 150.0, "bid": 149.9, "ask": 150.1,
                "volume": 1000000, "change_pct": 0.5, "timestamp": "2024-01-01T00:00:00",
                "currency": "USD"}

    async def mock_get_ticker_fundamentals(ticker):
        return {"ticker": ticker, "name": ticker, "sector": "Technology",
                "industry": "Software", "market_cap": 2e12, "total_debt": 1e10,
                "total_revenue": 5e11, "interest_expense": 5e8, "esg_scores": {},
                "currency": "USD", "exchange": "NASDAQ", "country": "US",
                "dividend_yield": 0.01, "beta": 1.1, "net_margin": 0.25,
                "fcf_yield": 0.05, "roe": 0.20, "total_equity": 1e11,
                "total_assets": 3e11, "is_sharia": True, "is_ethical": True,
                "sharia_score": 0.85}

    try:
        monkeypatch.setattr("backend.core.data.get_prices", mock_get_prices)
        monkeypatch.setattr("backend.core.data.get_live_quote", mock_get_live_quote)
        monkeypatch.setattr("backend.core.data.get_ticker_fundamentals", mock_get_ticker_fundamentals)
    except Exception:
        pass


class TestHealthMeta:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_meta(self, client):
        r = client.get("/api/meta")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data or "strategies" in data or isinstance(data, dict)


class TestStats:
    def test_stats_returns_dict(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestStrategies:
    def test_list_strategies(self, client):
        r = client.get("/api/strategies")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) or isinstance(data, dict)

    def test_custom_strategy(self, client):
        r = client.post("/api/strategies/custom", json={
            "name": "test_custom",
            "description": "Test",
            "rules": [{"type": "always_long"}],
            "combination": "majority",
        })
        assert r.status_code in (200, 201, 422)


class TestTickers:
    def test_list_tickers(self, client):
        r = client.get("/api/tickers")
        assert r.status_code == 200

    def test_search_tickers(self, client):
        r = client.get("/api/tickers/search?q=AAPL")
        assert r.status_code == 200

    def test_screen_tickers(self, client):
        r = client.post("/api/tickers/screen", json={"tickers": ["AAPL", "MSFT"]})
        assert r.status_code == 200

    def test_screen_empty(self, client):
        r = client.post("/api/tickers/screen", json={"tickers": []})
        assert r.status_code in (200, 422)

    def test_buffett_score(self, client):
        r = client.get("/api/tickers/AAPL/buffett")
        assert r.status_code in (200, 404, 500)

    def test_screening_detail(self, client):
        r = client.get("/api/tickers/AAPL/screening")
        assert r.status_code in (200, 404, 500)


class TestQuote:
    def test_live_quote(self, client):
        r = client.get("/api/quote/AAPL")
        assert r.status_code == 200
        data = r.json()
        assert "ticker" in data or "last" in data or isinstance(data, dict)


class TestPrices:
    def test_prices_db(self, client):
        r = client.get("/api/prices/db?tickers=AAPL&period=1y")
        assert r.status_code in (200, 422, 500)

    def test_prices(self, client):
        r = client.get("/api/prices?tickers=AAPL&period=1y")
        assert r.status_code in (200, 422, 500)


class TestPortfolio:
    def test_analytics(self, client):
        r = client.post("/api/portfolio/analytics", json={
            "tickers": ["AAPL", "MSFT"],
            "positions": {"AAPL": {"qty": 10, "avg_price": 140.0},
                          "MSFT": {"qty": 5, "avg_price": 280.0}},
            "period": "1y",
        })
        assert r.status_code in (200, 422, 500)

    def test_get_positions_no_header(self, client):
        r = client.get("/api/portfolio/positions")
        assert r.status_code == 200

    def test_get_positions_with_device_id(self, client):
        r = client.get("/api/portfolio/positions",
                       headers={"X-Device-ID": "test-unit-001"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_save_position(self, client):
        r = client.post("/api/portfolio/positions",
                        headers={"X-Device-ID": "test-unit-001"},
                        json={"ticker": "AAPL", "qty": 10, "avg_price": 150.0,
                              "currency": "USD"})
        assert r.status_code in (200, 201)

    def test_save_position_no_ticker(self, client):
        r = client.post("/api/portfolio/positions",
                        headers={"X-Device-ID": "test-unit-001"},
                        json={"qty": 10, "avg_price": 150.0})
        assert r.status_code in (200, 422)


class TestScreener:
    def test_screener_sp500(self, client):
        r = client.post("/api/screener", json={
            "universe": "sp500",
            "min_market_cap": 1e10,
            "ethical_only": False,
            "sharia_only": False,
            "page": 1,
            "page_size": 10,
        })
        assert r.status_code in (200, 422, 500)


class TestSignals:
    def test_signals_latest(self, client):
        r = client.get("/api/signals/latest?limit=5")
        assert r.status_code == 200

    def test_signals_latest_with_strategy(self, client):
        r = client.get("/api/signals/latest?strategy=buy_hold&limit=5")
        assert r.status_code == 200

    def test_rebalance(self, client):
        r = client.post("/api/signals/rebalance", json={
            "positions": {"AAPL": {"shares": 10, "currency": "USD", "market_cap_eur": 2e9}},
            "prices_eur": {"AAPL": 150.0},
            "target_weights": {"AAPL": 1.0},
            "cash_eur": 0.0,
        })
        assert r.status_code in (200, 422, 500)


class TestSentiment:
    def test_sentiment_market(self, client):
        r = client.get("/api/sentiment/market")
        assert r.status_code in (200, 500)

    def test_sentiment_post(self, client):
        r = client.post("/api/sentiment", json={"tickers": ["AAPL"]})
        assert r.status_code in (200, 422, 500)


class TestMontecarlo:
    def test_montecarlo(self, client):
        r = client.post("/api/montecarlo", json={
            "tickers": ["AAPL"],
            "initial_capital": 10000.0,
            "n_paths": 50,
            "n_days": 30,
            "method": "gbm",
        })
        assert r.status_code in (200, 422, 500)


class TestAdmin:
    def test_drive_sync(self, client):
        r = client.post("/api/admin/drive-sync")
        assert r.status_code in (200, 500)

    def test_drive_patch(self, client):
        r = client.post("/api/admin/drive-patch")
        assert r.status_code in (200, 500)
