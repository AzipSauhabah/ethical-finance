"""
:file: backend/core/sec_edgar.py
:brief: Fetcher de fondamentaux depuis SEC EDGAR (US GAAP officiel).

Couvre tous les tickers SP500 (sociétés US cotées).
API gratuite — pas de clé requise.
Rate limit : 10 req/s max (on throttle à 0.2s entre requêtes).

Données extraites :
  - Revenue (Revenus)
  - NetIncomeLoss (Résultat net)
  - OperatingIncomeLoss (EBIT proxy)
  - Assets (Total actif)
  - Liabilities (Total passif)
  - StockholdersEquity (Capitaux propres)
  - LongTermDebt (Dette long terme)
  - CashAndCashEquivalentsAtCarryingValue (Trésorerie)
  - EarningsPerShareBasic (BPA)
  - CommonStockSharesOutstanding (Actions en circulation)
  - ResearchAndDevelopmentExpense (R&D)
  - DividendsCommonStock (Dividendes)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

import requests

log = logging.getLogger(__name__)

SEC_BASE = "https://data.sec.gov"
USER_AGENT = "sauhabah@ethical-finance.eu"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
RATE_LIMIT_SLEEP = 0.15  # secondes entre requêtes


# ─── Facts GAAP à extraire ────────────────────────────────────────────────────

FACTS_MAP = {
    # Compte de résultat
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "net_income": [
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "ebitda_proxy": [
        "OperatingIncomeLoss",
    ],
    "rd_expense": [
        "ResearchAndDevelopmentExpense",
    ],
    "depreciation": [
        "DepreciationDepletionAndAmortization",
        "Depreciation",
    ],
    # Bilan
    "total_assets": [
        "Assets",
    ],
    "total_liabilities": [
        "Liabilities",
    ],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "short_term_debt": [
        "ShortTermBorrowings",
        "LongTermDebtCurrent",
        "NotesPayableCurrent",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "current_assets": [
        "AssetsCurrent",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
    ],
    "inventory": [
        "InventoryNet",
    ],
    "accounts_receivable": [
        "AccountsReceivableNetCurrent",
    ],
    # Par action
    "eps_basic": [
        "EarningsPerShareBasic",
    ],
    "eps_diluted": [
        "EarningsPerShareDiluted",
    ],
    "shares_outstanding": [
        "CommonStockSharesOutstanding",
    ],
    # Dividendes
    "dividends": [
        "DividendsCommonStock",
        "DividendsCommonStockCash",
    ],
    # Cash flow
    "operating_cashflow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CapitalExpendituresIncurredButNotYetPaid",
    ],
    "free_cashflow_proxy": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
}


# ─── CIK lookup ──────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _load_ticker_cik_map() -> dict[str, str]:
    """Charge le mapping ticker → CIK depuis SEC EDGAR."""
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        # Format: {0: {cik_str, entity_name, ticker}, ...}
        mapping = {}
        for entry in data.values():
            ticker = entry.get("ticker", "").upper()
            cik = str(entry.get("cik_str", "")).zfill(10)
            if ticker:
                mapping[ticker] = cik
        log.info("SEC CIK map loaded: %d tickers", len(mapping))
        return mapping
    except Exception as e:
        log.warning("Failed to load SEC CIK map: %s", e)
        return {}


def get_cik(ticker: str) -> str | None:
    """Retourne le CIK SEC pour un ticker donné."""
    mapping = _load_ticker_cik_map()
    return mapping.get(ticker.upper().replace("-", "."))


# ─── Company facts fetcher ────────────────────────────────────────────────────


def _fetch_company_facts(cik: str) -> dict | None:
    """Télécharge les facts GAAP d'une société depuis SEC EDGAR."""
    try:
        url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("SEC facts fetch error (CIK %s): %s", cik, e)
        return None


def _extract_latest_annual(facts: dict, concept_names: list[str]) -> float | None:
    """
    Extrait la dernière valeur annuelle (form 10-K) d'un concept GAAP.
    Essaie chaque nom dans concept_names jusqu'à trouver.
    """
    gaap = facts.get("facts", {}).get("us-gaap", {})

    for concept in concept_names:
        if concept not in gaap:
            continue

        units = gaap[concept].get("units", {})
        # Unité principale : USD pour montants, shares pour actions, USD/shares pour EPS
        for unit_key in ["USD", "shares", "USD/shares"]:
            if unit_key not in units:
                continue

            entries = units[unit_key]
            # Filtrer les 10-K annuels uniquement
            annual = [
                e
                for e in entries
                if e.get("form") in ("10-K", "10-K/A") and e.get("val") is not None
            ]
            if not annual:
                continue

            # Prendre la plus récente par end date
            annual.sort(key=lambda x: x.get("end", ""), reverse=True)
            latest = annual[0]
            return float(latest["val"])

    return None


# ─── Ratios calculés ──────────────────────────────────────────────────────────


