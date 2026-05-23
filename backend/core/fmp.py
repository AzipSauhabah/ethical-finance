"""
:file: backend/core/fmp.py
:brief: Client Financial Modeling Prep API — fondamentaux mondiaux.

Plan gratuit : 250 req/jour
Couvre : US, FR, DE, UK, JP, AU, CH, etc.

Endpoints utilisés (nouvelle API /stable/) :
  - /stable/profile          : infos société + market cap + beta
  - /stable/income-statement : compte de résultat (revenue, EBIT, net income)
  - /stable/balance-sheet    : bilan (dette, actifs, capitaux propres)
  - /stable/cash-flow        : flux de trésorerie (FCF, capex)
  - /stable/ratios           : ratios financiers (PE, EV/EBITDA, ROE, ROIC)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com/stable"
RATE_LIMIT_SLEEP = 0.5  # 250 req/jour → on space les requêtes


def _get_api_key() -> str:
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        raise ValueError("FMP_API_KEY non défini dans .env")
    return key


def _get(endpoint: str, params: dict) -> dict | list | None:
    """Requête GET vers FMP avec gestion d'erreurs."""
    try:
        params["apikey"] = _get_api_key()
        r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "Error Message" in data:
            log.warning("FMP error for %s: %s", endpoint, data["Error Message"])
            return None
        return data
    except Exception as e:
        log.warning("FMP request error (%s): %s", endpoint, e)
        return None


# ─── Profile ──────────────────────────────────────────────────────────────────


def fetch_profile(ticker: str) -> dict | None:
    """Récupère le profil complet d'une société."""
    data = _get("profile", {"symbol": ticker})
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    return data[0]


# ─── Fondamentaux complets ────────────────────────────────────────────────────


def _fmp_valuation_ratios(mc: float, ev: float, net_income, ebitda, revenue, equity, fcf) -> dict:
    """Compute FMP valuation ratios."""
    r = {}
    if mc > 0 and net_income and net_income > 0:
        r["pe_ratio"] = round(mc / net_income, 2)
    if ev > 0 and ebitda > 0:
        r["ev_ebitda"] = round(ev / ebitda, 2)
    if ev > 0 and revenue > 0:
        r["ev_revenue"] = round(ev / revenue, 2)
    if mc > 0 and equity > 0:
        r["pb_ratio"] = round(mc / equity, 2)
    if mc > 0 and fcf > 0:
        r["price_fcf"] = round(mc / fcf, 2)
        r["fcf_yield"] = round(fcf / mc, 4)
    return r


def _fmp_profitability_ratios(revenue, net_income, ebit, total_assets, equity) -> dict:
    """Compute FMP profitability ratios."""
    r = {}
    if revenue > 0:
        if net_income:
            r["net_margin"] = round(net_income / revenue, 4)
        if ebit:
            r["operating_margin"] = round(ebit / revenue, 4)
    if total_assets > 0 and net_income:
        r["roa"] = round(net_income / total_assets, 4)
    if equity > 0 and net_income:
        r["roe"] = round(net_income / equity, 4)
    return r


def _fmp_leverage_ratios(total_debt, equity, ebitda, cash, current_assets, current_liabilities) -> dict:
    """Compute FMP leverage and liquidity ratios."""
    r = {}
    if equity > 0:
        r["debt_equity"] = round(total_debt / equity, 2)
    if ebitda > 0:
        r["net_debt_ebitda"] = round((total_debt - cash) / ebitda, 2)
    if current_liabilities > 0:
        r["current_ratio"] = round(current_assets / current_liabilities, 2)
    return r


def _fmp_magic_formula(ev, ebit, total_assets, current_assets, current_liabilities) -> dict:
    """Compute FMP Magic Formula ratios."""
    r = {}
    if ev > 0 and ebit:
        r["earning_yield_fmp"] = round(ebit / ev, 4)
    net_working_capital = current_assets - current_liabilities
    net_fixed_assets = total_assets - current_assets
    invested_capital = net_working_capital + net_fixed_assets
    if invested_capital > 0 and ebit:
        r["roic_fmp"] = round(ebit / invested_capital, 4)
    return r


