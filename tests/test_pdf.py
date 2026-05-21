"""
:file: tests/test_pdf.py
:brief: PDF generation tests — ensures generate_pdf runs without exceptions
        and returns valid bytes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

reportlab = pytest.importorskip("reportlab", reason="reportlab not installed")


def _minimal_tearsheet() -> dict:
    """Minimal tearsheet that satisfies generate_pdf."""
    return {
        "meta": {
            "strategy": "buy_hold",
            "period": "1y",
            "tickers": ["AAPL"],
            "start": "2023-01-01",
            "end": "2024-01-01",
            "broker": "degiro",
            "account_type": "CTO",
            "benchmark": "^GSPC",
        },
        "metrics": {
            "total_return": 0.12,
            "cagr": 0.12,
            "annualised_vol": 0.15,
            "sharpe": 0.8,
            "sortino": 1.1,
            "max_drawdown": -0.08,
            "calmar": 1.5,
            "var_95": -0.02,
            "cvar_95": -0.03,
            "hit_rate": 0.55,
            "profit_factor": 1.3,
            "beta": 0.9,
            "alpha": 0.01,
            "skewness": 0.1,
            "kurtosis": 3.0,
            "omega": 1.2,
        },
        "significance": {
            "sharpe_tstat": 2.1,
            "sharpe_pvalue": 0.03,
            "significant": True,
        },
        "stress_tests": [
            {"name": "Covid crash", "return": -0.15},
            {"name": "2022 bear", "return": -0.10},
        ],
        "cost_summary": {
            "total_costs": 120.0,
            "commission": 80.0,
            "slippage": 30.0,
            "taxes": 10.0,
        },
        "cost_breakdown": {},
        "nav_chart": [{"date": "2023-01-01", "nav": 10000}, {"date": "2024-01-01", "nav": 11200}],
        "benchmark_chart": [{"date": "2023-01-01", "nav": 10000}, {"date": "2024-01-01", "nav": 10800}],
        "drawdown_chart": [{"date": "2023-01-01", "dd": 0.0}, {"date": "2024-01-01", "dd": -0.05}],
        "cost_chart": [],
        "allocation_chart": [{"ticker": "AAPL", "weight": 1.0}],
        "positions": {"AAPL": {"shares": 10, "avg_cost": 150.0, "current_price": 170.0}},
    }


class TestGeneratePDF:
    def test_generate_pdf_returns_bytes(self):
        from backend.report.pdf import generate_pdf
        pdf_bytes = generate_pdf(_minimal_tearsheet())
        assert isinstance(pdf_bytes, bytes)

    def test_generate_pdf_non_empty(self):
        from backend.report.pdf import generate_pdf
        pdf_bytes = generate_pdf(_minimal_tearsheet())
        assert len(pdf_bytes) > 1000

    def test_generate_pdf_starts_with_pdf_magic(self):
        from backend.report.pdf import generate_pdf
        pdf_bytes = generate_pdf(_minimal_tearsheet())
        assert pdf_bytes[:4] == b"%PDF"

    def test_generate_pdf_m_defined_before_use(self):
        """Regression test: UnboundLocalError on 'm' variable (fixed 2026-05-21)."""
        from backend.report.pdf import generate_pdf
        # Should not raise UnboundLocalError
        try:
            generate_pdf(_minimal_tearsheet())
        except UnboundLocalError as e:
            pytest.fail(f"UnboundLocalError regression: {e}")
