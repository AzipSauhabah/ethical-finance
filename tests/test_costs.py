"""
:file: tests/test_costs.py
:brief: Unit tests for broker fees, slippage, FX spread, and French taxes.
"""

from __future__ import annotations

import math

import pytest

from backend.backtest.costs import (
    broker_commission,
    capital_gains_tax,
    fx_spread_cost,
    slippage_cost,
    total_trade_cost,
    ttf_tax,
)

pytestmark = pytest.mark.unit


class TestBrokerCommissions:
    def test_degiro_eu_small_trade(self):
        # Degiro EU: 0.50 € + 0.04 %
        fee = broker_commission(1_000, broker="degiro", asset_type="stock_eu")
        assert math.isclose(fee, 0.50 + 1_000 * 0.0004, rel_tol=1e-9)

    def test_fortuneo_us_under_threshold(self):
        """Below 7 500 USD threshold → 50 USD flat."""
        fee = broker_commission(5_000, broker="fortuneo", asset_type="stock_us")
        assert math.isclose(fee, 50.0)

    def test_fortuneo_us_above_threshold(self):
        """Above 7 500 USD → 0.20 % + 9 USD."""
        fee = broker_commission(10_000, broker="fortuneo", asset_type="stock_us")
        # 10 000 * 0.002 + 9 = 29 USD
        assert math.isclose(fee, 10_000 * 0.002 + 9.0, rel_tol=1e-9)

    def test_min_fee_floor_respected(self):
        """Very tiny trades should still trigger min_fee."""
        fee = broker_commission(10, broker="degiro", asset_type="stock_eu")
        assert fee >= 0.50

    def test_ibkr_cap_respected(self):
        """IBKR caps at 1 USD."""
        fee = broker_commission(100_000, broker="interactive_brokers", asset_type="stock_us")
        assert fee <= 1.0


class TestSlippage:
    def test_slippage_scales_with_notional(self):
        s1 = slippage_cost(1_000, cap_size="mid_cap")
        s2 = slippage_cost(10_000, cap_size="mid_cap")
        assert math.isclose(s2, 10 * s1, rel_tol=1e-9)

    def test_small_cap_slippage_higher_than_large_cap(self):
        s_small = slippage_cost(1_000, cap_size="small_cap")
        s_large = slippage_cost(1_000, cap_size="large_cap")
        assert s_small > s_large


class TestFXSpread:
    def test_no_fx_cost_for_eur(self):
        assert fx_spread_cost(1_000, currency="EUR") == 0.0

    def test_usd_fx_cost_positive(self):
        assert fx_spread_cost(1_000, currency="USD") > 0


class TestTTF:
    def test_ttf_applied_above_threshold(self):
        # > 1 Bn EUR market cap
        tax = ttf_tax(10_000, market_cap_eur=2e9)
        assert math.isclose(tax, 10_000 * 0.001, rel_tol=1e-9)

    def test_ttf_not_applied_below_threshold(self):
        tax = ttf_tax(10_000, market_cap_eur=500e6)
        assert tax == 0.0


class TestCapitalGainsTax:
    def test_no_tax_on_loss(self):
        assert capital_gains_tax(-1000) == 0.0

    def test_cto_pfu_30_percent(self):
        # PFU = 30 % flat
        tax = capital_gains_tax(1_000, account_type="CTO")
        assert math.isclose(tax, 300.0, rel_tol=1e-9)

    def test_pea_after_5_years_only_social(self):
        """PEA after 5y → only PS 17.2 %."""
        tax = capital_gains_tax(1_000, account_type="PEA", pea_years=5)
        assert math.isclose(tax, 172.0, rel_tol=1e-9)

    def test_pea_before_5_years_full_pfu(self):
        tax = capital_gains_tax(1_000, account_type="PEA", pea_years=2)
        assert math.isclose(tax, 300.0, rel_tol=1e-9)


class TestTotalTradeCost:
    def test_returns_all_keys(self):
        c = total_trade_cost(1_000, broker="degiro")
        for k in ("commission", "slippage", "fx_spread", "ttf", "total", "notional"):
            assert k in c

    def test_total_equals_sum_of_parts(self):
        c = total_trade_cost(10_000, broker="degiro", side="buy")
        manual_total = c["commission"] + c["slippage"] + c["fx_spread"] + c["ttf"]
        assert math.isclose(c["total"], manual_total, rel_tol=1e-9)

    def test_sell_side_no_ttf(self):
        c = total_trade_cost(10_000, broker="degiro", side="sell")
        assert c["ttf"] == 0.0
