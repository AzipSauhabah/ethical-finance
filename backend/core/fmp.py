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
import time

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
    mc = float(profile.get("marketCap") or market_cap or 0)
    total_debt = float(balance.get("totalDebt") or balance.get("longTermDebt") or 0)
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

    # ── Ratios calculés ───────────────────────────────────────────────────────
    computed_ratios = {}

    # Valorisation
    if mc > 0 and net_income > 0:
        computed_ratios["pe_ratio"] = round(mc / net_income, 2)
    if ev > 0 and ebitda > 0:
        computed_ratios["ev_ebitda"] = round(ev / ebitda, 2)
    if ev > 0 and revenue > 0:
        computed_ratios["ev_revenue"] = round(ev / revenue, 2)
    if mc > 0 and equity > 0:
        computed_ratios["pb_ratio"] = round(mc / equity, 2)
    if mc > 0 and fcf > 0:
        computed_ratios["price_fcf"] = round(mc / fcf, 2)
        computed_ratios["fcf_yield"] = round(fcf / mc, 4)

    # Rentabilité
    if revenue > 0:
        if net_income:
            computed_ratios["net_margin"] = round(net_income / revenue, 4)
        if ebit:
            computed_ratios["operating_margin"] = round(ebit / revenue, 4)
    if total_assets > 0 and net_income:
        computed_ratios["roa"] = round(net_income / total_assets, 4)
    if equity > 0 and net_income:
        computed_ratios["roe"] = round(net_income / equity, 4)

    # Magic Formula
    if ev > 0 and ebit:
        computed_ratios["earning_yield_fmp"] = round(ebit / ev, 4)
    net_working_capital = current_assets - current_liabilities
    net_fixed_assets = total_assets - current_assets
    invested_capital = net_working_capital + net_fixed_assets
    if invested_capital > 0 and ebit:
        computed_ratios["roic_fmp"] = round(ebit / invested_capital, 4)

    # Levier
    if equity > 0:
        computed_ratios["debt_equity"] = round(total_debt / equity, 2)
    if ebitda > 0:
        computed_ratios["net_debt_ebitda"] = round((total_debt - cash) / ebitda, 2)

    # Liquidité
    if current_liabilities > 0:
        computed_ratios["current_ratio"] = round(current_assets / current_liabilities, 2)

    # Compléter avec les ratios FMP si disponibles
    fmp_ratios = {
        "pe_ratio": ratios.get("priceEarningsRatio"),
        "pb_ratio": ratios.get("priceToBookRatio"),
        "ev_ebitda": ratios.get("enterpriseValueMultiple"),
        "roe": ratios.get("returnOnEquity"),
        "roa": ratios.get("returnOnAssets"),
        "roic_fmp": ratios.get("returnOnCapitalEmployed"),
        "net_margin": ratios.get("netProfitMargin"),
        "current_ratio": ratios.get("currentRatio"),
        "debt_equity": ratios.get("debtEquityRatio"),
        "dividend_yield": ratios.get("dividendYield"),
    }
    for k, v in fmp_ratios.items():
        if v is not None and k not in computed_ratios:
            try:
                computed_ratios[k] = round(float(v), 4)
            except Exception:
                pass

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
        "total_debt": int(total_debt),
        "total_revenue": int(revenue),
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
                         updated_at, universe,
                         earning_yield_sec, roic_sec, pe_ratio, ev_ebitda,
                         net_margin, fcf_yield, debt_equity, current_ratio, sec_updated_at)
                        VALUES
                        (:ticker, :name, :sector, :industry, :country, :currency, :exchange,
                         :market_cap, :beta, :dividend_yield, :total_debt, :total_revenue,
                         :updated_at, :universe,
                         :earning_yield, :roic, :pe_ratio, :ev_ebitda,
                         :net_margin, :fcf_yield, :debt_equity, :current_ratio, :sec_updated_at)
                        ON CONFLICT (ticker) DO UPDATE SET
                            name = EXCLUDED.name,
                            sector = EXCLUDED.sector,
                            market_cap = EXCLUDED.market_cap,
                            total_debt = EXCLUDED.total_debt,
                            total_revenue = EXCLUDED.total_revenue,
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
                        "total_debt": int(data.get("total_debt", 0)),
                        "total_revenue": int(data.get("total_revenue", 0)),
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