def _compute_valuation_ratios(ev: float, market_cap: float, revenue, net_income, ebitda: float, equity, fcf: float) -> dict:
    """Compute valuation ratios: EV/Sales, EV/EBITDA, P/E, P/B, P/FCF."""
    ratios = {}
    if ev > 0 and revenue:
        ratios["ev_sales"] = round(ev / revenue, 3)
    if ev > 0 and ebitda > 0:
        ratios["ev_ebitda"] = round(ev / ebitda, 3)
    if market_cap > 0 and net_income and net_income > 0:
        ratios["pe_ratio"] = round(market_cap / net_income, 3)
    if market_cap > 0 and equity and equity > 0:
        ratios["pb_ratio"] = round(market_cap / equity, 3)
    if market_cap > 0 and fcf > 0:
        ratios["price_fcf"] = round(market_cap / fcf, 3)
    return ratios


def _compute_profitability_ratios(revenue, net_income, operating_income, total_assets, equity, operating_cf) -> dict:
    """Compute profitability ratios: margins, ROA, ROE."""
    ratios = {}
    if revenue and revenue > 0:
        if net_income is not None:
            ratios["net_margin"] = round(net_income / revenue, 4)
        if operating_income is not None:
            ratios["operating_margin"] = round(operating_income / revenue, 4)
        if operating_cf is not None:
            ratios["ocf_margin"] = round(operating_cf / revenue, 4)
    if total_assets and total_assets > 0 and net_income is not None:
        ratios["roa"] = round(net_income / total_assets, 4)
    if equity and equity > 0 and net_income is not None:
        ratios["roe"] = round(net_income / equity, 4)
    return ratios


def _compute_leverage_ratios(total_debt: float, equity, ebitda: float, current_assets, current_liabilities) -> dict:
    """Compute leverage and liquidity ratios."""
    ratios = {}
    if equity and equity > 0:
        ratios["debt_to_equity"] = round(total_debt / equity, 3)
    if ebitda > 0:
        ratios["debt_to_ebitda"] = round(total_debt / ebitda, 3)
    if current_assets and current_liabilities and current_liabilities > 0:
        ratios["current_ratio"] = round(current_assets / current_liabilities, 3)
        current_debt = current_liabilities
        ratios["quick_ratio"] = round((current_assets - (current_assets * 0.3)) / current_debt, 3)
    return ratios


def _compute_magic_formula(ev: float, operating_income, equity, total_debt: float, _cash: float) -> dict:
    """Compute Magic Formula ratios: earning yield and ROIC."""
    ratios = {}
    if ev > 0 and operating_income:
        earning_yield = operating_income / ev
        ratios["earning_yield"] = round(earning_yield, 4)
        net_working_capital = max(0, (equity or 0) - total_debt) if equity else 0
        net_fixed_assets = max(0, (equity or 0) * 0.5) if equity else 0
        invested_capital = net_working_capital + net_fixed_assets
        if invested_capital > 0:
            ratios["roic"] = round(operating_income / invested_capital, 4)
        else:
            ratios["roic"] = 0.0
        ratios["magic_formula_rank"] = round(earning_yield * 100, 2)
    return ratios


def _compute_ratios(raw: dict, market_cap: float) -> dict:
    """Calcule les ratios financiers à partir des données brutes SEC."""
    ratios = {}

    revenue = raw.get("revenue")
    net_income = raw.get("net_income")
    operating_income = raw.get("operating_income")
    total_assets = raw.get("total_assets")
    equity = raw.get("equity")
    long_term_debt = raw.get("long_term_debt", 0) or 0
    short_term_debt = raw.get("short_term_debt", 0) or 0
    cash = raw.get("cash", 0) or 0
    operating_cf = raw.get("operating_cashflow")
    capex = raw.get("capex", 0) or 0
    current_assets = raw.get("current_assets")
    current_liabilities = raw.get("current_liabilities")

    total_debt = long_term_debt + short_term_debt
    ebitda = (operating_income or 0) + raw.get("depreciation", 0) or 0
    ev = market_cap + total_debt - cash
    fcf = (operating_cf or 0) - capex

    ratios.update(_compute_valuation_ratios(ev, market_cap, revenue, net_income, ebitda, equity, fcf))
    ratios.update(_compute_profitability_ratios(revenue, net_income, operating_income, total_assets, equity, operating_cf))

    # Ratios de levier et liquidité
    ratios.update(_compute_leverage_ratios(total_debt, equity, ebitda, current_assets, current_liabilities))

    ratios.update(_compute_magic_formula(ev, operating_income, equity, total_debt, cash))
    if market_cap > 0 and fcf > 0:
        ratios["fcf_yield"] = round(fcf / market_cap, 4)
    for k, v in [("revenue_ttm", revenue), ("net_income_ttm", net_income), ("fcf_ttm", fcf if fcf else None)]:
        if v is not None:
            ratios[k] = v
    ratios.update({"total_debt": total_debt, "cash": cash, "ev": ev, "ebitda": ebitda})

    return ratios


