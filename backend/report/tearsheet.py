"""
:file: api/report/tearsheet.py
:brief: Build a structured tearsheet dict consumed by both the PDF renderer
        and the frontend.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from backend.backtest.engine import BacktestResult
from backend.backtest.stress import run_stress_tests
from backend.config import COPYRIGHT, DISCLAIMER, RISK_FREE_RATE
from backend.quant.metrics import all_metrics
from backend.quant.significance import alpha_ttest, bootstrap_ci, jobson_korkie


def build_tearsheet(
    result: BacktestResult,
    benchmark_returns: pd.Series | None = None,
    strategy_label: str | None = None,
) -> dict:
    r = result.returns_series.values
    nav = result.nav_series

    bench = benchmark_returns.values if benchmark_returns is not None else None
    metrics = all_metrics(r, benchmark_r=bench, rf=RISK_FREE_RATE)

    # Significance tests
    sig: dict = {}
    if bench is not None and len(bench) >= 30:
        n = min(len(r), len(bench))
        jk = jobson_korkie(r[:n], bench[:n])
        at = alpha_ttest(r[:n], bench[:n])
        sb = bootstrap_ci(
            r,
            lambda x: float(np.mean(x) / (np.std(x, ddof=1) + 1e-9) * np.sqrt(252)),
        )
        sig = {
            "jobson_korkie": {"z": jk.statistic, "p": jk.p_value, "significant": jk.significant},
            "alpha_ttest": {"t": at.statistic, "p": at.p_value, "significant": at.significant},
            "sharpe_bootstrap_95ci": [sb.ci_lower, sb.ci_upper],
        }

    # Stress tests
    stress = run_stress_tests(result.returns_series, benchmark_returns)

    # NAV chart (monthly sampled to keep payload light)
    nav_monthly = nav.resample("ME").last()
    nav_chart = [{"date": str(idx.date()), "nav": float(v)} for idx, v in nav_monthly.items()]

    # Benchmark NAV chart
    benchmark_chart = []
    if result.benchmark_nav is not None and not result.benchmark_nav.empty:
        bn = result.benchmark_nav.resample("ME").last()
        benchmark_chart = [{"date": str(idx.date()), "nav": float(v)} for idx, v in bn.items()]

    # Drawdown chart
    dd_chart = [
        {"date": str(idx.date()), "drawdown": float(v)}
        for idx, v in result.drawdown_series.resample("ME").min().items()
    ]

    # COST CHART — cumulative costs + taxes over time
    cost_chart = []
    if not result.costs_series.empty:
        cs = result.costs_series.resample("ME").last()
        cost_chart = [
            {
                "date": str(idx.date()),
                "costs": float(row["costs_eur"]),
                "taxes": float(row["taxes_eur"]),
                "total": float(row["costs_eur"] + row["taxes_eur"]),
            }
            for idx, row in cs.iterrows()
        ]

    # Cash vs invested
    allocation_chart = []
    if not result.cash_invested.empty:
        ci = result.cash_invested.resample("ME").last()
        allocation_chart = [
            {
                "date": str(idx.date()),
                "cash": float(row["cash_eur"]),
                "invested": float(row["invested_eur"]),
            }
            for idx, row in ci.iterrows()
        ]

    # Trade cost breakdown
    cost_breakdown = {"commission": 0.0, "slippage": 0.0, "fx_spread": 0.0, "ttf": 0.0}
    if not result.trades_df.empty:
        td = result.trades_df
        cost_breakdown = {
            "commission": float(td["commission"].sum()),
            "slippage": float(td["slippage"].sum()),
            "fx_spread": float(td["fx_spread"].sum() if "fx_spread" in td.columns else 0.0),
            "ttf": float(td["ttf"].sum()),
        }

    return {
        "meta": {
            "strategy": strategy_label or result.strategy_name,
            "generated_at": date.today().isoformat(),
            "copyright": COPYRIGHT,
            "disclaimer": DISCLAIMER,
        },
        "metrics": metrics,
        "significance": sig,
        "stress_tests": stress,
        "cost_summary": result.cost_summary,
        "cost_breakdown": cost_breakdown,
        "trades": {
            "count": len(result.trades_df),
            "sample": (
                result.trades_df.head(20).to_dict("records") if not result.trades_df.empty else []
            ),
        },
        "nav_chart": nav_chart,
        "benchmark_chart": benchmark_chart,
        "drawdown_chart": dd_chart,
        "cost_chart": cost_chart,
        "allocation_chart": allocation_chart,
        "positions": result.positions_final,
    }
