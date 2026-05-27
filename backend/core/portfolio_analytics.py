"""
Portfolio Analytics — Sharpe, Sortino, corrélations, risk contribution
Calculs depuis les données OHLCV en DB
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

TRADING_DAYS = 252


def _get_prices(tickers: list[str], engine, days: int = 365) -> pd.DataFrame:
    """Fetch prix ajustés depuis PostgreSQL."""
    import sqlalchemy as sa
    start = date.today() - timedelta(days=days)
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT ticker, date, adj_close
            FROM ohlcv
            WHERE ticker = ANY(:tickers) AND date >= :start AND adj_close > 0
            ORDER BY date ASC
        """), {"tickers": tickers, "start": str(start)}).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ticker", "date", "price"])
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot(index="date", columns="ticker", values="price")


def compute_portfolio_analytics(
    positions: dict[str, dict],  # {ticker: {qty, avg_price, last_price}}
    engine,
    days: int = 365,
) -> dict[str, Any]:
    """
    Calcule les métriques analytiques du portefeuille réel.
    positions: {ticker: {qty, avg_price, last_price, currency}}
    """
    tickers = list(positions.keys())
    if not tickers:
        return {"error": "Portefeuille vide"}

    # Prix historiques
    prices = _get_prices(tickers, engine, days)
    if prices.empty or len(prices) < 30:
        return {"error": "Données insuffisantes (< 30 jours)"}

    # Poids selon valeur de marché
    weights = {}
    total_value = 0.0
    for t, pos in positions.items():
        if t in prices.columns:
            val = pos.get("qty", 0) * pos.get("last_price", 0)
            weights[t] = val
            total_value += val

    if total_value <= 0:
        # Poids égaux si pas de valeur
        weights = {t: 1.0 for t in tickers if t in prices.columns}
        total_value = len(weights)

    tickers_available = [t for t in tickers if t in prices.columns]
    w = np.array([weights.get(t, 0) / total_value for t in tickers_available])
    prices_clean = prices[tickers_available].dropna()

    if len(prices_clean) < 30:
        return {"error": "Données insuffisantes après nettoyage"}

    # Rendements journaliers
    rets = prices_clean.pct_change().dropna()

    # ── Métriques portefeuille ─────────────────────────────────────────────
    port_rets = rets @ w
    mean_ret = port_rets.mean()
    std_ret = port_rets.std()

    sharpe = (mean_ret / std_ret * np.sqrt(TRADING_DAYS)) if std_ret > 0 else 0
    downside = port_rets[port_rets < 0].std()
    sortino = (mean_ret / downside * np.sqrt(TRADING_DAYS)) if downside > 0 else 0

    # Max drawdown
    cum = (1 + port_rets).cumprod()
    roll_max = cum.cummax()
    drawdown = (cum - roll_max) / roll_max
    max_dd = float(drawdown.min())

    # Annualized return
    n_days = len(port_rets)
    ann_ret = (1 + mean_ret) ** TRADING_DAYS - 1

    # ── Matrice corrélations ───────────────────────────────────────────────
    corr_matrix = rets.corr()

    # ── Risk contribution ──────────────────────────────────────────────────
    cov = rets.cov() * TRADING_DAYS
    port_vol = float(np.sqrt(w @ cov.values @ w))
    marginal_risk = cov.values @ w
    risk_contrib = w * marginal_risk / port_vol if port_vol > 0 else w * 0

    # ── NAV historique ─────────────────────────────────────────────────────
    nav_series = (1 + port_rets).cumprod()
    nav_history = [
        {"date": str(dt.date()), "nav": round(float(v), 4)}
        for dt, v in nav_series.items()
    ][-252:]  # dernière année

    # ── Résultat ───────────────────────────────────────────────────────────
    return {
        "metrics": {
            "sharpe":        round(float(sharpe), 2),
            "sortino":       round(float(sortino), 2),
            "ann_return":    round(float(ann_ret) * 100, 2),
            "ann_volatility": round(float(port_vol) * 100, 2),
            "max_drawdown":  round(float(max_dd) * 100, 2),
            "n_days":        int(n_days),
        },
        "weights": {t: round(float(w[i]) * 100, 1) for i, t in enumerate(tickers_available)},
        "risk_contribution": {
            t: round(float(risk_contrib[i]) * 100, 1)
            for i, t in enumerate(tickers_available)
        },
        "correlations": {
            t: {
                t2: round(float(corr_matrix.loc[t, t2]), 2)
                for t2 in tickers_available
            }
            for t in tickers_available
        },
        "nav_history": nav_history,
        "tickers": tickers_available,
    }
