"""
:file: tests/test_screening.py
:brief: Tests for ethical and sharia screening logic — pure functions.
"""

from __future__ import annotations

import pytest
from backend.core.registry import run_ethical_screen, run_sharia_screen

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# Ethical screen
# ─────────────────────────────────────────────────────────────────────────────


class TestEthicalScreen:
    def test_clean_company_passes(self):
        info = {
            "ticker": "AAPL",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 3e12,
            "total_debt": 100e9,
            "total_revenue": 400e9,
            "interest_expense": 3e9,
        }
        r = run_ethical_screen(info)
        assert r.passed is True
        assert r.score > 0

    def test_weapons_company_fails(self):
        info = {
            "ticker": "LMT",
            "sector": "Industrials",
            "industry": "Aerospace & Defense",
            "market_cap": 100e9,
        }
        r = run_ethical_screen(info)
        assert r.passed is False
        assert r.score == 0.0

    def test_tobacco_company_fails(self):
        info = {
            "ticker": "MO",
            "sector": "Consumer Defensive",
            "industry": "Tobacco",
            "market_cap": 80e9,
        }
        r = run_ethical_screen(info)
        assert r.passed is False

    def test_checks_returned_have_descriptions(self):
        info = {"ticker": "AAPL", "sector": "Tech", "market_cap": 1e12}
        r = run_ethical_screen(info)
        for c in r.checks:
            assert c.description, f"Empty description for check: {c.name}"


# ─────────────────────────────────────────────────────────────────────────────
# Sharia screen
# ─────────────────────────────────────────────────────────────────────────────


class TestShariaScreen:
    def test_clean_tech_company_passes(self):
        """Tech company with low debt should pass all 4 criteria."""
        info = {
            "ticker": "AAPL",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 3e12,
            "total_debt": 100e9,  # ratio = 3 %
            "total_cash": 50e9,  # ratio = 1.7 %
            "total_revenue": 400e9,
            "interest_expense": 2e9,  # ratio = 0.5 %
        }
        r = run_sharia_screen(info)
        assert r.passed is True
        assert r.score == 1.0

    def test_bank_fails_sector(self):
        info = {
            "ticker": "JPM",
            "sector": "Financial Services",
            "industry": "Banks - Diversified",
            "market_cap": 500e9,
            "total_debt": 100e9,
        }
        r = run_sharia_screen(info)
        assert r.passed is False
        # The sector check should specifically be the failed one
        sector_check = next(c for c in r.checks if "Activité" in c.name)
        assert sector_check.passed is False

    def test_high_debt_company_fails(self):
        info = {
            "ticker": "X",
            "sector": "Technology",
            "industry": "Software",
            "market_cap": 1e9,
            "total_debt": 800e6,  # 80 % debt ratio
        }
        r = run_sharia_screen(info)
        assert r.passed is False
        debt_check = next(c for c in r.checks if "dette" in c.name.lower())
        assert debt_check.passed is False

    def test_alcohol_fails(self):
        info = {
            "ticker": "BUD",
            "sector": "Consumer Defensive",
            "industry": "Beverages Alcoholic",
            "market_cap": 100e9,
        }
        r = run_sharia_screen(info)
        assert r.passed is False

    def test_score_proportional_to_passed_checks(self):
        """Score should equal #passed / total."""
        info = {
            "ticker": "PARTIAL",
            "sector": "Technology",
            "industry": "Software",
            "market_cap": 1e9,
            "total_debt": 800e6,  # fails
            "total_cash": 0,  # passes
            "total_revenue": 100e6,
            "interest_expense": 1e6,  # 1 % — passes
        }
        r = run_sharia_screen(info)
        n_passed = sum(1 for c in r.checks if c.passed)
        assert r.score == n_passed / len(r.checks)

    def test_returns_4_checks(self):
        info = {"ticker": "T", "sector": "Tech", "market_cap": 1e9}
        r = run_sharia_screen(info)
        assert len(r.checks) == 4
