"""
:file: api/backtest/stress.py
:brief: Stress testing — isolate strategy performance during historical crises.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import pandas as pd

from backend.config import STRESS_SCENARIOS
from backend.quant.metrics import all_metrics


def run_stress_tests(
    returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
) -> list[dict]:
    """Run all defined stress scenarios on a returns series.

    :param returns: daily returns (DatetimeIndex)
    :returns: list of stress-test result dicts
    """
    results = []
    for key, scenario in STRESS_SCENARIOS.items():
        start = scenario["start"]
        end = scenario["end"]
        label = scenario["label"]

        window = returns[start:end]
        if len(window) < 5:
            results.append(
                {
                    "scenario": key,
                    "label": label,
                    "n_days": 0,
                    "message": "No data for this scenario",
                }
            )
            continue

        metrics = all_metrics(window.values)
        bench_metrics = None
        if benchmark_returns is not None:
            bw = benchmark_returns[start:end]
            if len(bw) >= 5:
                bench_metrics = all_metrics(bw.values)

        results.append(
            {
                "scenario": key,
                "label": label,
                "start": start,
                "end": end,
                "n_days": len(window),
                "total_return": metrics["total_return"],
                "max_drawdown": metrics["max_drawdown"],
                "volatility": metrics["annualised_volatility"],
                "var_95": metrics["var_95"],
                "sharpe": metrics["sharpe_ratio"],
                "benchmark": (
                    {
                        "total_return": bench_metrics["total_return"] if bench_metrics else None,
                        "max_drawdown": bench_metrics["max_drawdown"] if bench_metrics else None,
                    }
                    if bench_metrics
                    else None
                ),
            }
        )

    return results
