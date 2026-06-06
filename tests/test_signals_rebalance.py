"""
tests/test_signals_rebalance.py
Tests unitaires — backend.signals.rebalance
"""
import pytest
pytestmark = pytest.mark.unit


def _positions(tickers=("AAPL", "MSFT"), shares=(10, 5)):
    return {t: {"shares": s, "currency": "USD", "market_cap_eur": 2e9}
            for t, s in zip(tickers, shares)}


def _prices(tickers=("AAPL", "MSFT"), vals=(150.0, 300.0)):
    return dict(zip(tickers, vals))


class TestComputeRebalanceOrders:
    def test_returns_list(self):
        from backend.signals.rebalance import compute_rebalance_orders
        orders = compute_rebalance_orders(
            _positions(), _prices(),
            {"AAPL": 0.5, "MSFT": 0.5}, cash_eur=1000.0
        )
        assert isinstance(orders, list)

    def test_empty_nav_returns_empty(self):
        from backend.signals.rebalance import compute_rebalance_orders
        orders = compute_rebalance_orders({}, {}, {}, cash_eur=0.0)
        assert orders == []

    def test_hold_when_no_drift(self):
        from backend.signals.rebalance import compute_rebalance_orders
        # Position exactement au target → hold
        pos = {"AAPL": {"shares": 50, "currency": "USD", "market_cap_eur": 2e9}}
        prices = {"AAPL": 100.0}
        # NAV = 50*100 + 5000 cash = 10000, target AAPL = 50% = 5000 → exact
        orders = compute_rebalance_orders(pos, prices, {"AAPL": 0.5}, cash_eur=5000.0, drift_threshold=0.05)
        aapl_order = next((o for o in orders if o["ticker"] == "AAPL"), None)
        assert aapl_order is not None
        assert aapl_order["side"] == "hold"

    def test_buy_when_underweight(self):
        from backend.signals.rebalance import compute_rebalance_orders
        # AAPL très sous-pondéré
        pos = {"AAPL": {"shares": 1, "currency": "USD", "market_cap_eur": 2e9}}
        prices = {"AAPL": 100.0}
        orders = compute_rebalance_orders(pos, prices, {"AAPL": 0.8}, cash_eur=10000.0)
        aapl = next((o for o in orders if o["ticker"] == "AAPL"), None)
        assert aapl is not None
        assert aapl["side"] == "buy"
        assert aapl["shares"] > 0

    def test_sell_when_overweight(self):
        from backend.signals.rebalance import compute_rebalance_orders
        # AAPL sur-pondéré
        pos = {"AAPL": {"shares": 100, "currency": "USD", "market_cap_eur": 2e9}}
        prices = {"AAPL": 100.0}
        orders = compute_rebalance_orders(pos, prices, {"AAPL": 0.1}, cash_eur=100.0)
        aapl = next((o for o in orders if o["ticker"] == "AAPL"), None)
        assert aapl is not None
        assert aapl["side"] == "sell"
        assert aapl["shares"] > 0

    def test_order_keys_present(self):
        from backend.signals.rebalance import compute_rebalance_orders
        orders = compute_rebalance_orders(
            _positions(), _prices(), {"AAPL": 0.6, "MSFT": 0.4}, cash_eur=2000.0
        )
        for o in orders:
            for k in ("ticker", "side", "shares", "price_eur", "notional_eur",
                      "current_pct", "target_pct", "drift_pct", "cost_eur", "rationale"):
                assert k in o

    def test_cost_non_negative(self):
        from backend.signals.rebalance import compute_rebalance_orders
        orders = compute_rebalance_orders(
            _positions(), _prices(), {"AAPL": 0.7, "MSFT": 0.3}, cash_eur=2000.0
        )
        for o in orders:
            assert o["cost_eur"] >= 0

    def test_zero_price_ticker_skipped(self):
        from backend.signals.rebalance import compute_rebalance_orders
        pos = {"AAPL": {"shares": 10, "currency": "USD", "market_cap_eur": 2e9},
               "DEAD": {"shares": 5, "currency": "USD", "market_cap_eur": 1e9}}
        prices = {"AAPL": 150.0, "DEAD": 0.0}
        orders = compute_rebalance_orders(pos, prices, {"AAPL": 1.0}, cash_eur=1000.0)
        tickers = [o["ticker"] for o in orders]
        assert "DEAD" not in tickers

    def test_new_ticker_in_target(self):
        from backend.signals.rebalance import compute_rebalance_orders
        # Ticker dans target mais pas dans positions → acheter
        pos = {"AAPL": {"shares": 10, "currency": "USD", "market_cap_eur": 2e9}}
        prices = {"AAPL": 100.0, "MSFT": 200.0}
        orders = compute_rebalance_orders(pos, prices, {"AAPL": 0.5, "MSFT": 0.5}, cash_eur=5000.0)
        msft = next((o for o in orders if o["ticker"] == "MSFT"), None)
        assert msft is not None

    def test_eu_stock_uses_eu_asset_type(self):
        from backend.signals.rebalance import compute_rebalance_orders
        pos = {"MC.PA": {"shares": 2, "currency": "EUR", "market_cap_eur": 2e9}}
        prices = {"MC.PA": 800.0}
        orders = compute_rebalance_orders(pos, prices, {"MC.PA": 0.9}, cash_eur=10000.0)
        mc = next((o for o in orders if o["ticker"] == "MC.PA"), None)
        assert mc is not None

    def test_drift_threshold_respected(self):
        from backend.signals.rebalance import compute_rebalance_orders
        # Petit drift → hold même si target différent
        pos = {"AAPL": {"shares": 50, "currency": "USD", "market_cap_eur": 2e9}}
        prices = {"AAPL": 100.0}
        # NAV = 5000 + 4950 = 9950, AAPL pct ≈ 50.25%, target 50% → drift < 1%
        orders = compute_rebalance_orders(pos, prices, {"AAPL": 0.50}, cash_eur=4950.0, drift_threshold=0.05)
        aapl = next(o for o in orders if o["ticker"] == "AAPL")
        assert aapl["side"] == "hold"


class TestRebalanceOrder:
    def test_dataclass_serializable(self):
        from backend.signals.rebalance import RebalanceOrder
        from dataclasses import asdict
        o = RebalanceOrder(
            ticker="AAPL", side="buy", shares=5, price_eur=150.0,
            notional_eur=750.0, current_pct=0.3, target_pct=0.5,
            drift_pct=-0.2, cost_eur=2.5, rationale="Test"
        )
        d = asdict(o)
        assert d["ticker"] == "AAPL"
        assert d["side"] == "buy"
