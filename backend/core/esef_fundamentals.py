"""
:file: backend/core/esef_fundamentals.py
:brief: Récupère les fondamentaux financiers depuis filings.xbrl.org (ESMA ESEF).

        Source : https://filings.xbrl.org
        - Couverture : toutes sociétés cotées UE (CAC40, DAX, FTSE, etc.)
        - Format : JSON iXBRL (facts structurés par concept IFRS)
        - Licence : données publiques ESEF
        - Coût : gratuit, sans clé API

        Mapping concepts IFRS → métriques ethical-finance :
        ┌─────────────────────────────────────────────┬──────────────────────┐
        │ Concept IFRS                                │ Métrique             │
        ├─────────────────────────────────────────────┼──────────────────────┤
        │ ifrs-full:Revenue                           │ total_revenue        │
        │ ifrs-full:GrossProfit                       │ gross_profit         │
        │ ifrs-full:ProfitLoss                        │ net_income           │
        │ ifrs-full:OtherOperatingIncomeExpense       │ ebit (proxy)         │
        │ ifrs-full:Equity                            │ total_equity         │
        │ ifrs-full:Assets                            │ total_assets         │
        │ ifrs-full:CurrentAssets                     │ current_assets       │
        │ ifrs-full:CurrentLiabilities                │ current_liabilities  │
        │ ifrs-full:LongtermBorrowings                │ long_term_debt       │
        │ ifrs-full:CurrentBorrowings...              │ short_term_debt      │
        │ ifrs-full:CashAndCashEquivalents            │ cash                 │
        │ ifrs-full:CashFlowsFromUsedInOperating...  │ operating_cash_flow  │
        │ ifrs-full:Inventories                       │ inventories          │
        │ ifrs-full:Goodwill                          │ goodwill             │
        │ ifrs-full:BasicEarningsLossPerShare         │ eps                  │
        │ ifrs-full:DividendsPaid                     │ dividends_paid       │
        └─────────────────────────────────────────────┴──────────────────────┘

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_XBRL_BASE  = "https://filings.xbrl.org"
_TIMEOUT    = 30.0
_USER_AGENT = "ethical-finance-platform contact@sauhabah-advisory.eu"


# ─────────────────────────────────────────────────────────────────────────────
# Mapping concept IFRS → clé interne
# ─────────────────────────────────────────────────────────────────────────────

_CONCEPT_MAP: dict[str, str] = {
    # P&L
    "ifrs-full:Revenue":                                          "total_revenue",
    "ifrs-full:GrossProfit":                                      "gross_profit",
    "ifrs-full:ProfitLoss":                                       "net_income",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent":           "net_income_group",
    "ifrs-full:IncomeTaxExpenseContinuingOperations":             "income_tax",
    "ifrs-full:FinanceIncomeCost":                                "net_finance_cost",
    "ifrs-full:DistributionCosts":                                "distribution_costs",
    "ifrs-full:AdministrativeExpense":                            "admin_expense",
    "ifrs-full:OtherOperatingIncomeExpense":                      "other_operating",
    "ifrs-full:ShareOfProfitLossOfAssociatesAndJointVentures"
    "AccountedForUsingEquityMethod":                              "share_of_associates",
    "ifrs-full:BasicEarningsLossPerShare":                        "eps_basic",
    "ifrs-full:DilutedEarningsLossPerShare":                      "eps_diluted",

    # Bilan — actif
    "ifrs-full:Assets":                                           "total_assets",
    "ifrs-full:NoncurrentAssets":                                 "noncurrent_assets",
    "ifrs-full:CurrentAssets":                                    "current_assets",
    "ifrs-full:Inventories":                                      "inventories",
    "ifrs-full:TradeAndOtherCurrentReceivables":                  "trade_receivables",
    "ifrs-full:CashAndCashEquivalents":                           "cash",
    "ifrs-full:Goodwill":                                         "goodwill",
    "ifrs-full:IntangibleAssetsOtherThanGoodwill":                "intangible_assets",
    "ifrs-full:PropertyPlantAndEquipment":                        "ppe",
    "ifrs-full:RightofuseAssets":                                 "right_of_use_assets",
    "ifrs-full:InvestmentAccountedForUsingEquityMethod":          "equity_investments",

    # Bilan — passif
    "ifrs-full:EquityAndLiabilities":                             "total_equity_liabilities",
    "ifrs-full:Equity":                                           "total_equity",
    "ifrs-full:EquityAttributableToOwnersOfParent":               "equity_group",
    "ifrs-full:NoncontrollingInterests":                          "minority_interests",
    "ifrs-full:NoncurrentLiabilities":                            "noncurrent_liabilities",
    "ifrs-full:CurrentLiabilities":                               "current_liabilities",
    "ifrs-full:LongtermBorrowings":                               "long_term_debt",
    "ifrs-full:CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings": "short_term_debt",
    "ifrs-full:NoncurrentLeaseLiabilities":                       "lease_liabilities_nc",
    "ifrs-full:CurrentLeaseLiabilities":                          "lease_liabilities_c",
    "ifrs-full:TradeAndOtherCurrentPayables":                     "trade_payables",
    "ifrs-full:DeferredTaxLiabilities":                           "deferred_tax_liabilities",
    "ifrs-full:DeferredTaxAssets":                                "deferred_tax_assets",

    # Cash flow
    "ifrs-full:CashFlowsFromUsedInOperatingActivities":           "operating_cash_flow",
    "ifrs-full:CashFlowsFromUsedInInvestingActivities":           "investing_cash_flow",
    "ifrs-full:CashFlowsFromUsedInFinancingActivities":           "financing_cash_flow",
    "ifrs-full:DividendsPaidClassifiedAsFinancingActivities":     "dividends_paid",
    "ifrs-full:IncomeTaxesPaidRefundClassifiedAsOperatingActivities": "taxes_paid",
}

# Concepts qui peuvent avoir plusieurs valeurs (années N et N-1) — on prend le max period
_FLOW_CONCEPTS = {
    "ifrs-full:Revenue", "ifrs-full:GrossProfit", "ifrs-full:ProfitLoss",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities",
    "ifrs-full:CashFlowsFromUsedInInvestingActivities",
    "ifrs-full:CashFlowsFromUsedInFinancingActivities",
    "ifrs-full:IncomeTaxExpenseContinuingOperations",
    "ifrs-full:FinanceIncomeCost",
    "ifrs-full:DistributionCosts", "ifrs-full:AdministrativeExpense",
    "ifrs-full:DividendsPaidClassifiedAsFinancingActivities",
    "ifrs-full:BasicEarningsLossPerShare", "ifrs-full:DilutedEarningsLossPerShare",
}


# ─────────────────────────────────────────────────────────────────────────────
# Fetch LEI depuis info-financiere.gouv.fr
# ─────────────────────────────────────────────────────────────────────────────

async def get_lei(ticker: str, client: httpx.AsyncClient) -> Optional[str]:
    """Résout ticker .PA → LEI via le dataset codes-lei."""
    fragment = ticker.upper().replace(".PA", "").replace(".FP", "")
    try:
        r = await client.get(
            "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/codes-lei/records",
            params={
                "where": f'identificationsociete_iso_nom_soc like "%{fragment}%"',
                "limit": 1,
                "select": "identificationsociete_iso_cd_lei,identificationsociete_iso_nom_soc",
            },
        )
        results = r.json().get("results", [])
        if results:
            lei = results[0].get("identificationsociete_iso_cd_lei")
            name = results[0].get("identificationsociete_iso_nom_soc")
            log.debug("LEI resolved: %s → %s (%s)", ticker, lei, name)
            return lei
    except Exception as exc:
        log.warning("LEI lookup failed for %s: %s", ticker, exc)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Fetch filing ESEF le plus récent
# ─────────────────────────────────────────────────────────────────────────────

async def get_latest_filing(lei: str, client: httpx.AsyncClient) -> Optional[dict]:
    """Retourne le filing ESEF le plus récent pour un LEI."""
    try:
        r = await client.get(
            f"{_XBRL_BASE}/api/filings",
            params={
                "filter[entity.identifier]": lei,
                "sort": "-period_end",
                "limit": 1,
            },
        )
        data = r.json().get("data", [])
        if data:
            # Trie côté Python par period_end décroissant
            data.sort(key=lambda x: x["attributes"].get("period_end", ""), reverse=True)
            return data[0]["attributes"]
    except Exception as exc:
        log.warning("Filing lookup failed for LEI %s: %s", lei, exc)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Parse le JSON iXBRL → métriques financières
# ─────────────────────────────────────────────────────────────────────────────

def _extract_period_year(period_str: str) -> Optional[int]:
    """Extrait l'année depuis une période ISO.
    Flux (2024-01-01/2025-01-01) → début → 2024.
    Stock (2024-12-31) → date → 2024.
    """
    if "/" in period_str:
        ref = period_str.split("/")[0]
    else:
        ref = period_str
    try:
        return int(ref[:4])
    except (ValueError, IndexError):
        return None


def _parse_facts(facts: dict) -> dict[str, float]:
    """
    Parse les facts iXBRL et retourne un dict {metric_key: value}.
    Pour les concepts de flux (P&L, CF), prend la période la plus récente.
    Pour les concepts de stock (bilan), prend la valeur sans dimension période.
    """
    # Regroupe les facts par concept
    by_concept: dict[str, list[dict]] = {}
    for fact in facts.values():
        dims = fact.get("dimensions", {})
        concept = dims.get("concept", "")
        if concept in _CONCEPT_MAP:
            by_concept.setdefault(concept, []).append({
                "value": fact.get("value"),
                "period": dims.get("period", ""),
                "dimensions": {k: v for k, v in dims.items()
                               if k not in ("concept", "entity", "period")},
            })

    result: dict[str, float] = {}

    for concept, entries in by_concept.items():
        key = _CONCEPT_MAP[concept]

        # Filtre : pas de dimensions supplémentaires (évite les sous-totaux)
        simple_entries = [e for e in entries if not e["dimensions"]]
        if not simple_entries:
            simple_entries = entries  # fallback : prend tout

        # Pour les flux : prend l'année la plus récente
        if concept in _FLOW_CONCEPTS:
            best = None
            best_year = 0
            for e in simple_entries:
                year = _extract_period_year(e["period"]) or 0
                if year > best_year:
                    best_year = year
                    best = e
            if best and best["value"] is not None:
                try:
                    result[key] = float(best["value"])
                except (ValueError, TypeError):
                    pass
        else:
            # Pour les stocks (bilan) : prend la valeur la plus récente
            best = None
            best_year = 0
            for e in simple_entries:
                year = _extract_period_year(e["period"]) or 0
                if year > best_year:
                    best_year = year
                    best = e
            if best and best["value"] is not None:
                try:
                    result[key] = float(best["value"])
                except (ValueError, TypeError):
                    pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Calcul des ratios depuis les métriques ESEF
# ─────────────────────────────────────────────────────────────────────────────

def _compute_ratios(m: dict, market_cap: float) -> dict[str, float]:
    """
    Calcule les ratios financiers depuis les métriques extraites.
    Équivalent de _fmp_valuation_ratios + _fmp_profitability_ratios + etc.
    """
    ratios: dict[str, float] = {}

    revenue     = m.get("total_revenue", 0)
    net_income  = m.get("net_income_group") or m.get("net_income", 0)
    gross_profit= m.get("gross_profit", 0)
    equity      = m.get("equity_group") or m.get("total_equity", 0)
    total_assets= m.get("total_assets", 0)
    lt_debt     = m.get("long_term_debt", 0)
    st_debt     = m.get("short_term_debt", 0)
    total_debt  = lt_debt + st_debt
    cash        = m.get("cash", 0)
    op_cf       = m.get("operating_cash_flow", 0)
    cur_assets  = m.get("current_assets", 0)
    cur_liab    = m.get("current_liabilities", 0)
    inventories = m.get("inventories", 0)
    ppe         = m.get("ppe", 0)
    goodwill    = m.get("goodwill", 0)
    intangibles = m.get("intangible_assets", 0)
    mc          = float(market_cap or 0)

    # EBIT approx : GrossProfit - DistributionCosts - AdminExpense + OtherOperating
    dist   = abs(m.get("distribution_costs", 0))
    admin  = abs(m.get("admin_expense", 0))
    other  = m.get("other_operating", 0)
    tax    = abs(m.get("income_tax", 0))
    fin    = m.get("net_finance_cost", 0)
    # EBIT = net_income + tax + net_finance_cost (approx)
    ebit = net_income + tax - fin if (net_income and tax) else gross_profit - dist - admin + other

    # EV
    ev = mc + total_debt - cash if mc > 0 else 0

    # ── Valorisation ─────────────────────────────────────────────────────────
    if mc > 0 and net_income and net_income > 0:
        ratios["pe_ratio"] = round(mc / net_income, 2)
    if mc > 0 and equity and equity > 0:
        ratios["pb_ratio"] = round(mc / equity, 2)
    if mc > 0 and revenue and revenue > 0:
        ratios["ps_ratio"] = round(mc / revenue, 2)
    if ev > 0 and ebit and ebit > 0:
        ratios["ev_ebit"] = round(ev / ebit, 2)
    if ev > 0 and revenue and revenue > 0:
        ratios["ev_revenue"] = round(ev / revenue, 2)
    if mc > 0 and op_cf and op_cf > 0:
        ratios["price_fcf"] = round(mc / op_cf, 2)
        ratios["fcf_yield"] = round(op_cf / mc, 4)

    # ── Rentabilité ───────────────────────────────────────────────────────────
    if revenue > 0:
        if gross_profit:
            ratios["gross_margin"] = round(gross_profit / revenue, 4)
        if net_income:
            ratios["net_margin"] = round(net_income / revenue, 4)
        if ebit:
            ratios["operating_margin"] = round(ebit / revenue, 4)
    if total_assets > 0 and net_income:
        ratios["roa"] = round(net_income / total_assets, 4)
    if equity > 0 and net_income:
        ratios["roe"] = round(net_income / equity, 4)

    # ── Magic Formula (Greenblatt) ────────────────────────────────────────────
    if ev > 0 and ebit and ebit > 0:
        ratios["earning_yield"] = round(ebit / ev, 4)
    nwc = cur_assets - cur_liab
    net_fixed = total_assets - cur_assets - goodwill - intangibles
    invested_capital = nwc + max(net_fixed, 0)
    if invested_capital > 0 and ebit and ebit > 0:
        ratios["roic"] = round(ebit / invested_capital, 4)

    # ── Levier / Liquidité ────────────────────────────────────────────────────
    if equity > 0:
        ratios["debt_equity"] = round(total_debt / equity, 2)
    if cur_liab > 0:
        ratios["current_ratio"] = round(cur_assets / cur_liab, 2)
        if inventories >= 0:
            ratios["quick_ratio"] = round((cur_assets - inventories) / cur_liab, 2)
    if ebit and ebit > 0:
        ratios["net_debt_ebit"] = round((total_debt - cash) / ebit, 2)

    # ── Sharia ratios ─────────────────────────────────────────────────────────
    if mc > 0:
        ratios["debt_to_market_cap"] = round(total_debt / mc, 4)  # critère 2
        ratios["cash_to_market_cap"] = round(cash / mc, 4)        # critère 3

    return ratios


# ─────────────────────────────────────────────────────────────────────────────
# Interface publique principale
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_fundamentals_esef(
    ticker:     str,
    lei:        Optional[str] = None,
    market_cap: float = 0,
) -> Optional[dict]:
    """
    Récupère les fondamentaux financiers depuis filings.xbrl.org pour un ticker FR.

    Args:
        ticker:     Ticker Euronext (ex: "MC.PA")
        lei:        LEI optionnel (si déjà connu, évite le lookup)
        market_cap: Market cap en euros (pour calcul des ratios)

    Returns:
        Dict compatible avec le format retourné par fetch_fundamentals_fmp(),
        ou None si non disponible.
    """
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
    ) as client:

        # ── 1. Résolution LEI ────────────────────────────────────────────────
        if not lei:
            lei = await get_lei(ticker, client)
        if not lei:
            log.info("No LEI found for %s — ESEF fundamentals unavailable", ticker)
            return None

        # ── 2. Filing le plus récent ─────────────────────────────────────────
        filing = await get_latest_filing(lei, client)
        if not filing:
            log.info("No ESEF filing found for %s (LEI: %s)", ticker, lei)
            return None

        json_url = filing.get("json_url")
        period   = filing.get("period_end", "")[:10]
        if not json_url:
            return None

        log.info("ESEF fundamentals: fetching %s (period: %s)", ticker, period)

        # ── 3. Fetch facts JSON ──────────────────────────────────────────────
        try:
            r = await client.get(f"{_XBRL_BASE}{json_url}", timeout=60.0)
            r.raise_for_status()
            facts = r.json().get("facts", {})
        except Exception as exc:
            log.warning("ESEF JSON fetch failed for %s: %s", ticker, exc)
            return None

        if not facts:
            log.info("Empty facts in ESEF filing for %s", ticker)
            return None

        # ── 4. Parse métriques ───────────────────────────────────────────────
        metrics = _parse_facts(facts)

        if not metrics.get("total_revenue"):
            log.info("No revenue found in ESEF facts for %s", ticker)
            return None

        # ── 5. Calcul ratios ─────────────────────────────────────────────────
        ratios = _compute_ratios(metrics, market_cap)

        total_debt = metrics.get("long_term_debt", 0) + metrics.get("short_term_debt", 0)

        log.info(
            "ESEF fundamentals OK for %s: revenue=%.1fB, net_income=%.1fB, ratios=%d",
            ticker,
            metrics.get("total_revenue", 0) / 1e9,
            metrics.get("net_income", 0) / 1e9,
            len(ratios),
        )

        return {
            "ticker":         ticker,
            "period":         period,
            "source":         "ESEF",
            "total_revenue":  int(metrics.get("total_revenue", 0)),
            "total_debt":     int(total_debt),
            "total_cash":     int(metrics.get("cash", 0)),
            "total_equity":   int(metrics.get("total_equity", 0)),
            "total_assets":   int(metrics.get("total_assets", 0)),
            "net_income":     int(metrics.get("net_income", 0)),
            "operating_cf":   int(metrics.get("operating_cash_flow", 0)),
            "ratios":         ratios,
            "raw":            metrics,
        }