def _merge_fmp_ratios(computed: dict, ratios: dict) -> dict:
    """Merge FMP API ratios into computed ratios (no overwrite)."""
    keys = {
        "pe_ratio": "priceEarningsRatio",
        "pb_ratio": "priceToBookRatio",
        "ev_ebitda": "enterpriseValueMultiple",
        "roe": "returnOnEquity",
        "roa": "returnOnAssets",
        "roic_fmp": "returnOnCapitalEmployed",
        "net_margin": "netProfitMargin",
        "current_ratio": "currentRatio",
        "debt_equity": "debtEquityRatio",
        "dividend_yield": "dividendYield",
    }
    for k, fmp_key in keys.items():
        v = ratios.get(fmp_key)
        if v is not None and k not in computed:
            try:
                computed[k] = round(float(v), 4)
            except Exception:
                pass
    return computed


def _extract_fmp_metrics(profile: dict, income: dict, balance: dict, cf: dict, market_cap: float) -> dict:
    """Extract and compute key metrics from FMP API responses."""
    mc = float(profile.get("marketCap") or market_cap or 0)
    total_debt            = float(balance.get("totalDebt") or balance.get("longTermDebt") or 0)
    short_term_debt       = float(balance.get("shortTermDebt") or balance.get("shortTermBorrowings") or 0)
    long_term_debt_val    = float(balance.get("longTermDebt") or balance.get("longTermBorrowings") or 0)
    interest_bearing_debt = short_term_debt + long_term_debt_val
    total_assets          = float(balance.get("totalAssets") or 0)
    total_equity          = float(balance.get("totalStockholdersEquity") or balance.get("totalEquity") or 0)
    interest_expense      = float(abs(float(income.get("interestExpense") or income.get("interestAndDebtExpense") or 0)))
    interest_income       = float(abs(float(income.get("interestIncome") or income.get("netInterestIncome") or 0)))
    cash = float(balance.get("cashAndCashEquivalents") or 0)
    ev = mc + total_debt - cash
    revenue = float(income.get("revenue") or 0)
    ebit = float(income.get("operatingIncome") or income.get("ebit") or 0)
    net_income = float(income.get("netIncome") or 0)
    depreciation = float(cf.get("depreciationAndAmortization") or 0)
    ebitda = ebit + depreciation
    capex = abs(float(cf.get("capitalExpenditure") or 0))
    operating_cf = float(cf.get("operatingCashFlow") or 0)
    fcf = operating_cf - capex
    equity = float(balance.get("totalEquity") or balance.get("stockholdersEquity") or 0)
    total_assets = float(balance.get("totalAssets") or 0)
    current_assets = float(balance.get("totalCurrentAssets") or 0)
    current_liabilities = float(balance.get("totalCurrentLiabilities") or 0)
    return dict(
        mc=mc, total_debt=total_debt, cash=cash, ev=ev,
        revenue=revenue, ebit=ebit, net_income=net_income,
        ebitda=ebitda, fcf=fcf, equity=equity,
        total_assets=total_assets, current_assets=current_assets,
        current_liabilities=current_liabilities,
        short_term_debt=short_term_debt,
        long_term_debt=long_term_debt_val,
        interest_bearing_debt=interest_bearing_debt,
        interest_expense=interest_expense,
        interest_income=interest_income,
        total_equity=total_equity,
    )