def fetch_fundamentals_sec(ticker: str, market_cap: float = 0) -> dict | None:
    """
    Récupère les fondamentaux complets d'un ticker depuis SEC EDGAR.

    Args:
        ticker: symbole boursier (ex: AAPL, MSFT)
        market_cap: capitalisation boursière en USD (pour calculer les ratios)

    Returns:
        dict avec raw data + ratios calculés, ou None si non trouvé
    """
    cik = get_cik(ticker)
    if not cik:
        log.debug("SEC: CIK not found for %s", ticker)
        return None

    time.sleep(RATE_LIMIT_SLEEP)
    facts = _fetch_company_facts(cik)
    if not facts:
        return None

    # Extraire les données brutes
    raw = {}
    for key, concept_names in FACTS_MAP.items():
        val = _extract_latest_annual(facts, concept_names)
        if val is not None:
            raw[key] = val

    if not raw:
        log.debug("SEC: no GAAP facts extracted for %s (CIK %s)", ticker, cik)
        return None

    # Calculer les ratios
    ratios = _compute_ratios(raw, market_cap)

    return {
        "ticker": ticker,
        "cik": cik,
        "source": "SEC_EDGAR",
        "raw": raw,
        "ratios": ratios,
    }


def fetch_fundamentals_bulk_sec(
    tickers: list[str],
    market_caps: dict[str, float] | None = None,
    max_tickers: int = 50,
) -> dict[str, dict]:
    """
    Récupère les fondamentaux SEC pour une liste de tickers.
    Throttlé à RATE_LIMIT_SLEEP secondes entre chaque requête.

    Args:
        tickers: liste de tickers
        market_caps: dict ticker → market_cap
        max_tickers: limite pour éviter les timeouts (défaut 50)

    Returns:
        dict ticker → fundamentals
    """
    results = {}
    market_caps = market_caps or {}

    for i, ticker in enumerate(tickers[:max_tickers]):
        if ticker.startswith("^"):
            continue
        mc = market_caps.get(ticker, 0)
        try:
            data = fetch_fundamentals_sec(ticker, mc)
            if data:
                results[ticker] = data
                log.debug("SEC: fetched %s (%d/%d)", ticker, i + 1, min(len(tickers), max_tickers))
        except Exception as e:
            log.warning("SEC bulk error for %s: %s", ticker, e)

    log.info("SEC bulk fetch complete: %d/%d tickers", len(results), min(len(tickers), max_tickers))
    return results


# ─── Upsert dans ticker_fundamentals ─────────────────────────────────────────


async def upsert_sec_fundamentals(tickers: list[str]) -> int:
    """
    Met à jour ticker_fundamentals avec les données SEC EDGAR.
    Enrichit les colonnes existantes + ajoute les ratios SEC.

    Returns:
        nombre de tickers mis à jour
    """
    import asyncio
    import os

    import sqlalchemy as sa

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        log.warning("DATABASE_URL not set")
        return 0

    sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
    engine = sa.create_engine(sync_url, pool_pre_ping=True)

    # Récupérer les market caps existantes
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT ticker, market_cap FROM ticker_fundamentals WHERE ticker = ANY(:t)"),
            {"t": tickers},
        ).fetchall()
    market_caps = {r[0]: float(r[1] or 0) for r in rows}

    # Fetch SEC (synchrone dans executor)
    loop = asyncio.get_event_loop()
    sec_data = await loop.run_in_executor(
        None,
        lambda: fetch_fundamentals_bulk_sec(tickers, market_caps, max_tickers=100),
    )

    # Upsert dans la DB
    from datetime import date

    today = date.today().isoformat()
    updated = 0
    with engine.begin() as conn:
        for ticker, data in sec_data.items():
            raw = data.get("raw", {})
            ratios = data.get("ratios", {})

            try:
                conn.execute(
                    sa.text("""
                        UPDATE ticker_fundamentals SET
                            total_debt         = COALESCE(:total_debt, total_debt),
                            total_revenue      = COALESCE(:total_revenue, total_revenue),
                            earning_yield_sec  = :earning_yield_sec,
                            roic_sec           = :roic_sec,
                            pe_ratio           = :pe_ratio,
                            ev_ebitda          = :ev_ebitda,
                            net_margin         = :net_margin,
                            fcf_yield          = :fcf_yield,
                            debt_equity        = :debt_equity,
                            current_ratio      = :current_ratio,
                            sec_updated_at     = :sec_updated_at,
                            updated_at         = :updated_at
                        WHERE ticker = :ticker
                    """),
                    {
                        "ticker": ticker,
                        "total_debt": int(ratios.get("total_debt", 0) or 0),
                        "total_revenue": int(raw.get("revenue", 0) or 0),
                        "earning_yield_sec": ratios.get("earning_yield_sec"),
                        "roic_sec": ratios.get("roic_sec"),
                        "pe_ratio": ratios.get("pe_ratio"),
                        "ev_ebitda": ratios.get("ev_ebitda"),
                        "net_margin": ratios.get("net_margin"),
                        "fcf_yield": ratios.get("fcf_yield"),
                        "debt_equity": ratios.get("debt_equity"),
                        "current_ratio": ratios.get("current_ratio"),
                        "sec_updated_at": today,
                        "updated_at": today,
                    },
                )
                updated += 1
            except Exception as e:
                log.warning("DB upsert error for %s: %s", ticker, e)

    log.info("SEC fundamentals upserted: %d tickers", updated)
    return updated
