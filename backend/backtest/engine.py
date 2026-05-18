"""
:file: api/backtest/engine.py
:brief: STRICT event-driven backtest engine.

        Loop semantics:
        ────────────────
        For each trading bar ``dt`` in price index:
            1. Compute prices_eur from native + FX rates.
            2. Apply stop-loss using TODAY's close (path-dependent).
            3. Check rebalance schedule.
            4. If rebalance day: call ``strategy.on_bar(dt, past_prices[:dt],
               params, state)`` — strategy sees ONLY past data including dt.
            5. Convert target weights to integer share orders, respecting:
                * Integer share sizing
                * Cash > 0 constraint
                * max_position_pct cap
                * Broker fees + slippage + TTF
            6. Execute orders at dt's close.
            7. Snapshot NAV + cumulative costs.

        No look-ahead is mechanically possible — the strategy receives a
        slice of the price DataFrame that ends at ``dt``.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.backtest.costs import cap_size_from_market_cap, country_from_ticker
from backend.backtest.portfolio import Portfolio
from backend.quant.metrics import all_metrics, drawdown_series
from backend.strategies.base import Strategy, StrategyParams

log = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    strategy_name: str
    nav_series: pd.Series
    returns_series: pd.Series
    drawdown_series: pd.Series
    costs_series: pd.DataFrame  # cumulative costs/taxes over time
    cash_invested: pd.DataFrame  # cash vs invested over time
    metrics: dict
    trades_df: pd.DataFrame
    cost_summary: dict
    positions_final: dict
    benchmark_nav: pd.Series | None = None  # for comparison chart


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _fx_convert(
    prices_native: dict[str, float],
    currencies: dict[str, str],
    fx_rates: dict[str, float],
) -> dict[str, float]:
    result = {}
    for t, p in prices_native.items():
        ccy = currencies.get(t, "USD")
        if ccy == "EUR":
            result[t] = p
        else:
            rate = fx_rates.get(f"{ccy}EUR", 1.0 / max(fx_rates.get(f"EUR{ccy}", 1.0), 1e-9))
            result[t] = p * rate
    return result


def _target_shares(
    weight: float, nav_eur: float, price_eur: float, cap: float, allow_fractional: bool = False
) -> float:
    """Calcule le nombre d'actions cible.

    - Fortuneo / Boursorama / default : actions entières uniquement (floor)
    - Revolut : fractions permises (allow_fractional=True)
    """
    if not price_eur or price_eur <= 0 or price_eur != price_eur:
        return 0
    capped = min(weight, cap)
    raw = (nav_eur * capped) / price_eur
    return raw if allow_fractional else int(raw)  # floor implicite via int()


def _rebalance_dates(idx: pd.DatetimeIndex, freq: str) -> set:
    if freq == "daily":
        return set(idx)
    if freq == "weekly":
        return set(idx[idx.day_of_week == 4])
    if freq == "monthly":
        return set(idx[idx.is_month_end])
    if freq == "quarterly":
        return set(idx[idx.month.isin([3, 6, 9, 12]) & idx.is_month_end])
    return set(idx[idx.is_month_end])


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────


class BacktestEngine:
    """Strict event-driven backtester.

    :param strategy:   Strategy instance
    :param prices:     DataFrame[date, ticker] of adjusted closes (native ccy)
    :param currencies: ticker → ISO currency
    :param fx_rates:   '{FROM}{TO}' → rate, e.g. {'USDEUR': 0.92}
    :param params:     StrategyParams
    :param benchmark_prices: optional benchmark price series
    """

    def __init__(
        self,
        strategy: Strategy,
        prices: pd.DataFrame,
        currencies: dict[str, str] | None = None,
        fx_rates: dict[str, float] | None = None,
        params: StrategyParams | None = None,
        benchmark_prices: pd.Series | None = None,
    ) -> None:
        self.strategy = strategy
        self.prices = prices.sort_index()
        self.currencies = currencies or {t: "USD" for t in prices.columns}
        self.fx_rates = fx_rates or {"USDEUR": 0.92, "EURUSD": 1.087}
        self.params = params or StrategyParams()
        self.benchmark_prices = benchmark_prices

    # ── Main loop ────────────────────────────────────────────────────────

    def run(self) -> BacktestResult:
        params = self.params
        prices = self.prices

        portfolio = Portfolio(
            initial_capital=params.initial_capital,
            broker=params.broker,
            account_type=params.account_type,
        )

        # Strategy state — opaque dict reused across all on_bar calls
        state: dict = {}

        rebalance_days = _rebalance_dates(prices.index, params.rebalance_frequency)

        # Track months for monthly contributions
        last_contribution_month: int | None = None

        log.info(
            "Running event-driven backtest for strategy '%s'  (%d bars)",
            self.strategy.name,
            len(prices),
        )

        for ts in prices.index:
            dt = ts.date() if hasattr(ts, "date") else ts
            row_native = prices.loc[ts].to_dict()
            # Taux FX historique du jour si disponible
            fx_today = dict(self.fx_rates)
            eurusd = row_native.pop("EURUSD=X", None)
            if eurusd and eurusd > 0:
                fx_today["USDEUR"] = 1.0 / eurusd
                fx_today["EURUSD"] = eurusd
            prices_eur = _fx_convert(row_native, self.currencies, fx_today)

            # ── Monthly contribution (first trading day of month) ─────────
            cur_month = ts.month
            if last_contribution_month != cur_month and params.monthly_contribution > 0:
                portfolio.cash += params.monthly_contribution
                last_contribution_month = cur_month

            # ── Stop-loss on today's close (path-dependent) ───────────────
            if params.stop_loss_pct is not None:
                self._apply_stop_loss(portfolio, dt, prices_eur, params.stop_loss_pct)

            # ── Rebalance: ask strategy for target weights ────────────────
            if ts in rebalance_days and len(prices.loc[:ts]) >= self.strategy.requires_warmup_days:
                past_view = prices.loc[:ts]  # IMPORTANT: only past + current bar
                try:
                    target_weights = self.strategy.on_bar(dt, past_view, params, state)
                except Exception as exc:
                    log.warning("on_bar error at %s: %s", dt, exc)
                    target_weights = {}
                if target_weights:
                    self._execute_rebalance(
                        portfolio, dt, prices_eur, target_weights, params, past_prices=past_view
                    )

            # ── Snapshot ─────────────────────────────────────────────────
            portfolio.snapshot(dt, prices_eur)

        # ── Assemble result ──────────────────────────────────────────────
        nav = portfolio.nav_series()
        rets = nav.pct_change(fill_method=None).dropna()
        dd = pd.Series(drawdown_series(rets.values), index=rets.index)

        last_prices = {t: prices[t].iloc[-1] for t in prices.columns}
        last_eur = _fx_convert(last_prices, self.currencies, self.fx_rates)
        metrics = all_metrics(rets.values)

        bench_nav = None
        if self.benchmark_prices is not None and not self.benchmark_prices.empty:
            bp = self.benchmark_prices.dropna()
            bench_nav = (bp / bp.iloc[0]) * params.initial_capital

        return BacktestResult(
            strategy_name=self.strategy.name,
            nav_series=nav,
            returns_series=rets,
            drawdown_series=dd,
            costs_series=portfolio.costs_series(),
            cash_invested=portfolio.cash_invested_series(),
            metrics=metrics,
            trades_df=portfolio.trades_df(),
            cost_summary={
                "total_costs_eur": portfolio._total_costs,
                "total_taxes_eur": portfolio._total_taxes,
                "cost_pct_nav": portfolio._total_costs / max(params.initial_capital, 1.0),
            },
            positions_final=portfolio.summary(last_eur),
            benchmark_nav=bench_nav,
        )

    # ── Order execution ──────────────────────────────────────────────────

    def _execute_rebalance(
        self,
        portfolio: Portfolio,
        dt: date,
        prices_eur: dict[str, float],
        target_weights: dict[str, float],
        params: StrategyParams,
        past_prices=None,
    ) -> None:
        nav = portfolio.market_value(prices_eur)
        if nav <= 0:
            return

        # 1) SELL first to free up cash, in order: tickers absent or
        #    over-weighted vs target
        for ticker, pos in list(portfolio._positions.items()):
            if pos.shares == 0:
                continue
            price = prices_eur.get(ticker, 0.0)
            if price <= 0:
                continue
            target_w = target_weights.get(ticker, 0.0)
            target_v = target_w * nav
            current_v = pos.shares * price

            if current_v > target_v:
                excess_v = current_v - target_v
                shares_to_sell = int(excess_v // price)
                if shares_to_sell > 0:
                    portfolio.sell(
                        dt,
                        ticker,
                        shares_to_sell,
                        price,
                        self.currencies.get(ticker, "USD"),
                        cap_size=cap_size_from_market_cap(
                            self.params.custom.get("market_caps", {}).get(ticker, 2_000_000_000)
                        ),
                        country=country_from_ticker(ticker),
                    )

        # 2) BUY under-weighted tickers
        for ticker, target_w in target_weights.items():
            price = prices_eur.get(ticker, 0.0)
            if price <= 0:
                continue

            # Contrainte VaR : si activee et VaR journaliere > 5%, reduit le poids de 50%
            if (
                params.use_var_constraint
                and past_prices is not None
                and ticker in past_prices.columns
            ):
                rets = past_prices[ticker].pct_change(fill_method=None).dropna()
                if len(rets) >= 20:
                    var_95 = float(rets.quantile(0.05))
                    if var_95 < -0.05:  # VaR > 5% par jour
                        target_w = target_w * 0.5
                        log.debug(
                            "VaR constraint applied to %s: weight reduced to %.2f", ticker, target_w
                        )

            pos = portfolio._positions.get(ticker)
            cur_shares = pos.shares if pos else 0
            target_shares = _target_shares(
                target_w,
                portfolio.market_value(prices_eur, allow_fractional=params.allow_fractional),
                price,
                params.max_position_pct,
            )
            diff = target_shares - cur_shares
            if diff > 0:
                _country = country_from_ticker(ticker)
                _cap = cap_size_from_market_cap(
                    self.params.custom.get("market_caps", {}).get(ticker, 2_000_000_000)
                )
                portfolio.buy(
                    dt,
                    ticker,
                    diff,
                    price,
                    self.currencies.get(ticker, "USD"),
                    cap_size=_cap,
                    country=_country,
                )

    def _apply_stop_loss(
        self,
        portfolio: Portfolio,
        dt: date,
        prices_eur: dict[str, float],
        stop_pct: float,
    ) -> None:
        for ticker, pos in list(portfolio._positions.items()):
            if pos.shares == 0 or pos.avg_cost_eur == 0:
                continue
            current = prices_eur.get(ticker, pos.avg_cost_eur)
            if current < pos.avg_cost_eur * (1 - stop_pct):
                portfolio.sell(
                    dt,
                    ticker,
                    pos.shares,
                    current,
                    self.currencies.get(ticker, "USD"),
                    cap_size=cap_size_from_market_cap(2_000_000_000),
                    country=country_from_ticker(ticker),
                )