def fetch_fundamentals_fmp(ticker: str, market_cap: float = 0) -> dict | None:
    """
    Récupère les fondamentaux complets depuis FMP.

    Priorité : FMP pour les actions non-US, SEC EDGAR pour les US.
    Mais FMP fonctionne aussi pour les US en fallback.

    Args:
        ticker: symbole boursier (ex: AAPL, MC.PA, HSBA.L)
        market_cap: market cap en EUR (pour les ratios si FMP ne les fournit pas)

    Returns:
        dict avec raw data + ratios calculés
    """
    # 1. Profile
    profile = fetch_profile(ticker)
    if not profile:
        return None

    # Plan gratuit : uniquement profile disponible
    # income-statement, balance-sheet, cash-flow, ratios → plan payant
    ratios = {}
    income = {}
    balance = {}
    cf = {}

    # ── Extraire les métriques clés ───────────────────────────────────────────
    _m = _extract_fmp_metrics(profile, income, balance, cf, market_cap)
    mc = _m["mc"]; total_debt = _m["total_debt"]; cash = _m["cash"]; ev = _m["ev"]
    short_term_debt       = _m.get("short_term_debt", 0)
    long_term_debt_val    = _m.get("long_term_debt", 0)
    interest_bearing_debt = _m.get("interest_bearing_debt", 0)
    interest_expense      = _m.get("interest_expense", 0)
    interest_income       = _m.get("interest_income", 0)
    total_equity          = _m.get("total_equity", 0)
    revenue = _m["revenue"]; ebit = _m["ebit"]; net_income = _m["net_income"]
    ebitda = _m["ebitda"]; fcf = _m["fcf"]; equity = _m["equity"]
    total_assets = _m["total_assets"]; current_assets = _m["current_assets"]
    current_liabilities = _m["current_liabilities"]

    # ── Ratios calculés ───────────────────────────────────────────────────────
    computed_ratios = {}
    computed_ratios.update(_fmp_valuation_ratios(mc, ev, net_income, ebitda, revenue, equity, fcf))
    computed_ratios.update(_fmp_profitability_ratios(revenue, net_income, ebit, total_assets, equity))
    computed_ratios.update(_fmp_magic_formula(ev, ebit, total_assets, current_assets, current_liabilities))
    computed_ratios.update(_fmp_leverage_ratios(total_debt, equity, ebitda, cash, current_assets, current_liabilities))

    computed_ratios = _merge_fmp_ratios(computed_ratios, ratios)

    # Données de base pour ticker_fundamentals
    return {
        "ticker": ticker,
        "name": profile.get("companyName", ticker),
        "sector": profile.get("sector", ""),
        "industry": profile.get("industry", ""),
        "country": profile.get("country", ""),
        "currency": profile.get("currency", "USD"),
        "exchange": profile.get("exchange", ""),
        "market_cap": int(mc),
        "beta": float(profile.get("beta") or 1.0),
        "dividend_yield": float(profile.get("lastDividend") or 0),
        "total_debt":            int(total_debt),
        "total_revenue":         int(revenue),
        "short_term_debt":       int(short_term_debt),
        "long_term_debt":        int(long_term_debt_val),
        "interest_bearing_debt": int(interest_bearing_debt),
        "interest_expense":      int(interest_expense),
        "interest_income":       int(interest_income),
        "total_assets":          int(total_assets),
        "total_equity":          int(total_equity),
        "source": "FMP",
        "ratios": computed_ratios,
        "raw": {
            "revenue": revenue,
            "ebit": ebit,
            "net_income": net_income,
            "ebitda": ebitda,
            "fcf": fcf,
            "total_assets": total_assets,
            "equity": equity,
            "total_debt": total_debt,
            "cash": cash,
            "ev": ev,
        },
    }


# ─── Bulk fetch ───────────────────────────────────────────────────────────────


def fetch_fundamentals_bulk_fmp(
    tickers: list[str],
    max_tickers: int = 30,
) -> dict[str, dict]:
    """
    Récupère les fondamentaux FMP pour une liste de tickers.
    Limité à 30 tickers par défaut (5 req × 30 = 150 req, dans la limite gratuite).
    """
    results = {}
    for i, ticker in enumerate(tickers[:max_tickers]):
        if ticker.startswith("^"):
            continue
        try:
            data = fetch_fundamentals_fmp(ticker)
            if data:
                results[ticker] = data
                log.info("FMP: fetched %s (%d/%d)", ticker, i + 1, min(len(tickers), max_tickers))
        except Exception as e:
            log.warning("FMP bulk error for %s: %s", ticker, e)
    return results


# ─── Upsert DB ────────────────────────────────────────────────────────────────


