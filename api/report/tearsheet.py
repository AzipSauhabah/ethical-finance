"""
:file: api/report/tearsheet.py
:brief: Produces a structured tearsheet dict for a single strategy result.

        The tearsheet is JSON-serialisable and consumed by both the PDF
        renderer and the frontend dashboard.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from api.backtest.engine import BacktestResult
from api.backtest.stress import run_stress_tests
from api.config import COPYRIGHT, DISCLAIMER, RISK_FREE_RATE
from api.quant.metrics import all_metrics
from api.quant.significance import alpha_ttest, bootstrap_ci, jobson_korkie


def build_tearsheet(
    result: BacktestResult,
    benchmark_returns: pd.Series | None = None,
    strategy_label: str | None = None,
) -> dict:
    """Build a full tearsheet for a single strategy.

    :param result:            output of BacktestEngine.run()
    :param benchmark_returns: benchmark daily returns (optional)
    :param strategy_label:    display name override
    :returns: nested dict ready for JSON / PDF rendering
    """
    r   = result.returns_series.values
    nav = result.nav_series

    # Core metrics
    bench = benchmark_returns.values if benchmark_returns is not None else None
    metrics = all_metrics(r, benchmark_r=bench, rf=RISK_FREE_RATE)

    # Statistical significance
    sig: dict = {}
    if bench is not None and len(bench) >= 30:
        n   = min(len(r), len(bench))
        jk  = jobson_korkie(r, bench)
        at  = alpha_ttest(r, bench)
        sr_boot = bootstrap_ci(
            r, lambda x: float(np.mean(x) / (np.std(x, ddof=1) + 1e-9) * np.sqrt(252))
        )
        sig = {
            "jobson_korkie": {"z": jk.statistic, "p": jk.p_value, "significant": jk.significant},
            "alpha_ttest":   {"t": at.statistic,  "p": at.p_value,  "significant": at.significant},
            "sharpe_bootstrap_95ci": [sr_boot.ci_lower, sr_boot.ci_upper],
        }

    # Stress tests
    stress = run_stress_tests(
        result.returns_series,
        benchmark_returns,
    )

    # NAV chart data (monthly sampling for readability)
    nav_monthly = nav.resample("ME").last()
    nav_data = [
        {"date": str(idx.date()), "nav": float(v)}
        for idx, v in nav_monthly.items()
    ]

    # Drawdown chart
    dd_data = [
        {"date": str(idx.date()), "drawdown": float(v)}
        for idx, v in result.drawdown_series.resample("ME").min().items()
    ]

    return {
        "meta": {
            "strategy":      strategy_label or result.strategy_name,
            "generated_at":  date.today().isoformat(),
            "copyright":     COPYRIGHT,
            "disclaimer":    DISCLAIMER,
        },
        "metrics":    metrics,
        "significance": sig,
        "stress_tests": stress,
        "cost_summary": result.cost_summary,
        "trades": {
            "count":      len(result.trades_df),
            "sample":     result.trades_df.head(10).to_dict("records") if not result.trades_df.empty else [],
        },
        "nav_chart":      nav_data,
        "drawdown_chart": dd_data,
        "positions":      result.positions_final,
    }
