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
    prices: "pd.DataFrame | None" = None,
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

    # ── Données pour les nouveaux graphiques matplotlib ───────────────────────

    # Monthly returns (pour heatmap)
    monthly_rets = result.returns_series.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    {
        str(idx.year): {str(idx.month): round(float(v) * 100, 2) for idx, v in monthly_rets.items()}
        for idx in monthly_rets.index
    }
    # Format list pour sérialisation
    [
        {"date": str(idx.date()), "return": round(float(v) * 100, 2)}
        for idx, v in monthly_rets.items()
    ]

    # Rolling Sharpe 252j
    r_series = result.returns_series
    if len(r_series) >= 252:
        rs = (
            r_series.rolling(252)
            .apply(lambda x: float(np.mean(x) / (np.std(x, ddof=1) + 1e-9) * np.sqrt(252)))
            .dropna()
        )
        rs_monthly = rs.resample("ME").last()
        [{"date": str(idx.date()), "sharpe": round(float(v), 3)} for idx, v in rs_monthly.items()]

    # Rolling Volatility 63j
    if len(r_series) >= 63:
        rv = r_series.rolling(63).std() * np.sqrt(252) * 100
        rv_monthly = rv.resample("ME").last().dropna()
        [{"date": str(idx.date()), "vol": round(float(v), 2)} for idx, v in rv_monthly.items()]

    # Rolling Beta 252j
    rolling_beta = []
    if benchmark_returns is not None and len(r_series) >= 252:
        bench_aligned = benchmark_returns.reindex(r_series.index).fillna(0)

        def _rolling_beta(window_r, window_b):
            cov = np.cov(window_r, window_b)
            var_b = np.var(window_b, ddof=1)
            return cov[0, 1] / (var_b + 1e-9) if var_b > 0 else 1.0

        for i in range(252, len(r_series), 21):
            window_r = r_series.iloc[i - 252 : i].values
            window_b = bench_aligned.iloc[i - 252 : i].values
            dt = r_series.index[i]
            beta_val = _rolling_beta(window_r, window_b)
            rolling_beta.append({"date": str(dt.date()), "beta": round(float(beta_val), 3)})

    # Return distribution (daily returns en %)
    [round(float(v) * 100, 4) for v in r_series.values if not np.isnan(v)]

    # Win/Loss distribution
    wins = [v * 100 for v in r_series.values if v > 0]
    losses = [v * 100 for v in r_series.values if v < 0]
    {
        "wins": [round(v, 4) for v in wins],
        "losses": [round(v, 4) for v in losses],
        "hit_rate": round(len(wins) / max(len(r_series), 1) * 100, 2),
    }

    # NAV chart (monthly sampled to keep payload light)
    nav_monthly = nav.resample("ME").last()
    nav_chart = [{"date": str(idx.date()), "nav": float(v)} for idx, v in nav_monthly.items()]

    # NAV multi-devises — conversion via paires FX historiques
    nav_multiccy = {"EUR": nav_chart}
    fx_pairs = {
        "USD": "EURUSD=X",
        "GBP": "EURGBP=X",
        "CHF": "EURCHF=X",
        "JPY": "EURJPY=X",
    }
    for ccy, fx_ticker in fx_pairs.items():
        if prices is not None and fx_ticker in prices.columns:
            fx = prices[fx_ticker].dropna().reindex(nav.index, method="ffill")
            nav_ccy = nav * fx
            nav_ccy_monthly = nav_ccy.resample("ME").last()
            nav_multiccy[ccy] = [
                {"date": str(idx.date()), "nav": round(float(v), 2)}
                for idx, v in nav_ccy_monthly.items()
                if not np.isnan(v)
            ]

    # NAV en équivalent OR
    if prices is not None and "GLD" in prices.columns:
        gld = prices["GLD"].dropna().reindex(nav.index, method="ffill")
        eurusd = (
            prices.get("EURUSD=X", pd.Series(dtype=float))
            .dropna()
            .reindex(nav.index, method="ffill")
        )
        if not eurusd.empty:
            nav_usd = nav * eurusd
            nav_gold_oz = nav_usd / gld  # NAV en onces d'or
            nav_gold_monthly = nav_gold_oz.resample("ME").last()
            nav_multiccy["XAU"] = [
                {"date": str(idx.date()), "nav": round(float(v), 4)}
                for idx, v in nav_gold_monthly.items()
                if not np.isnan(v)
            ]

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
    # VaR par position
    risk_by_position = {}
    if not prices.empty and result.positions_final.get("positions"):
        for ticker, pos_info in result.positions_final["positions"].items():
            if ticker in prices.columns:
                ticker_rets = prices[ticker].pct_change(fill_method=None).dropna()
                if len(ticker_rets) > 20:
                    var_95 = float(np.percentile(ticker_rets, 5))
                    cvar_95 = (
                        float(ticker_rets[ticker_rets <= var_95].mean())
                        if len(ticker_rets[ticker_rets <= var_95]) > 0
                        else var_95
                    )
                    weight = pos_info.get("weight", 0)
                    value_eur = pos_info.get("value_eur", 0)
                    risk_by_position[ticker] = {
                        "weight": weight,
                        "value_eur": value_eur,
                        "var_95_daily": var_95,
                        "cvar_95_daily": cvar_95,
                        "var_95_eur": var_95 * value_eur,
                        "contribution_pct": weight * var_95,
                    }

    if not result.trades_df.empty:
        td = result.trades_df
        cost_breakdown = {
            "commission": float(td["commission"].sum()),
            "slippage": float(td["slippage"].sum()),
            "market_impact": float(
                td["market_impact"].sum() if "market_impact" in td.columns else 0.0
            ),
            "fx_spread": float(td["fx_spread"].sum() if "fx_spread" in td.columns else 0.0),
            "ttf": float(td["ttf"].sum() if "ttf" in td.columns else 0.0),
            "stamp_duty": float(td["stamp_duty"].sum() if "stamp_duty" in td.columns else 0.0),
        }

    import math

    def _clean(obj):
        """Remplace inf et NaN par None pour la sérialisation JSON."""
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return obj

    return _clean(
        {
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
            "risk_by_position": risk_by_position,
            "trades": {
                "count": len(result.trades_df),
                "sample": (
                    result.trades_df.to_dict("records") if not result.trades_df.empty else []
                ),
            },
            "nav_chart": nav_chart,
            "benchmark_chart": benchmark_chart,
            "nav_multiccy": nav_multiccy,
            "drawdown_chart": dd_chart,
            "cost_chart": cost_chart,
            "allocation_chart": allocation_chart,
            "positions": result.positions_final,
        }
    )