async def upsert_fmp_fundamentals(tickers: list[str]) -> int:
    """
    Met à jour ticker_fundamentals avec les données FMP.
    Utilisé pour les tickers non-US (CAC40, UK, AU, JP, etc.)

    Returns:
        nombre de tickers mis à jour
    """
    import asyncio
    import os

    import sqlalchemy as sa

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return 0

    sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
    engine = sa.create_engine(sync_url, pool_pre_ping=True)

    loop = asyncio.get_event_loop()
    fmp_data = await loop.run_in_executor(
        None,
        lambda: fetch_fundamentals_bulk_fmp(tickers, max_tickers=50),
    )

    from datetime import date

    today = date.today().isoformat()
    updated = 0

    with engine.begin() as conn:
        for ticker, data in fmp_data.items():
            ratios = data.get("ratios", {})
            try:
                conn.execute(
                    sa.text("""
                        INSERT INTO ticker_fundamentals
                        (ticker, name, sector, industry, country, currency, exchange,
                         market_cap, beta, dividend_yield, total_debt, total_revenue,
                         short_term_debt, long_term_debt, interest_bearing_debt,
                         interest_expense, interest_income, total_assets, total_equity,
                         updated_at, universe,
                         earning_yield_sec, roic_sec, pe_ratio, ev_ebitda,
                         net_margin, fcf_yield, debt_equity, current_ratio, sec_updated_at)
                        VALUES
                        (:ticker, :name, :sector, :industry, :country, :currency, :exchange,
                         :market_cap, :beta, :dividend_yield, :total_debt, :total_revenue,
                         :short_term_debt, :long_term_debt, :interest_bearing_debt,
                         :interest_expense, :interest_income, :total_assets, :total_equity,
                         :updated_at, :universe,
                         :earning_yield, :roic, :pe_ratio, :ev_ebitda,
                         :net_margin, :fcf_yield, :debt_equity, :current_ratio, :sec_updated_at)
                        ON CONFLICT (ticker) DO UPDATE SET
                            name = EXCLUDED.name,
                            sector = EXCLUDED.sector,
                            market_cap = EXCLUDED.market_cap,
                            total_debt            = EXCLUDED.total_debt,
                            total_revenue         = EXCLUDED.total_revenue,
                            short_term_debt       = EXCLUDED.short_term_debt,
                            long_term_debt        = EXCLUDED.long_term_debt,
                            interest_bearing_debt = EXCLUDED.interest_bearing_debt,
                            interest_expense      = EXCLUDED.interest_expense,
                            interest_income       = EXCLUDED.interest_income,
                            total_assets          = EXCLUDED.total_assets,
                            total_equity          = EXCLUDED.total_equity,
                            beta = EXCLUDED.beta,
                            earning_yield_sec = EXCLUDED.earning_yield_sec,
                            roic_sec = EXCLUDED.roic_sec,
                            pe_ratio = EXCLUDED.pe_ratio,
                            ev_ebitda = EXCLUDED.ev_ebitda,
                            net_margin = EXCLUDED.net_margin,
                            fcf_yield = EXCLUDED.fcf_yield,
                            debt_equity = EXCLUDED.debt_equity,
                            current_ratio = EXCLUDED.current_ratio,
                            sec_updated_at = EXCLUDED.sec_updated_at,
                            updated_at = EXCLUDED.updated_at
                    """),
                    {
                        "ticker": ticker,
                        "name": data.get("name", ticker),
                        "sector": data.get("sector", ""),
                        "industry": data.get("industry", ""),
                        "country": data.get("country", ""),
                        "currency": data.get("currency", "USD"),
                        "exchange": data.get("exchange", ""),
                        "market_cap": int(data.get("market_cap", 0)),
                        "beta": float(data.get("beta", 1.0)),
                        "dividend_yield": float(data.get("dividend_yield", 0)),
                        "total_debt":            int(data.get("total_debt", 0)),
                        "total_revenue":         int(data.get("total_revenue", 0)),
                        "short_term_debt":       int(data.get("short_term_debt", 0)),
                        "long_term_debt":        int(data.get("long_term_debt", 0)),
                        "interest_bearing_debt": int(data.get("interest_bearing_debt", 0)),
                        "interest_expense":      int(data.get("interest_expense", 0)),
                        "interest_income":       int(data.get("interest_income", 0)),
                        "total_assets":          int(data.get("total_assets", 0)),
                        "total_equity":          int(data.get("total_equity", 0)),
                        "updated_at": today,
                        "universe": _detect_universe(ticker),
                        "earning_yield": ratios.get("earning_yield_fmp"),
                        "roic": ratios.get("roic_fmp"),
                        "pe_ratio": ratios.get("pe_ratio"),
                        "ev_ebitda": ratios.get("ev_ebitda"),
                        "net_margin": ratios.get("net_margin"),
                        "fcf_yield": ratios.get("fcf_yield"),
                        "debt_equity": ratios.get("debt_equity"),
                        "current_ratio": ratios.get("current_ratio"),
                        "sec_updated_at": today,
                    },
                )
                updated += 1
            except Exception as e:
                log.warning("FMP DB upsert error for %s: %s", ticker, e)

    log.info("FMP fundamentals upserted: %d tickers", updated)
    return updated


def _detect_universe(ticker: str) -> str:
    """Détecte l'univers depuis le suffixe du ticker."""
    if ticker.endswith(".PA") or ticker.endswith(".AS") or ticker.endswith(".BR"):
        return "cac40" if ticker.endswith(".PA") else "msci_world"
    if ticker.endswith((".L", ".DE", ".SW", ".MI", ".MC", ".HE", ".ST", ".OL", ".CO")):
        return "msci_world"
    if ticker.endswith(".AX"):
        return "msci_world"
    if ticker.endswith(".T"):
        return "msci_world"
    if ticker.endswith(".JO"):
        return "msci_world"
    return "sp500"
