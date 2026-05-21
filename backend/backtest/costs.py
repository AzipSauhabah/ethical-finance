"""
:file: api/backtest/costs.py
:brief: Real cost model: broker commissions, bid-ask spread/slippage, FX,
        and French taxes (PFU, TTF).

        All functions are pure — they take trade details and return cost in EUR.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

from typing import Literal

from backend.config import (
    BROKER_FEES,
    CUSTODY_FEES_ANNUAL_BPS,
    MARKET_IMPACT_BPS,
    SLIPPAGE_BPS,
    STAMP_DUTY,
    TAX_RATES,
    TYPICAL_ADV_EUR,
    WITHHOLDING_TAX,
)


def _broker_schedule(broker: str) -> dict:
    return BROKER_FEES.get(broker.lower(), BROKER_FEES["default"])


# ─────────────────────────────────────────────────────────────────────────────
# Commission
# ─────────────────────────────────────────────────────────────────────────────


def broker_commission(
    notional_eur: float,
    broker: str = "default",
    asset_type: Literal["stock_eu", "stock_us", "etf"] = "stock_eu",
) -> float:
    """Compute broker commission in EUR.

    :param notional_eur: trade size in EUR (already converted from USD if needed)
    :param broker: broker name key (see config.BROKER_FEES)
    :param asset_type: ``'stock_eu'`` | ``'stock_us'`` | ``'etf'``
    :returns: commission in EUR (always positive)
    """
    sch = _broker_schedule(broker)

    if broker.lower() == "fortuneo" and asset_type == "stock_us":
        # Fortuneo special schedule for US equities
        threshold = sch.get("stock_us_flat_threshold", 7_500.0)
        if notional_eur <= threshold:
            return float(sch.get("stock_us_flat_fee", 50.0))
        else:
            return float(
                notional_eur * sch.get("stock_us_pct_above", 0.002)
                + sch.get("stock_us_fixed_above", 9.0)
            )

    fixed = float(sch.get(f"{asset_type}_fixed", sch.get("stock_eu_fixed", 1.0)))
    pct = float(sch.get(f"{asset_type}_pct", sch.get("stock_eu_pct", 0.001)))
    fee = fixed + notional_eur * pct
    fee = max(fee, float(sch.get("min_fee", 0.0)))
    max_f = sch.get("max_fee")
    if max_f is not None:
        fee = min(fee, float(max_f))
    return fee


# ─────────────────────────────────────────────────────────────────────────────
# Slippage
# ─────────────────────────────────────────────────────────────────────────────


def slippage_cost(
    notional_eur: float,
    cap_size: Literal["large_cap", "mid_cap", "small_cap", "etf"] = "mid_cap",
) -> float:
    """Estimate bid-ask / slippage cost in EUR.

    :param cap_size: category determining BPS
    """
    bps = SLIPPAGE_BPS.get(cap_size, SLIPPAGE_BPS["mid_cap"])
    return notional_eur * bps / 10_000.0


# ─────────────────────────────────────────────────────────────────────────────
# FX cost (EUR/USD spread)
# ─────────────────────────────────────────────────────────────────────────────


def fx_spread_cost(
    notional_eur: float,
    currency: str = "USD",
    spread_bps: float = 3.0,  # retail FX spread ~3 bps
) -> float:
    """Estimate FX conversion cost for non-EUR assets."""
    if currency.upper() == "EUR":
        return 0.0
    return notional_eur * spread_bps / 10_000.0


# ─────────────────────────────────────────────────────────────────────────────
# TTF (Taxe sur les transactions financières)
# ─────────────────────────────────────────────────────────────────────────────


def ttf_tax(
    notional_eur: float,
    market_cap_eur: float = 2e9,  # default: large-cap (TTF applies)
) -> float:
    """French TTF — 0.1 % on buy-side for companies with market cap > 1 Bn EUR."""
    if market_cap_eur < TAX_RATES["ttf_threshold_market_cap"]:
        return 0.0
    return notional_eur * TAX_RATES["ttf_rate"]


# ─────────────────────────────────────────────────────────────────────────────
# Capital gains tax
# ─────────────────────────────────────────────────────────────────────────────


def capital_gains_tax(
    gain_eur: float,
    account_type: str = "CTO",
    pea_years: int = 0,
) -> float:
    """Compute French capital gains tax on realised profits.

    :param account_type: ``'CTO'`` | ``'PEA'``
    :param pea_years: years since PEA opening (exempt from IR after 5 y)
    """
    if gain_eur <= 0:
        return 0.0

    if account_type.upper() == "PEA":
        if pea_years >= TAX_RATES["pea_capital_exempt_years"]:
            return gain_eur * TAX_RATES["pea_social_rate"]
        else:
            return gain_eur * TAX_RATES["pfu_rate"]

    return gain_eur * TAX_RATES["pfu_rate"]


# ─────────────────────────────────────────────────────────────────────────────
# Total round-trip cost
# ─────────────────────────────────────────────────────────────────────────────


def total_trade_cost(
    notional_eur: float,
    broker: str = "default",
    asset_type: Literal["stock_eu", "stock_us", "etf"] = "stock_eu",
    cap_size: Literal["large_cap", "mid_cap", "small_cap", "etf"] = "mid_cap",
    currency: str = "EUR",
    market_cap_eur: float = 2e9,
    side: Literal["buy", "sell"] = "buy",
    country: str = "US",
) -> dict[str, float]:
    """Compute all costs for a single trade — modèle réaliste complet.

    Inclut :
    - Commission broker (grille tarifaire réelle)
    - Slippage bid-ask (selon capitalisation)
    - Impact marché (modèle racine carrée)
    - Spread FX (si non-EUR)
    - TTF (actions françaises > 1Md€)
    - Stamp duty (UK 0.5%, BE 0.35%, IT 0.2%)

    :returns: dict avec le détail de chaque composante et le total
    """
    comm = broker_commission(notional_eur, broker, asset_type)
    slip = slippage_cost(notional_eur, cap_size)
    impact = market_impact_cost(notional_eur, cap_size)
    fx = fx_spread_cost(notional_eur, currency)
    tax = ttf_tax(notional_eur, market_cap_eur) if side == "buy" else 0.0
    stamp = stamp_duty_cost(notional_eur, country, market_cap_eur)
    total = comm + slip + impact + fx + tax + stamp
    return {
        "commission": round(comm, 4),
        "slippage": round(slip, 4),
        "market_impact": round(impact, 4),
        "fx_spread": round(fx, 4),
        "ttf": round(tax, 4),
        "stamp_duty": round(stamp, 4),
        "total": round(total, 4),
        "notional": notional_eur,
        "cost_pct": round(total / notional_eur * 100, 4) if notional_eur > 0 else 0.0,
        "cost_bps": round(total / notional_eur * 10_000, 2) if notional_eur > 0 else 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Impact marché (modèle linéaire)
# ─────────────────────────────────────────────────────────────────────────────


def market_impact_cost(
    notional_eur: float,
    cap_size: str = "mid_cap",
    _participation_rate: float = 0.05,
) -> float:
    """
    Coût d'impact marché — modèle linéaire.

    Impact = impact_bps × sqrt(notional / ADV)
    Plus l'ordre est grand par rapport au volume journalier,
    plus le prix se dégrade.

    Args:
        notional_eur: taille de l'ordre en EUR
        cap_size: catégorie de capitalisation
        _participation_rate: fraction du volume journalier (défaut 5%)

    Returns:
        coût en EUR
    """
    impact_bps = MARKET_IMPACT_BPS.get(cap_size, MARKET_IMPACT_BPS["mid_cap"])
    adv = TYPICAL_ADV_EUR.get(cap_size, TYPICAL_ADV_EUR["mid_cap"])

    # Impact proportionnel à la racine carrée de la participation
    participation = min(notional_eur / max(adv, 1), 1.0)
    impact = notional_eur * impact_bps / 10_000.0 * (participation**0.5)
    return impact


# ─────────────────────────────────────────────────────────────────────────────
# Withholding tax sur dividendes
# ─────────────────────────────────────────────────────────────────────────────


def withholding_tax_cost(
    dividend_eur: float,
    country: str = "US",
    account_type: str = "CTO",
) -> float:
    """
    Retenue à la source sur dividendes.

    Sur un CTO français, la retenue à la source est prélevée à la source
    et partiellement récupérable via la déclaration fiscale (crédit d'impôt).
    Sur un PEA, les dividendes de sociétés hors UE ne sont pas éligibles.

    Args:
        dividend_eur: montant brut du dividende en EUR
        country: pays d'origine de la société
        account_type: "CTO", "PEA", "PEA_PME"

    Returns:
        montant de la retenue en EUR (coût net pour l'investisseur)
    """
    if account_type.upper() == "PEA":
        # PEA : pas de withholding (sociétés UE uniquement)
        return 0.0

    rate = WITHHOLDING_TAX.get(country.upper(), WITHHOLDING_TAX["default"])
    # Crédit d'impôt partiel récupérable (convention fiscale FR)
    # On applique seulement la part non récupérable (~50% en moyenne)
    net_rate = rate * 0.5  # approximation crédit d'impôt
    return dividend_eur * net_rate


# ─────────────────────────────────────────────────────────────────────────────
# Stamp duty / PTT
# ─────────────────────────────────────────────────────────────────────────────


def stamp_duty_cost(
    notional_eur: float,
    country: str = "US",
    market_cap_eur: float = 0.0,
) -> float:
    """
    Taxe boursière selon le pays de cotation.

    Args:
        notional_eur: montant de la transaction en EUR
        country: pays de cotation (UK, BE, IT, FR, etc.)
        market_cap_eur: capitalisation boursière (pour TTF italienne)

    Returns:
        montant de la taxe en EUR
    """
    country = country.upper()

    # Italie : Tobin Tax uniquement si cap > 500M€
    if country == "IT" and market_cap_eur < 500_000_000:
        return 0.0

    rate = STAMP_DUTY.get(country, STAMP_DUTY["default"])
    return notional_eur * rate


# ─────────────────────────────────────────────────────────────────────────────
# Frais de garde (custody fees)
# ─────────────────────────────────────────────────────────────────────────────


def custody_fee_daily(
    portfolio_value_eur: float,
    broker: str = "default",
) -> float:
    """
    Frais de garde journaliers (fraction des frais annuels).

    Args:
        portfolio_value_eur: valeur du portefeuille en EUR
        broker: courtier

    Returns:
        frais de garde pour la journée en EUR
    """
    annual_bps = CUSTODY_FEES_ANNUAL_BPS.get(broker.lower(), CUSTODY_FEES_ANNUAL_BPS["default"])
    annual_fee = portfolio_value_eur * annual_bps / 10_000.0
    return annual_fee / 252.0  # fraction journalière


# ─────────────────────────────────────────────────────────────────────────────
# Coût total réaliste d'une transaction
# ─────────────────────────────────────────────────────────────────────────────


def total_transaction_cost(
    notional_eur: float,
    broker: str = "default",
    asset_type: str = "stock_eu",
    cap_size: str = "mid_cap",
    country: str = "US",
    market_cap_eur: float = 0.0,
    is_french: bool = False,
) -> dict[str, float]:
    """
    Calcule le coût total réaliste d'une transaction.

    Inclut :
    - Commission broker
    - Slippage bid-ask
    - Impact marché
    - Spread FX (si non-EUR)
    - TTF (si action française > 1Md€)
    - Stamp duty (si UK, BE, IT)

    Returns:
        dict avec le détail de chaque composante et le total
    """
    commission = broker_commission(notional_eur, broker, asset_type)
    slippage = slippage_cost(notional_eur, cap_size)
    impact = market_impact_cost(notional_eur, cap_size)
    fx = fx_spread_cost(notional_eur, "USD" if country != "FR" else "EUR")
    ttf = french_ttf(notional_eur, market_cap_eur) if is_french else 0.0
    stamp = stamp_duty_cost(notional_eur, country, market_cap_eur)

    total = commission + slippage + impact + fx + ttf + stamp

    return {
        "commission": round(commission, 4),
        "slippage": round(slippage, 4),
        "market_impact": round(impact, 4),
        "fx_spread": round(fx, 4),
        "ttf": round(ttf, 4),
        "stamp_duty": round(stamp, 4),
        "total": round(total, 4),
        "total_bps": round(total / max(notional_eur, 1) * 10_000, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaire — déduire le pays depuis le ticker
# ─────────────────────────────────────────────────────────────────────────────


def country_from_ticker(ticker: str) -> str:
    """
    Déduit le pays de cotation depuis le suffixe du ticker.

    Exemples :
        AAPL      → US
        MC.PA     → FR
        HSBA.L    → UK
        SAP.DE    → DE
        ASML.AS   → NL
        UCG.MI    → IT
        AGS.BR    → BE
        NESN.SW   → CH
        7203.T    → JP
        BHP.AX    → AU
    """
    ticker = ticker.upper()
    if "." not in ticker:
        return "US"  # ticker sans suffixe = US par défaut

    suffix = ticker.rsplit(".", 1)[-1]
    mapping = {
        "PA": "FR",
        "CO": "FR",  # France
        "L": "UK",
        "LON": "UK",  # UK
        "DE": "DE",
        "XETRA": "DE",  # Allemagne
        "AS": "NL",
        "AMS": "NL",  # Pays-Bas
        "MI": "IT",
        "MIL": "IT",  # Italie
        "BR": "BE",  # Belgique
        "SW": "CH",
        "VX": "CH",  # Suisse
        "T": "JP",
        "TYO": "JP",  # Japon
        "AX": "AU",  # Australie
        "TO": "CA",  # Canada
        "HK": "HK",  # Hong Kong
        "SS": "CN",
        "SZ": "CN",  # Chine
        "KS": "KR",  # Corée du Sud
        "NS": "IN",
        "BO": "IN",  # Inde
        "SA": "BR",  # Brésil
        "MX": "MX",  # Mexique
        "MC": "ES",  # Espagne
        "LS": "PT",  # Portugal
        "HE": "FI",  # Finlande
        "ST": "SE",  # Suède
        "OL": "NO",  # Norvège
        "CO2": "DK",  # Danemark
        "IS": "IE",  # Irlande
        "WA": "PL",  # Pologne
        "PR": "CZ",  # Tchéquie
    }
    return mapping.get(suffix, "US")


def cap_size_from_market_cap(market_cap_eur: float) -> str:
    """Déduit la catégorie de capitalisation depuis la market cap en EUR."""
    if market_cap_eur >= 10_000_000_000:  # > 10 Md€
        return "large_cap"
    elif market_cap_eur >= 1_000_000_000:  # 1-10 Md€
        return "mid_cap"
    elif market_cap_eur >= 100_000_000:  # 100M-1Md€
        return "small_cap"
    else:
        return "micro_cap"
